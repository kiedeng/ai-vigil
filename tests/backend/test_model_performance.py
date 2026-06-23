import json
from pathlib import Path
from io import BytesIO

from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import (
    ModelPerformanceComparison,
    ModelPerformanceComparisonItem,
    ModelPerformanceRun,
    ModelPerformanceTest,
    NewApiInstance,
)
from backend.app.services.model_performance import (
    _evalscope_failure_message,
    analyze_evalscope_output,
    build_evalscope_command,
    cancel_model_performance_run,
    create_model_performance_run,
    read_run_log,
)
from backend.app.services import model_performance_datasets
from backend.app.services.model_performance_comparisons import (
    build_comparison_report,
    read_comparison_log,
    validate_comparison_items,
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return session_factory()


def test_build_evalscope_command_redacts_authorization_header():
    db = _db()
    try:
        instance = NewApiInstance(
            name="local",
            base_url="http://localhost:3000",
            api_key="secret-token",
            enabled=True,
            is_default=True,
        )
        test = ModelPerformanceTest(
            name="perf",
            model_name="qwen",
            endpoint="/v1/chat/completions",
            dataset_config={},
            load_config={"parallel": [3], "number": 7, "stream": True},
            threshold_config={},
            extra_args={},
            new_api_instance_id=1,
        )
        db.add(instance)
        db.add(test)
        db.commit()
        db.refresh(test)

        command, sanitized = build_evalscope_command(db, test, Path("/tmp/run"), parallel=3, number=7)

        assert "--parallel" in command
        assert command[command.index("--parallel") + 1] == "3"
        assert "-n" in command
        assert command[command.index("-n") + 1] == "7"
        assert "--dataset" in command
        assert "secret-token" in " ".join(command)
        assert "secret-token" not in " ".join(sanitized)
        assert "Authorization=<redacted>" in " ".join(sanitized)
    finally:
        db.close()


def test_build_evalscope_command_cache_busts_line_by_line_dataset(tmp_path):
    db = _db()
    dataset_path = tmp_path / "prompts.txt"
    dataset_path.write_text("hello\nworld\n", encoding="utf-8")
    try:
        instance = NewApiInstance(
            name="local",
            base_url="http://localhost:3000",
            api_key="secret-token",
            enabled=True,
            is_default=True,
        )
        test = ModelPerformanceTest(
            name="perf",
            model_name="qwen",
            endpoint="/v1/chat/completions",
            dataset_config={"dataset": "line_by_line", "dataset_path": str(dataset_path)},
            load_config={"parallel": [2], "number": 2, "stream": True},
            threshold_config={},
            extra_args={},
            new_api_instance_id=1,
        )
        db.add(instance)
        db.add(test)
        db.commit()
        db.refresh(test)

        command, _ = build_evalscope_command(db, test, tmp_path / "run", parallel=2, number=2, run_id=42)

        generated_path = Path(command[command.index("--dataset-path") + 1])
        lines = generated_path.read_text(encoding="utf-8").splitlines()
        assert generated_path.name == "cache_busted_dataset.txt"
        assert len(lines) == 2
        assert lines[0].startswith("hello [perf_nonce: run=42 parallel=2 item=000001 uuid=")
        assert lines[1].startswith("world [perf_nonce: run=42 parallel=2 item=000002 uuid=")
        assert lines[0] != lines[1]
    finally:
        db.close()


def test_build_evalscope_command_cache_busts_openqa_dataset(tmp_path):
    db = _db()
    dataset_path = tmp_path / "prompts.jsonl"
    dataset_path.write_text(
        '{"question":"What is latency?","answer":"delay"}\n{"question":"What is throughput?"}\n',
        encoding="utf-8",
    )
    try:
        instance = NewApiInstance(
            name="local",
            base_url="http://localhost:3000",
            api_key="secret-token",
            enabled=True,
            is_default=True,
        )
        test = ModelPerformanceTest(
            name="perf",
            model_name="qwen",
            endpoint="/v1/chat/completions",
            dataset_config={"dataset": "openqa", "dataset_path": str(dataset_path)},
            load_config={"parallel": [4], "number": 2, "stream": True},
            threshold_config={},
            extra_args={},
            new_api_instance_id=1,
        )
        db.add(instance)
        db.add(test)
        db.commit()
        db.refresh(test)

        command, _ = build_evalscope_command(db, test, tmp_path / "run", parallel=4, number=2, run_id=99)

        generated_path = Path(command[command.index("--dataset-path") + 1])
        records = [json.loads(line) for line in generated_path.read_text(encoding="utf-8").splitlines()]
        assert generated_path.name == "cache_busted_dataset.jsonl"
        assert records[0]["question"].startswith("What is latency?")
        assert "[perf_nonce: run=99 parallel=4 item=000001 uuid=" in records[0]["question"]
        assert records[0]["answer"] == "delay"
        assert records[1]["question"].startswith("What is throughput?")
        assert records[0]["question"] != records[1]["question"]
    finally:
        db.close()


def test_build_evalscope_command_can_disable_cache_busting(tmp_path):
    db = _db()
    dataset_path = tmp_path / "prompts.txt"
    dataset_path.write_text("hello\n", encoding="utf-8")
    try:
        instance = NewApiInstance(
            name="local",
            base_url="http://localhost:3000",
            api_key="secret-token",
            enabled=True,
            is_default=True,
        )
        test = ModelPerformanceTest(
            name="perf",
            model_name="qwen",
            endpoint="/v1/chat/completions",
            dataset_config={
                "dataset": "line_by_line",
                "dataset_path": str(dataset_path),
                "cache_busting_enabled": False,
            },
            load_config={"parallel": [1], "number": 1, "stream": True},
            threshold_config={},
            extra_args={},
            new_api_instance_id=1,
        )
        db.add(instance)
        db.add(test)
        db.commit()
        db.refresh(test)

        command, _ = build_evalscope_command(db, test, tmp_path / "run", parallel=1, number=1, run_id=1)

        assert command[command.index("--dataset-path") + 1] == str(dataset_path)
        assert not (tmp_path / "run" / "cache_busted_dataset.txt").exists()
    finally:
        db.close()


def test_read_run_log_uses_offset(tmp_path):
    log_path = tmp_path / "benchmark.log"
    log_path.write_text("line1\nline2\n", encoding="utf-8")
    run = ModelPerformanceRun(
        test_id=1,
        status="running",
        duration_ms=0,
        log_path=str(log_path),
        command=[],
        summary={},
        chart_data={},
        analysis={},
    )

    first = read_run_log(run, 0)
    second = read_run_log(run, first["next_offset"])

    assert first["content"] == "line1\nline2\n"
    assert second["content"] == ""
    assert second["done"] is False


def test_read_run_log_falls_back_to_output_dir_and_redacts_secret(tmp_path):
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    (output_dir / "benchmark.log").write_text(
        'headers={"Authorization": "Bearer secret-token"}\nAuthorization=Bearer another-secret\n',
        encoding="utf-8",
    )
    run = ModelPerformanceRun(
        test_id=1,
        status="success",
        duration_ms=0,
        output_dir=str(output_dir),
        log_path=None,
        command=[],
        summary={},
        chart_data={},
        analysis={},
    )

    log = read_run_log(run, 0)

    assert "secret-token" not in log["content"]
    assert "another-secret" not in log["content"]
    assert "Bearer <redacted>" in log["content"]
    assert log["done"] is True


def test_evalscope_failure_message_extracts_http_error_and_redacts_secret(tmp_path):
    log_path = tmp_path / "benchmark.log"
    log_path.write_text(
        """
        2026-05-21 - evalscope - INFO: Starting benchmark
        2026-05-21 - evalscope - INFO: {"headers": {"Authorization": "Bearer secret-token"}}
        2026-05-21 - evalscope - ERROR: Non-retryable error (HTTP 403): {"error": {"message": "预扣费额度失败, 用户剩余额度: $0.15, 需要预扣费额度: $0.41", "code": "insufficient_user_quota"}}. Please check your --url and --api settings.
        """,
        encoding="utf-8",
    )

    message = _evalscope_failure_message(log_path, 1)

    assert message == "EvalScope HTTP 403: 预扣费额度失败, 用户剩余额度: $0.15, 需要预扣费额度: $0.41 (insufficient_user_quota)"
    assert "secret-token" not in message


def test_analyze_evalscope_output_extracts_chart_data(tmp_path):
    log_path = tmp_path / "benchmark.log"
    log_path.write_text(
        """
        === parallel 1, number 10 ===
        throughput: 3.5
        p95 latency: 900
        p99 latency: 1200
        error rate: 0%
        tokens/s: 42
        === parallel 4, number 10 ===
        throughput: 9.5
        p95 latency: 3200
        p99 latency: 4800
        error rate: 2%
        tokens/s: 90
        """,
        encoding="utf-8",
    )

    summary, chart_data, analysis = analyze_evalscope_output(
        tmp_path,
        {"max_error_rate": 0.01, "max_p95_latency_ms": 5000},
    )

    assert summary["best_parallel"] == 4
    assert chart_data["x_axis"] == [1, 4]
    assert chart_data["throughput"] == [3.5, 9.5]
    assert chart_data["error_rate"] == [0.0, 0.02]
    assert analysis["recommended_parallel"] == 1


def test_analyze_evalscope_output_builds_professional_report_metrics(tmp_path):
    run_dir = tmp_path / "parallel_4"
    run_dir.mkdir()
    (run_dir / "benchmark_summary.json").write_text(
        """
        {
          "Total Requests": 20,
          "Success Requests": 19,
          "Failed Requests": 1,
          "Concurrency": 4,
          "Test Duration (s)": 10,
          "Req Throughput (req/s)": 2,
          "Avg Latency (s)": 1.2,
          "TTFT (ms)": 450,
          "TPOT (ms)": 35,
          "Avg Input Tokens": 100,
          "Avg Output Tokens": 200,
          "Output Throughput (tok/s)": 380,
          "Total Throughput (tok/s)": 570
        }
        """,
        encoding="utf-8",
    )
    (run_dir / "benchmark_percentile.json").write_text(
        """
        [
          {"Percentiles": "50%", "Latency (s)": 1.0, "TTFT (ms)": 400, "TPOT (ms)": 30},
          {"Percentiles": "90%", "Latency (s)": 1.8, "TTFT (ms)": 700, "TPOT (ms)": 45},
          {"Percentiles": "95%", "Latency (s)": 2.0, "TTFT (ms)": 900, "TPOT (ms)": 50},
          {"Percentiles": "99%", "Latency (s)": 3.0, "TTFT (ms)": 1200, "TPOT (ms)": 70}
        ]
        """,
        encoding="utf-8",
    )

    summary, chart_data, analysis = analyze_evalscope_output(
        tmp_path,
        {
            "max_error_rate": 0.1,
            "max_p95_latency_ms": 2500,
            "max_p99_latency_ms": 3500,
            "max_ttft_ms": 1000,
            "min_throughput": 1,
            "input_token_price_per_1k": 0.001,
            "output_token_price_per_1k": 0.002,
        },
    )

    point = chart_data["points"][0]
    assert point["success_rate"] == 0.95
    assert point["p99_latency_ms"] == 3000
    assert point["ttft_p95_ms"] == 900
    assert point["input_tokens"] == 2000
    assert point["output_tokens"] == 4000
    assert point["estimated_cost"] == 0.01
    assert summary["success_rate"] == 0.95
    assert summary["estimated_cost"] == 0.01
    assert analysis["passed"] is True
    assert analysis["recommended_parallel"] == 4
    assert analysis["safe_parallel_range"] == [4, 4]
    assert {item["metric"] for item in analysis["sla_checks"]} >= {"max_error_rate", "p99_latency_ms", "ttft_ms"}


def test_create_model_performance_run_defaults():
    db = _db()
    try:
        test = ModelPerformanceTest(
            name="perf",
            model_name="qwen",
            endpoint="/v1/chat/completions",
            dataset_config={},
            load_config={},
            threshold_config={},
            extra_args={},
        )
        db.add(test)
        db.commit()
        db.refresh(test)

        run = create_model_performance_run(db, test)

        assert run.status == "pending"
        assert run.test_id == test.id
        assert run.summary == {}
        assert run.chart_data == {}
    finally:
        db.close()


def test_cancel_model_performance_run_marks_running_run_cancelled():
    db = _db()
    try:
        test = ModelPerformanceTest(
            name="perf",
            model_name="qwen",
            endpoint="/v1/chat/completions",
            dataset_config={},
            load_config={},
            threshold_config={},
            extra_args={},
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        run = create_model_performance_run(db, test)
        run.status = "running"
        db.commit()

        cancelled = cancel_model_performance_run(db, run)

        assert cancelled is True
        assert run.status == "cancelled"
        assert run.finished_at is not None
        assert run.error == "Run cancelled by user"
    finally:
        db.close()


def test_cancel_model_performance_run_rejects_finished_run():
    db = _db()
    try:
        run = ModelPerformanceRun(
            test_id=1,
            status="success",
            duration_ms=0,
            command=[],
            summary={},
            chart_data={},
            analysis={},
        )

        assert cancel_model_performance_run(db, run) is False
        assert run.status == "success"
    finally:
        db.close()


def test_model_performance_dataset_upload_list_and_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(model_performance_datasets, "dataset_storage_dir", lambda: tmp_path)
    upload = UploadFile(
        filename="business.jsonl",
        file=BytesIO(
            b'{"question":"What is the refund policy?"}\n'
            b'{"question":"How do I reset my password?"}\n'
        ),
    )

    saved = model_performance_datasets.save_performance_dataset(
        file=upload,
        name="business-faq",
        dataset="openqa",
        description="Business FAQ",
    )
    datasets = model_performance_datasets.list_performance_datasets()
    preview = model_performance_datasets.preview_performance_dataset("business-faq")

    assert saved.item_count == 2
    assert any(item.name == "business-faq" for item in datasets)
    assert preview is not None
    assert preview.preview == ["What is the refund policy?", "How do I reset my password?"]


def test_builtin_long_output_short_input_dataset_is_available():
    datasets = model_performance_datasets.list_performance_datasets()
    dataset = next((item for item in datasets if item.name == "内置短输入长输出集"), None)

    assert dataset is not None
    assert dataset.dataset == "line_by_line"
    assert dataset.item_count >= 8
    assert dataset.preview
    assert "3000到4000 token" in dataset.preview[0]


def test_builtin_evalscope_hc3_openqa_dataset_is_available():
    datasets = model_performance_datasets.list_performance_datasets()
    dataset = next((item for item in datasets if item.name == "EvalScope 官方 HC3 中文问答集"), None)

    assert dataset is not None
    assert dataset.dataset == "openqa"
    assert dataset.source == "builtin"
    assert dataset.item_count >= 3000
    assert dataset.preview


def test_builtin_code_agent_workload_dataset_is_available():
    datasets = model_performance_datasets.list_performance_datasets()
    dataset = next((item for item in datasets if item.name == "代码开发代理压测集"), None)

    assert dataset is not None
    assert dataset.dataset == "line_by_line"
    assert dataset.source == "builtin"
    assert dataset.item_count >= 20
    assert "代码开发代理" in dataset.preview[0]


def test_builtin_swe_bench_verified_prompt_dataset_is_available():
    datasets = model_performance_datasets.list_performance_datasets()
    dataset = next((item for item in datasets if item.name == "SWE-bench Verified Prompt 压测集"), None)

    assert dataset is not None
    assert dataset.dataset == "line_by_line"
    assert dataset.source == "builtin"
    assert dataset.item_count == 500
    assert "SWE-bench Verified" in dataset.preview[0]
    assert "Issue:" in dataset.preview[0]


def test_builtin_public_sample_datasets_are_available():
    datasets = {item.name: item for item in model_performance_datasets.list_performance_datasets()}
    expected_counts = {
        "公开 GSM8K 数学推理抽样集": 100,
        "公开 TruthfulQA 真实性问答抽样集": 200,
        "公开 MMLU 学科选择题抽样集": 200,
        "公开 WildChat 真实聊天抽样集": 100,
        "公开 CNN/DailyMail 长文摘要抽样集": 50,
        "公开 XSum 新闻摘要抽样集": 100,
    }

    for name, count in expected_counts.items():
        dataset = datasets.get(name)
        assert dataset is not None
        assert dataset.dataset == "line_by_line"
        assert dataset.source == "builtin"
        assert dataset.item_count == count
        assert dataset.preview


def test_validate_comparison_items_requires_two_to_five_models():
    try:
        validate_comparison_items([object()])
        raise AssertionError("expected validation error")
    except ValueError as exc:
        assert "2 to 5" in str(exc)

    validate_comparison_items([object(), object()])


def test_build_comparison_report_ranks_models_and_calculates_deltas():
    db = _db()
    try:
        comparison = ModelPerformanceComparison(
            name="compare",
            enabled=True,
            status="running",
            duration_ms=0,
            dataset_config={},
            load_config={},
            threshold_config={},
            extra_args={},
            summary={},
            chart_data={},
            analysis={},
        )
        db.add(comparison)
        db.commit()
        db.refresh(comparison)
        item_a = ModelPerformanceComparisonItem(
            comparison_id=comparison.id,
            display_name="model-a",
            model_name="a",
            endpoint="/v1/chat/completions",
            sort_order=0,
            status="success",
        )
        item_b = ModelPerformanceComparisonItem(
            comparison_id=comparison.id,
            display_name="model-b",
            model_name="b",
            endpoint="/v1/chat/completions",
            sort_order=1,
            status="success",
        )
        db.add_all([item_a, item_b])
        db.commit()
        test_a = ModelPerformanceTest(
            name="a",
            model_name="a",
            endpoint="/v1/chat/completions",
            dataset_config={},
            load_config={},
            threshold_config={},
            extra_args={},
        )
        test_b = ModelPerformanceTest(
            name="b",
            model_name="b",
            endpoint="/v1/chat/completions",
            dataset_config={},
            load_config={},
            threshold_config={},
            extra_args={},
        )
        db.add_all([test_a, test_b])
        db.commit()
        run_a = ModelPerformanceRun(
            test_id=test_a.id,
            status="success",
            duration_ms=1000,
            command=[],
            summary={"best_throughput": 10, "best_p95_latency_s": 1.0, "max_error_rate": 0.0, "estimated_cost": 0.2},
            chart_data={"points": [{"parallel": 1, "throughput": 10}]},
            analysis={"passed": True, "recommended_parallel": 1},
        )
        run_b = ModelPerformanceRun(
            test_id=test_b.id,
            status="success",
            duration_ms=1000,
            command=[],
            summary={"best_throughput": 20, "best_p95_latency_s": 1.5, "max_error_rate": 0.0, "estimated_cost": 0.3},
            chart_data={"points": [{"parallel": 1, "throughput": 20}]},
            analysis={"passed": True, "recommended_parallel": 1},
        )
        db.add_all([run_a, run_b])
        db.commit()
        item_a.run_id = run_a.id
        item_b.run_id = run_b.id
        db.commit()
        db.refresh(comparison)

        summary, chart_data, analysis = build_comparison_report(db, comparison)

        assert summary["winner_model"] == "model-b"
        assert summary["best_throughput_model"] == "model-b"
        assert chart_data["models"] == ["model-b", "model-a"]
        assert analysis["metric_deltas"]["model-a"]["throughput_pct"] == -50.0
        assert analysis["evaluator_status"] == "not_started"
    finally:
        db.close()


def test_read_comparison_log_includes_child_run_log_from_output_dir(tmp_path):
    db = _db()
    try:
        output_dir = tmp_path / "run"
        output_dir.mkdir()
        (output_dir / "benchmark.log").write_text(
            "Benchmarking summary:\nTotal / Success / Failed  2 / 2 / 0\n",
            encoding="utf-8",
        )
        comparison = ModelPerformanceComparison(
            name="compare",
            enabled=True,
            status="running",
            duration_ms=0,
            dataset_config={},
            load_config={},
            threshold_config={},
            extra_args={},
            summary={},
            chart_data={},
            analysis={},
        )
        test = ModelPerformanceTest(
            name="a",
            model_name="a",
            endpoint="/v1/chat/completions",
            dataset_config={},
            load_config={},
            threshold_config={},
            extra_args={},
        )
        db.add_all([comparison, test])
        db.commit()
        run = ModelPerformanceRun(
            test_id=test.id,
            status="success",
            duration_ms=1000,
            output_dir=str(output_dir),
            log_path=None,
            command=[],
            summary={},
            chart_data={},
            analysis={},
        )
        db.add(run)
        db.commit()
        item = ModelPerformanceComparisonItem(
            comparison_id=comparison.id,
            display_name="model-a",
            model_name="a",
            endpoint="/v1/chat/completions",
            sort_order=0,
            status="success",
            run_id=run.id,
        )
        db.add(item)
        db.commit()

        log = read_comparison_log(db, comparison)

        assert "[model-a] model=a status=success" in log["content"]
        assert "run_log_tail_last_" in log["content"]
        assert "Benchmarking summary" in log["content"]
        assert "Total / Success / Failed  2 / 2 / 0" in log["content"]
        assert log["done"] is False
    finally:
        db.close()
