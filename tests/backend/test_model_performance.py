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
