from pathlib import Path
from io import BytesIO

from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import ModelPerformanceRun, ModelPerformanceTest, NewApiInstance
from backend.app.services.model_performance import (
    analyze_evalscope_output,
    build_evalscope_command,
    create_model_performance_run,
    read_run_log,
)
from backend.app.services import model_performance_datasets


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
