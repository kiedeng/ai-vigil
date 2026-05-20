from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session, selectinload

from ..database import SessionLocal
from ..models import (
    ModelPerformanceComparison,
    ModelPerformanceComparisonItem,
    ModelPerformanceRun,
    ModelPerformanceTest,
)
from .model_performance import (
    LOG_TAIL_CHARS,
    cancel_model_performance_run,
    create_model_performance_run,
    execute_model_performance_run,
    read_run_log,
)
from .new_api_instances import auth_headers, resolve_instance
from .settings import effective_settings


COMPARISON_CHILD_MARKER = "_comparison_child"


def validate_comparison_items(items: list[Any]) -> None:
    if not 2 <= len(items) <= 5:
        raise ValueError("comparison items must contain 2 to 5 models")


def create_comparison(db: Session, payload: Any) -> ModelPerformanceComparison:
    items = list(payload.items)
    validate_comparison_items(items)
    comparison = ModelPerformanceComparison(
        name=payload.name,
        enabled=payload.enabled,
        status="idle",
        duration_ms=0,
        dataset_config=payload.dataset_config,
        load_config=payload.load_config,
        threshold_config=payload.threshold_config,
        extra_args=payload.extra_args,
        summary={},
        chart_data={},
        analysis={},
    )
    db.add(comparison)
    db.flush()
    for index, item in enumerate(items):
        db.add(
            ModelPerformanceComparisonItem(
                comparison_id=comparison.id,
                display_name=item.display_name,
                new_api_instance_id=item.new_api_instance_id,
                model_name=item.model_name,
                endpoint=item.endpoint,
                sort_order=item.sort_order or index,
                status="pending",
            )
        )
    db.commit()
    return get_comparison(db, comparison.id) or comparison


def update_comparison(db: Session, comparison: ModelPerformanceComparison, payload: Any) -> ModelPerformanceComparison:
    data = payload.model_dump(exclude_unset=True)
    items = data.pop("items", None)
    for key, value in data.items():
        setattr(comparison, key, value)
    if items is not None:
        validate_comparison_items(items)
        comparison.items.clear()
        db.flush()
        for index, item in enumerate(items):
            db.add(
                ModelPerformanceComparisonItem(
                    comparison_id=comparison.id,
                    display_name=item["display_name"],
                    new_api_instance_id=item.get("new_api_instance_id"),
                    model_name=item["model_name"],
                    endpoint=item.get("endpoint") or "/v1/chat/completions",
                    sort_order=item.get("sort_order") or index,
                    status="pending",
                )
            )
    comparison.status = "idle"
    comparison.summary = {}
    comparison.chart_data = {}
    comparison.analysis = {}
    comparison.error = None
    db.commit()
    return get_comparison(db, comparison.id) or comparison


def get_comparison(db: Session, comparison_id: int) -> ModelPerformanceComparison | None:
    return (
        db.query(ModelPerformanceComparison)
        .options(selectinload(ModelPerformanceComparison.items))
        .filter(ModelPerformanceComparison.id == comparison_id)
        .first()
    )


def create_comparison_child_test(
    db: Session,
    comparison: ModelPerformanceComparison,
    item: ModelPerformanceComparisonItem,
) -> ModelPerformanceTest:
    test = ModelPerformanceTest(
        name=f"[对比子项] {comparison.name} / {item.display_name}",
        enabled=False,
        new_api_instance_id=item.new_api_instance_id,
        model_name=item.model_name,
        endpoint=item.endpoint,
        dataset_config=dict(comparison.dataset_config or {}),
        load_config=dict(comparison.load_config or {}),
        threshold_config=dict(comparison.threshold_config or {}),
        extra_args={
            **dict(comparison.extra_args or {}),
            COMPARISON_CHILD_MARKER: True,
            "comparison_id": comparison.id,
            "comparison_item_id": item.id,
        },
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    item.test_id = test.id
    db.commit()
    return test


def cancel_comparison(db: Session, comparison: ModelPerformanceComparison) -> bool:
    if comparison.status not in {"pending", "running"}:
        return False
    comparison.status = "cancelled"
    comparison.finished_at = datetime.utcnow()
    comparison.error = "Comparison cancelled by user"
    if comparison.started_at:
        comparison.duration_ms = int((comparison.finished_at - comparison.started_at).total_seconds() * 1000)
    for item in comparison.items:
        if item.run_id:
            run = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == item.run_id).first()
            if run and run.status in {"pending", "running"}:
                cancel_model_performance_run(db, run)
        if item.status in {"pending", "running"}:
            item.status = "cancelled"
            item.error = "Comparison cancelled by user"
    db.commit()
    return True


async def execute_comparison(comparison_id: int) -> None:
    db = SessionLocal()
    started = time.perf_counter()
    try:
        comparison = get_comparison(db, comparison_id)
        if not comparison:
            return
        comparison.status = "running"
        comparison.started_at = datetime.utcnow()
        comparison.finished_at = None
        comparison.duration_ms = 0
        comparison.error = None
        comparison.summary = {}
        comparison.chart_data = {}
        comparison.analysis = {}
        for item in comparison.items:
            item.status = "pending"
            item.error = None
            item.run_id = None
        db.commit()

        for item in sorted(comparison.items, key=lambda row: row.sort_order):
            db.refresh(comparison)
            if comparison.status == "cancelled":
                return
            item.status = "running"
            db.commit()
            test = create_comparison_child_test(db, comparison, item)
            run = create_model_performance_run(db, test)
            item.run_id = run.id
            db.commit()
            await execute_model_performance_run(run.id)
            db.refresh(run)
            db.refresh(item)
            item.status = run.status
            item.error = run.error
            db.commit()

        comparison = get_comparison(db, comparison_id)
        if not comparison or comparison.status == "cancelled":
            return
        summary, chart_data, analysis = build_comparison_report(db, comparison)
        analysis = await add_ai_conclusion(db, summary, chart_data, analysis)
        statuses = [item.status for item in comparison.items]
        comparison.summary = summary
        comparison.chart_data = chart_data
        comparison.analysis = analysis
        comparison.finished_at = datetime.utcnow()
        comparison.duration_ms = int((time.perf_counter() - started) * 1000)
        if all(status == "success" for status in statuses):
            comparison.status = "success"
        elif any(status == "success" for status in statuses):
            comparison.status = "partial_failure"
            comparison.error = "Some comparison models failed"
        else:
            comparison.status = "failure"
            comparison.error = "All comparison models failed"
        db.commit()
    except Exception as exc:
        comparison = get_comparison(db, comparison_id)
        if comparison:
            comparison.status = "failure"
            comparison.finished_at = datetime.utcnow()
            comparison.duration_ms = int((time.perf_counter() - started) * 1000)
            comparison.error = str(exc)
            db.commit()
    finally:
        db.close()


def build_comparison_report(
    db: Session,
    comparison: ModelPerformanceComparison,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for item in sorted(comparison.items, key=lambda row: row.sort_order):
        run = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == item.run_id).first() if item.run_id else None
        if not run or run.status != "success":
            failures.append(
                {
                    "display_name": item.display_name,
                    "model_name": item.model_name,
                    "status": item.status,
                    "error": item.error or (run.error if run else "Run not available"),
                }
            )
            continue
        summary = run.summary or {}
        analysis = run.analysis or {}
        row = {
            "item_id": item.id,
            "run_id": run.id,
            "display_name": item.display_name,
            "model_name": item.model_name,
            "instance_id": item.new_api_instance_id,
            "status": run.status,
            "passed": bool(analysis.get("passed")),
            "recommended_parallel": analysis.get("recommended_parallel"),
            "best_throughput": _num(summary.get("best_throughput")),
            "best_p95_latency_s": _num(summary.get("best_p95_latency_s")),
            "best_p99_latency_s": _num(summary.get("best_p99_latency_s")),
            "best_ttft_ms": _num(summary.get("best_ttft_ms")),
            "best_output_throughput": _num(summary.get("best_output_throughput")),
            "max_error_rate": _num(summary.get("max_error_rate")),
            "estimated_cost": _num(summary.get("estimated_cost")),
            "summary": summary,
            "analysis": analysis,
        }
        row["score"] = _comparison_score(row)
        rows.append(row)

    ranking = sorted(rows, key=lambda row: row["score"], reverse=True)
    baseline = ranking[0] if ranking else None
    for row in ranking:
        row["deltas"] = _metric_deltas(baseline, row)

    winner = ranking[0] if ranking else None
    summary = {
        "winner_model": winner.get("display_name") if winner else None,
        "baseline_model": baseline.get("display_name") if baseline else None,
        "model_count": len(comparison.items),
        "passed_models": [row["display_name"] for row in rows if row["passed"]],
        "ranking": [_public_row(row) for row in ranking],
        "best_throughput_model": _best_name(rows, "best_throughput", reverse=True),
        "best_latency_model": _best_name(rows, "best_p95_latency_s", reverse=False),
        "lowest_cost_model": _best_name(rows, "estimated_cost", reverse=False),
        "failures": failures,
    }
    chart_data = {
        "models": [row["display_name"] for row in ranking],
        "throughput_by_model": [row.get("best_throughput") for row in ranking],
        "latency_by_model": [row.get("best_p95_latency_s") for row in ranking],
        "error_rate_by_model": [row.get("max_error_rate") for row in ranking],
        "cost_by_model": [row.get("estimated_cost") for row in ranking],
        "points_by_model": {
            row["display_name"]: (db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == row["run_id"]).first().chart_data or {}).get("points", [])
            for row in ranking
        },
    }
    analysis = {
        "passed": bool(winner) and any(row["passed"] for row in rows),
        "recommendation": _rule_recommendation(winner, failures),
        "rule_conclusion": _rule_conclusion(ranking, failures),
        "metric_deltas": {row["display_name"]: row["deltas"] for row in ranking},
        "tradeoffs": _tradeoffs(ranking),
        "ai_conclusion": None,
        "evaluator_status": "not_started",
    }
    return summary, chart_data, analysis


async def add_ai_conclusion(
    db: Session,
    summary: dict[str, Any],
    chart_data: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    fallback = _business_conclusion(summary, analysis)
    payload = {
        "summary": summary,
        "chart_data": {key: value for key, value in chart_data.items() if key != "points_by_model"},
        "rule_analysis": {key: value for key, value in analysis.items() if key not in {"ai_conclusion", "evaluator_status"}},
        "fallback_conclusion": fallback,
    }
    enriched = dict(analysis)
    result = await generate_ai_conclusion(db, payload)
    if not _valid_ai_conclusion(result.get("reason")):
        result = {
            **result,
            "status": "fallback_rule_conclusion",
            "reason": fallback,
            "raw_reason": result.get("reason"),
        }
    enriched["evaluator_status"] = result.get("status")
    enriched["ai_conclusion"] = result
    return enriched


async def generate_ai_conclusion(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    settings = effective_settings(db)
    model = str(settings["evaluator_model"])
    instance = resolve_instance(db, None)
    compact_payload = {
        "summary": payload["summary"],
        "chart_data": payload["chart_data"],
        "rule_analysis": payload["rule_analysis"],
    }
    prompt = (
        "你是企业 AI 平台的模型性能评估专家。请只输出中文自然语言结论，不要输出 JSON、Markdown、英文校验语、"
        "提示词评价或格式审查。\n"
        "结论需要面向业务决策，必须覆盖：推荐模型、主要优势、风险或注意事项、适用场景；如果有失败模型，需要说明先排查。"
        "请控制在 180 到 260 个中文字符。\n"
        "只能依据下面的压测数据，不要编造未出现的指标。\n\n"
        f"{json.dumps(compact_payload, ensure_ascii=False, indent=2)}\n\n"
        f"如果无法生成高质量结论，请原样输出这段兜底结论：{payload['fallback_conclusion']}"
    )
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{instance.base_url.rstrip('/')}/v1/chat/completions",
                headers=auth_headers(instance),
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 800,
                },
            )
            response.raise_for_status()
        content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "enabled": True,
            "status": "success",
            "reason": str(content).strip(),
            "model": model,
            "instance_id": instance.id,
            "instance_name": instance.name,
        }
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:1000] if exc.response is not None else ""
        return {
            "enabled": True,
            "status": "evaluator_http_error",
            "reason": f"AI conclusion HTTP error: {exc.response.status_code}; {body}",
            "model": model,
            "instance_id": instance.id,
            "instance_name": instance.name,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "status": "evaluator_error",
            "reason": str(exc),
            "model": model,
            "instance_id": instance.id,
            "instance_name": instance.name,
        }


def read_comparison_log(db: Session, comparison: ModelPerformanceComparison) -> dict[str, Any]:
    db.expire_all()
    comparison = get_comparison(db, comparison.id) or comparison
    lines = [
        f"Comparison #{comparison.id} {comparison.name}",
        f"Status: {comparison.status}",
    ]
    for item in sorted(comparison.items, key=lambda row: row.sort_order):
        run = db.query(ModelPerformanceRun).filter(ModelPerformanceRun.id == item.run_id).first() if item.run_id else None
        status = run.status if run else item.status
        lines.append(f"\n[{item.display_name}] model={item.model_name} status={status} run_id={item.run_id or '-'}")
        if item.error:
            lines.append(f"error={item.error}")
        if run:
            lines.append(f"duration_ms={run.duration_ms} output_dir={run.output_dir or '-'}")
            if run.error and run.error != item.error:
                lines.append(f"run_error={run.error}")
            log_content = str(read_run_log(run, 0).get("content") or "").strip()
            if log_content:
                tail = log_content[-LOG_TAIL_CHARS:]
                lines.append(f"run_log_tail_last_{LOG_TAIL_CHARS}_chars:")
                lines.append(tail)
            else:
                lines.append("run_log_tail: <empty>")
    return {"content": "\n".join(lines) + "\n", "done": comparison.status not in {"pending", "running"}}


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _comparison_score(row: dict[str, Any]) -> float:
    score = 1000 if row.get("passed") else 0
    score += (row.get("best_throughput") or 0) * 10
    score -= (row.get("max_error_rate") or 0) * 10000
    score -= (row.get("best_p95_latency_s") or 0) * 2
    score -= (row.get("estimated_cost") or 0) * 10
    return round(score, 6)


def _metric_deltas(baseline: dict[str, Any] | None, row: dict[str, Any]) -> dict[str, Any]:
    if not baseline:
        return {}
    return {
        "throughput_pct": _pct_delta(baseline.get("best_throughput"), row.get("best_throughput")),
        "p95_latency_pct": _pct_delta(baseline.get("best_p95_latency_s"), row.get("best_p95_latency_s")),
        "error_rate_delta": _delta(baseline.get("max_error_rate"), row.get("max_error_rate")),
        "cost_delta": _delta(baseline.get("estimated_cost"), row.get("estimated_cost")),
    }


def _pct_delta(base: Any, value: Any) -> float | None:
    base_num = _num(base)
    value_num = _num(value)
    if base_num in {None, 0} or value_num is None:
        return None
    return round((value_num - base_num) / base_num * 100, 2)


def _delta(base: Any, value: Any) -> float | None:
    base_num = _num(base)
    value_num = _num(value)
    if base_num is None or value_num is None:
        return None
    return round(value_num - base_num, 6)


def _best_name(rows: list[dict[str, Any]], key: str, reverse: bool) -> str | None:
    available = [row for row in rows if row.get(key) is not None]
    if not available:
        return None
    return sorted(available, key=lambda row: row.get(key) or 0, reverse=reverse)[0]["display_name"]


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"summary", "analysis"}}


def _rule_recommendation(winner: dict[str, Any] | None, failures: list[dict[str, Any]]) -> str:
    if not winner:
        return "没有模型完成可用压测，无法给出推荐。"
    suffix = f"；另有 {len(failures)} 个模型运行失败，需要先排查。" if failures else "。"
    return f"推荐使用 {winner['display_name']}，它在当前规则评分中排名第一{suffix}"


def _rule_conclusion(ranking: list[dict[str, Any]], failures: list[dict[str, Any]]) -> str:
    if not ranking:
        return "所有模型均未产出成功结果。"
    first = ranking[0]
    parts = [
        f"{first['display_name']} 综合排名第一",
        f"最佳吞吐 {first.get('best_throughput')}" if first.get("best_throughput") is not None else "",
        f"P95 {first.get('best_p95_latency_s')}s" if first.get("best_p95_latency_s") is not None else "",
    ]
    if failures:
        parts.append(f"{len(failures)} 个模型失败")
    return "，".join(part for part in parts if part) + "。"


def _business_conclusion(summary: dict[str, Any], analysis: dict[str, Any]) -> str:
    ranking = summary.get("ranking") or []
    failures = summary.get("failures") or []
    if not ranking:
        return "本次对比没有模型产出可用压测结果，暂不建议直接选型。建议先排查失败模型的网关连通性、模型名、超时和错误日志，恢复成功样本后重新运行对比。"

    winner = ranking[0]
    winner_name = winner.get("display_name") or summary.get("winner_model") or "排名第一模型"
    throughput = winner.get("best_throughput")
    p95 = winner.get("best_p95_latency_s")
    error_rate = _num(winner.get("max_error_rate"))
    passed = bool(winner.get("passed"))
    risks = list(analysis.get("tradeoffs") or [])
    if failures:
        risks.append(f"另有 {len(failures)} 个模型运行失败，需要先排查。")
    if not risks:
        risks.append("仍需结合真实业务峰值、上下文长度和成本预算复测。")

    metric_parts = []
    if throughput is not None:
        metric_parts.append(f"最佳 RPS {throughput}")
    if p95 is not None:
        metric_parts.append(f"P95 {p95}s")
    if error_rate is not None:
        metric_parts.append(f"错误率 {round(error_rate * 100, 2)}%")
    metrics = "，".join(metric_parts) or "综合指标最优"
    passed_text = "满足当前 SLA" if passed else "但未完全满足当前 SLA"
    return (
        f"推荐模型：{winner_name}。主要优势是{metrics}，在本次对比中综合排名第一，{passed_text}。"
        f"风险或注意事项：{risks[0]} 适用场景：优先用于与本次数据集、并发阶梯和输出长度相近的业务流量；"
        "上线前建议用真实高峰流量再做一次容量确认。"
    )


def _valid_ai_conclusion(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lower = text.lower()
    invalid_markers = [
        "observed output",
        "does not contain",
        "business-oriented chinese conclusion",
        "only provides technical metrics",
        "json",
    ]
    if any(marker in lower for marker in invalid_markers):
        return False
    required_keywords = ("推荐", "优势", "风险", "适用")
    return all(keyword in text for keyword in required_keywords)


def _tradeoffs(ranking: list[dict[str, Any]]) -> list[str]:
    if len(ranking) < 2:
        return []
    first = ranking[0]
    second = ranking[1]
    notes = []
    if (second.get("best_throughput") or 0) > (first.get("best_throughput") or 0):
        notes.append(f"{second['display_name']} 吞吐更高，但综合 SLA/延迟/成本得分低于 {first['display_name']}。")
    if first.get("estimated_cost") is not None and second.get("estimated_cost") is not None and second["estimated_cost"] < first["estimated_cost"]:
        notes.append(f"{second['display_name']} 成本更低，可作为成本优先场景备选。")
    return notes
