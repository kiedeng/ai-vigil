from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time
from typing import Any

from sqlalchemy.orm import Session

from ..config import PROJECT_ROOT, get_settings
from ..database import SessionLocal
from ..models import ModelPerformanceRun, ModelPerformanceTest
from .new_api_instances import resolve_instance


DEFAULT_DATASET = PROJECT_ROOT / "backend" / "app" / "datasets" / "evalscope_openqa_zh.jsonl"
SENSITIVE_HEADER_NAMES = {"authorization", "api-key", "x-api-key"}
EVALSCOPE_MISSING_MESSAGE = (
    "EvalScope is not installed or not on PATH. Install it in the backend environment with: "
    "pip install 'evalscope[perf]==1.7.0'"
)


def _as_int_list(value: Any, default: list[int]) -> list[int]:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
        return [int(item) for item in parts if item]
    if isinstance(value, list):
        return [int(item) for item in value]
    return default


def _default_dataset_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = {"dataset": "openqa", "dataset_path": str(DEFAULT_DATASET)}
    merged.update(config or {})
    return merged


def _default_load_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "parallel": [1, 2, 4],
        "number": 20,
        "read_timeout": 120,
        "connect_timeout": 30,
        "max_tokens": 128,
        "max_prompt_length": 128000,
        "log_every_n_query": 5,
        "stream": True,
    }
    merged.update(config or {})
    return merged


def _flag_name(key: str) -> str:
    return "--" + key.replace("_", "-")


def _add_optional_arg(command: list[str], flag: str, value: Any) -> None:
    if value is None or value == "":
        return
    if isinstance(value, bool):
        if value:
            command.append(flag)
        return
    command.extend([flag, str(value)])


def _sanitize_header(header: str) -> str:
    key = header.split("=", 1)[0].strip().lower()
    if key in SENSITIVE_HEADER_NAMES:
        return f"{header.split('=', 1)[0]}=<redacted>"
    if key == "authorization":
        return "Authorization=<redacted>"
    return header


def sanitize_command(command: list[str]) -> list[str]:
    sanitized: list[str] = []
    mask_next_headers = False
    for item in command:
        if item == "--headers":
            sanitized.append(item)
            mask_next_headers = True
            continue
        if item.startswith("--") and item != "--headers":
            mask_next_headers = False
        sanitized.append(_sanitize_header(item) if mask_next_headers and "=" in item else item)
    return sanitized


def _evalscope_command_prefix() -> list[str]:
    executable = shutil.which("evalscope")
    if executable:
        return [executable]
    sibling = Path(sys.executable).resolve().parent / "evalscope"
    if sibling.exists():
        return [str(sibling)]
    raise FileNotFoundError(EVALSCOPE_MISSING_MESSAGE)


def build_evalscope_command(
    db: Session,
    test: ModelPerformanceTest,
    output_dir: Path,
    parallel: int | None = None,
    number: int | None = None,
) -> tuple[list[str], list[str]]:
    instance = resolve_instance(db, test.new_api_instance_id)
    endpoint = test.endpoint or "/v1/chat/completions"
    url = f"{instance.base_url.rstrip('/')}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
    dataset_config = _default_dataset_config(test.dataset_config)
    load_config = _default_load_config(test.load_config)
    dataset_path = Path(str(dataset_config.get("dataset_path") or DEFAULT_DATASET)).expanduser()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    command = [
        *_evalscope_command_prefix(),
        "perf",
        "--url",
        url,
        "--parallel",
        str(parallel or _as_int_list(load_config.get("parallel"), [1])[0]),
        "--model",
        test.model_name,
        "--log-every-n-query",
        str(load_config.get("log_every_n_query", 5)),
        "--read-timeout",
        str(load_config.get("read_timeout", 120)),
        "--connect-timeout",
        str(load_config.get("connect_timeout", 30)),
        "-n",
        str(number or load_config.get("number", 20)),
        "--max-prompt-length",
        str(load_config.get("max_prompt_length", 128000)),
        "--max-tokens",
        str(load_config.get("max_tokens", 128)),
        "--api",
        str(load_config.get("api", "openai")),
        "--dataset",
        str(dataset_config.get("dataset", "openqa")),
        "--dataset-path",
        str(dataset_path),
        "--name",
        f"model_perf_run_{output_dir.name}",
    ]
    if load_config.get("stream", True):
        command.append("--stream")

    headers: list[str] = []
    if instance.api_key:
        headers.append(f"Authorization=Bearer {instance.api_key}")
    for key, value in (test.extra_args or {}).get("headers", {}).items():
        headers.append(f"{key}={value}")
    if headers:
        command.append("--headers")
        command.extend(headers)

    for key, value in (test.extra_args or {}).items():
        if key in {"headers", "extra_cli_args"}:
            continue
        _add_optional_arg(command, _flag_name(key), value)
    for item in (test.extra_args or {}).get("extra_cli_args", []):
        command.append(str(item))

    return command, sanitize_command(command)


def create_model_performance_run(db: Session, test: ModelPerformanceTest) -> ModelPerformanceRun:
    run = ModelPerformanceRun(
        test_id=test.id,
        status="pending",
        duration_ms=0,
        command=[],
        summary={},
        chart_data={},
        analysis={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


async def execute_model_performance_run(run_id: int) -> None:
    db = SessionLocal()
    try:
        run = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == run_id).first()
        if not run:
            return
        test = db.query(ModelPerformanceTest).filter(ModelPerformanceTest.id == run.test_id).first()
        if not test:
            run.status = "failure"
            run.error = "Model performance test not found"
            db.commit()
            return

        storage_dir = Path(get_settings().model_performance_storage_dir)
        run_dir = storage_dir / str(run.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "benchmark.log"
        load_config = _default_load_config(test.load_config)
        parallels = _as_int_list(load_config.get("parallel"), [1])
        numbers = _as_int_list(load_config.get("number"), [20])
        command, sanitized = build_evalscope_command(db, test, run_dir, parallels[0], numbers[0])
        run.status = "running"
        run.started_at = datetime.utcnow()
        run.output_dir = str(run_dir)
        run.log_path = str(log_path)
        run.command = sanitized
        db.commit()

        started = time.perf_counter()
        return_code = 0
        with log_path.open("w", encoding="utf-8") as log_file:
            for index, parallel in enumerate(parallels):
                number = numbers[index] if len(numbers) > index else numbers[-1]
                parallel_dir = run_dir / f"parallel_{parallel}"
                parallel_dir.mkdir(parents=True, exist_ok=True)
                command, sanitized = build_evalscope_command(db, test, parallel_dir, parallel, number)
                log_file.write(f"\n=== parallel {parallel}, number {number} ===\n")
                log_file.write("Command: " + " ".join(sanitized) + "\n\n")
                log_file.flush()
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=str(parallel_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                assert process.stdout is not None
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    log_file.write(line.decode("utf-8", errors="replace"))
                    log_file.flush()
                code = await process.wait()
                if code != 0:
                    return_code = code
                    break

        duration_ms = int((time.perf_counter() - started) * 1000)
        summary, chart_data, analysis = analyze_evalscope_output(run_dir, test.threshold_config or {})
        run.duration_ms = duration_ms
        run.finished_at = datetime.utcnow()
        run.summary = summary
        run.chart_data = chart_data
        run.analysis = analysis
        run.status = "success" if return_code == 0 else "failure"
        if return_code != 0:
            run.error = f"evalscope exited with code {return_code}"
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "chart_data.json").write_text(json.dumps(chart_data, ensure_ascii=False, indent=2), encoding="utf-8")
        db.commit()
    except Exception as exc:
        run = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == run_id).first()
        if run:
            run.status = "failure"
            run.finished_at = datetime.utcnow()
            run.error = str(exc)
            db.commit()
    finally:
        db.close()


def read_run_log(run: ModelPerformanceRun, offset: int = 0) -> dict[str, Any]:
    path = Path(run.log_path or "")
    if not path.exists():
        return {"content": "", "next_offset": 0, "done": run.status not in {"pending", "running"}}
    with path.open("rb") as handle:
        handle.seek(max(offset, 0))
        data = handle.read()
        next_offset = handle.tell()
    return {
        "content": data.decode("utf-8", errors="replace"),
        "next_offset": next_offset,
        "done": run.status not in {"pending", "running"},
    }


def analyze_evalscope_output(output_dir: Path, threshold_config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    points = _extract_points_from_json(output_dir)
    text = _read_output_text(output_dir)
    if not points:
        points = _extract_points_from_text(text)
    sqlite_summary = _summarize_sqlite_results(output_dir)
    if sqlite_summary and not points:
        points = [sqlite_summary]

    summary = _summary_from_points(points, sqlite_summary)
    chart_data = {
        "points": points,
        "x_axis": [point.get("parallel") for point in points],
        "throughput": [point.get("throughput") for point in points],
        "error_rate": [point.get("error_rate") for point in points],
        "avg_latency_ms": [point.get("avg_latency_ms") for point in points],
        "p95_latency_ms": [point.get("p95_latency_ms") for point in points],
        "p99_latency_ms": [point.get("p99_latency_ms") for point in points],
        "tokens_per_second": [point.get("tokens_per_second") for point in points],
        "total_tokens_per_second": [point.get("total_tokens_per_second") for point in points],
        "ttft_ms": [point.get("ttft_ms") for point in points],
        "tpot_ms": [point.get("tpot_ms") for point in points],
    }
    analysis = _build_analysis(points, summary, threshold_config)
    return summary, chart_data, analysis


def _json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _percentile_value(items: Any, percentile: str, key: str) -> float | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and str(item.get("Percentiles")) == percentile:
            value = item.get(key)
            return float(value) if value is not None else None
    return None


def _extract_points_from_json(output_dir: Path) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for summary_path in sorted(output_dir.rglob("benchmark_summary.json")):
        summary = _json_file(summary_path)
        if not isinstance(summary, dict):
            continue
        percentiles = _json_file(summary_path.with_name("benchmark_percentile.json"))
        total = int(summary.get("Total Requests") or 0)
        failed = int(summary.get("Failed Requests") or 0)
        concurrency = int(summary.get("Concurrency") or 0)
        point = {
            "parallel": concurrency,
            "total_requests": total,
            "success_requests": int(summary.get("Success Requests") or 0),
            "failed_requests": failed,
            "error_rate": round(failed / total, 4) if total else None,
            "test_duration_s": summary.get("Test Duration (s)"),
            "throughput": summary.get("Req Throughput (req/s)"),
            "avg_latency_s": summary.get("Avg Latency (s)"),
            "avg_latency_ms": round(float(summary["Avg Latency (s)"]) * 1000, 2) if summary.get("Avg Latency (s)") is not None else None,
            "p50_latency_s": _percentile_value(percentiles, "50%", "Latency (s)"),
            "p90_latency_s": _percentile_value(percentiles, "90%", "Latency (s)"),
            "p95_latency_s": _percentile_value(percentiles, "95%", "Latency (s)"),
            "p99_latency_s": _percentile_value(percentiles, "99%", "Latency (s)"),
            "p50_latency_ms": _seconds_to_ms(_percentile_value(percentiles, "50%", "Latency (s)")),
            "p90_latency_ms": _seconds_to_ms(_percentile_value(percentiles, "90%", "Latency (s)")),
            "p95_latency_ms": _seconds_to_ms(_percentile_value(percentiles, "95%", "Latency (s)")),
            "p99_latency_ms": _seconds_to_ms(_percentile_value(percentiles, "99%", "Latency (s)")),
            "ttft_ms": summary.get("TTFT (ms)"),
            "ttft_p95_ms": _percentile_value(percentiles, "95%", "TTFT (ms)"),
            "tpot_ms": summary.get("TPOT (ms)"),
            "tpot_p95_ms": _percentile_value(percentiles, "95%", "TPOT (ms)"),
            "itl_ms": summary.get("ITL (ms)"),
            "avg_input_tokens": summary.get("Avg Input Tokens"),
            "avg_output_tokens": summary.get("Avg Output Tokens"),
            "tokens_per_second": summary.get("Output Throughput (tok/s)"),
            "total_tokens_per_second": summary.get("Total Throughput (tok/s)"),
            "decode_tokens_per_second": _percentile_value(percentiles, "50%", "Decode (tok/s)"),
        }
        points.append(point)
    return sorted(points, key=lambda item: item.get("parallel") or 0)


def _seconds_to_ms(value: float | None) -> float | None:
    return round(value * 1000, 2) if value is not None else None


def _read_output_text(output_dir: Path) -> str:
    chunks: list[str] = []
    for path in output_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {"", ".log", ".txt", ".md", ".json"}:
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(chunks)


def _first_number(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return float(match.group(1))
    return None


def _extract_points_from_text(text: str) -> list[dict[str, Any]]:
    points: dict[int, dict[str, Any]] = {}
    blocks = re.split(r"\n(?=.*?(?:parallel|concurrency|并发)\D+\d+)", text, flags=re.I)
    for block in blocks:
        parallel = _first_number(block, [r"(?:parallel|concurrency|并发)\D+(\d+)"])
        if parallel is None:
            continue
        item = points.setdefault(int(parallel), {"parallel": int(parallel)})
        item["throughput"] = _first_number(block, [r"(?:qps|throughput|吞吐)\D+([0-9.]+)"])
        item["error_rate"] = _normalize_rate(_first_number(block, [r"(?:error rate|failed rate|失败率|错误率)\D+([0-9.]+)\s*%?"]))
        item["avg_latency_ms"] = _first_number(block, [r"(?:avg.*?latency|average.*?latency|平均延迟)\D+([0-9.]+)"])
        item["p50_latency_ms"] = _first_number(block, [r"(?:p50|50%).*?(?:latency|延迟)?\D+([0-9.]+)"])
        item["p90_latency_ms"] = _first_number(block, [r"(?:p90|90%).*?(?:latency|延迟)?\D+([0-9.]+)"])
        item["p95_latency_ms"] = _first_number(block, [r"(?:p95|95%).*?(?:latency|延迟)?\D+([0-9.]+)"])
        item["p99_latency_ms"] = _first_number(block, [r"(?:p99|99%).*?(?:latency|延迟)?\D+([0-9.]+)"])
        item["tokens_per_second"] = _first_number(block, [r"(?:tokens/s|token/s|output token.*?throughput)\D+([0-9.]+)"])
    return [points[key] for key in sorted(points)]


def _normalize_rate(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100 if value > 1 else value


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return round(ordered[index], 2)


def _summarize_sqlite_results(output_dir: Path) -> dict[str, Any] | None:
    db_files = list(output_dir.rglob("*.db")) + list(output_dir.rglob("*.sqlite"))
    for db_file in db_files:
        try:
            with sqlite3.connect(db_file) as con:
                tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                if "result" not in tables:
                    continue
                columns = [row[1] for row in con.execute("PRAGMA table_info(result)")]
                rows = con.execute("SELECT * FROM result").fetchall()
                if not rows:
                    continue
                dict_rows = [dict(zip(columns, row, strict=False)) for row in rows]
                success_count = sum(1 for row in dict_rows if str(row.get("success")).lower() in {"true", "1"})
                total = len(dict_rows)
                latencies = [
                    float(row[key])
                    for row in dict_rows
                    for key in ("latency", "duration", "elapsed", "rt")
                    if key in row and row[key] is not None
                ]
                return {
                    "parallel": None,
                    "total_requests": total,
                    "success_requests": success_count,
                    "failed_requests": total - success_count,
                    "error_rate": round((total - success_count) / total, 4),
                    "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
                    "p50_latency_ms": _percentile(latencies, 0.50),
                    "p90_latency_ms": _percentile(latencies, 0.90),
                    "p95_latency_ms": _percentile(latencies, 0.95),
                    "p99_latency_ms": _percentile(latencies, 0.99),
                }
        except (sqlite3.Error, OSError, ValueError):
            continue
    return None


def _summary_from_points(points: list[dict[str, Any]], sqlite_summary: dict[str, Any] | None) -> dict[str, Any]:
    best = max(points, key=lambda item: item.get("throughput") or 0, default={})
    worst_error = max((item.get("error_rate") or 0 for item in points), default=0)
    total_requests = sum(int(item.get("total_requests") or 0) for item in points) or None
    success_requests = sum(int(item.get("success_requests") or 0) for item in points) or None
    failed_sum = sum(int(item.get("failed_requests") or 0) for item in points)
    failed_requests = failed_sum if points else None
    summary = {
        "total_requests": total_requests or (sqlite_summary.get("total_requests") if sqlite_summary else None),
        "success_requests": success_requests or (sqlite_summary.get("success_requests") if sqlite_summary else None),
        "failed_requests": failed_requests if failed_requests is not None else (sqlite_summary.get("failed_requests") if sqlite_summary else None),
        "best_parallel": best.get("parallel"),
        "best_throughput": best.get("throughput"),
        "best_output_throughput": best.get("tokens_per_second"),
        "best_total_throughput": best.get("total_tokens_per_second"),
        "best_avg_latency_s": best.get("avg_latency_s"),
        "best_p95_latency_s": best.get("p95_latency_s"),
        "max_error_rate": round(worst_error, 4),
        "points_count": len(points),
    }
    if sqlite_summary and not points:
        summary.update({key: value for key, value in sqlite_summary.items() if key not in {"parallel"}})
    return summary


def _build_analysis(points: list[dict[str, Any]], summary: dict[str, Any], threshold_config: dict[str, Any]) -> dict[str, Any]:
    max_error_rate = float(threshold_config.get("max_error_rate", 0.01))
    max_p95 = threshold_config.get("max_p95_latency_ms")
    candidates = []
    for point in points:
        error_ok = (point.get("error_rate") or 0) <= max_error_rate
        latency_ok = max_p95 is None or point.get("p95_latency_ms") is None or point.get("p95_latency_ms") <= float(max_p95)
        if error_ok and latency_ok:
            candidates.append(point)
    recommended = max(candidates, key=lambda item: item.get("parallel") or 0, default=None)
    passed = bool(recommended) and (summary.get("max_error_rate") or 0) <= max_error_rate
    if max_p95 is not None:
        passed = passed and all(
            item.get("p95_latency_ms") is None or item.get("p95_latency_ms") <= float(max_p95) for item in points
        )
    best_latency = min(
        (item for item in points if item.get("avg_latency_s") is not None),
        key=lambda item: item.get("avg_latency_s") or float("inf"),
        default=None,
    )
    return {
        "passed": passed,
        "recommended_parallel": recommended.get("parallel") if recommended else None,
        "recommendation": (
            f"建议使用并发 {recommended.get('parallel')}，该点满足错误率和延迟阈值。"
            if recommended
            else "没有找到同时满足错误率和延迟阈值的并发点，建议降低并发或扩容后重测。"
        ),
        "thresholds": {"max_error_rate": max_error_rate, "max_p95_latency_ms": max_p95},
        "best_throughput_parallel": summary.get("best_parallel"),
        "best_throughput": summary.get("best_throughput"),
        "best_latency_parallel": best_latency.get("parallel") if best_latency else None,
        "best_avg_latency_s": best_latency.get("avg_latency_s") if best_latency else None,
    }
