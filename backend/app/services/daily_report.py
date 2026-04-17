from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..models import AlertChannel, AlertEvent, Check, CheckRun, CheckState, GoldenRun, NewApiInstance
from .alerts import _send_webhook
from .analytics import _percentile
from .new_api_instances import auth_headers, resolve_instance
from .settings import effective_settings


def _extract_summary_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    content = message.get("content") or message.get("reasoning_content") or choice.get("text")
    if isinstance(content, list):
        return "".join(str(item.get("text") or item.get("content") or "") for item in content if isinstance(item, dict))
    return str(content or "").strip()


def build_daily_report_payload(db: Session) -> dict[str, Any]:
    since = datetime.utcnow() - timedelta(hours=24)
    runs = db.query(CheckRun).filter(CheckRun.created_at >= since).all()
    total_runs = len(runs)
    success_runs = sum(1 for row in runs if row.status == "success")
    failure_runs = total_runs - success_runs
    latencies = [row.duration_ms for row in runs if row.duration_ms is not None]

    settings = effective_settings(db)
    total_checks = db.query(Check).count()
    enabled_checks = db.query(Check).filter(Check.enabled.is_(True)).count()
    disabled_checks = max(total_checks - enabled_checks, 0)
    healthy = (
        db.query(CheckState)
        .join(Check, Check.id == CheckState.check_id)
        .filter(Check.enabled.is_(True), CheckState.status == "success")
        .count()
    )
    failing = (
        db.query(CheckState)
        .join(Check, Check.id == CheckState.check_id)
        .filter(Check.enabled.is_(True), CheckState.status == "failure")
        .count()
    )
    unknown = max(enabled_checks - healthy - failing, 0)
    golden_total = db.query(GoldenRun).filter(GoldenRun.created_at >= since).count()
    golden_success = (
        db.query(GoldenRun).filter(GoldenRun.created_at >= since, GoldenRun.status == "success").count()
    )
    current_failures = (
        db.query(CheckState, Check)
        .join(Check, Check.id == CheckState.check_id)
        .filter(Check.enabled.is_(True), CheckState.status == "failure")
        .order_by(CheckState.consecutive_failures.desc())
        .limit(20)
        .all()
    )
    disabled_failures = (
        db.query(CheckState, Check)
        .join(Check, Check.id == CheckState.check_id)
        .filter(Check.enabled.is_(False), CheckState.status == "failure")
        .order_by(CheckState.consecutive_failures.desc())
        .limit(20)
        .all()
    )
    recent_failed_runs = (
        db.query(CheckRun, Check)
        .join(Check, Check.id == CheckRun.check_id)
        .filter(CheckRun.created_at >= since, CheckRun.status == "failure")
        .order_by(CheckRun.id.desc())
        .limit(20)
        .all()
    )
    instances = db.query(NewApiInstance).order_by(NewApiInstance.is_default.desc(), NewApiInstance.id.asc()).all()

    return {
        "event_type": "daily_report",
        "status": "alive",
        "generated_at": datetime.utcnow().isoformat(),
        "window_hours": 24,
        "summary": {
            "total_checks": total_checks,
            "enabled_checks": enabled_checks,
            "disabled_checks": disabled_checks,
            "healthy_checks": healthy,
            "failing_checks": failing,
            "unknown_checks": unknown,
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failure_runs": failure_runs,
            "availability": round((success_runs / total_runs) * 100, 2) if total_runs else 0.0,
            "p50_ms": _percentile(latencies, 50),
            "p90_ms": _percentile(latencies, 90),
            "p95_ms": _percentile(latencies, 95),
            "golden_total": golden_total,
            "golden_success": golden_success,
            "golden_pass_rate": round((golden_success / golden_total) * 100, 2) if golden_total else 0.0,
        },
        "new_api_instances": [
            {
                "id": item.id,
                "name": item.name,
                "base_url": item.base_url,
                "enabled": item.enabled,
                "is_default": item.is_default,
                "api_key_configured": item.api_key_configured,
            }
            for item in instances
        ],
        "current_failures": [
            {
                "check_id": check.id,
                "check_name": check.name,
                "check_type": check.type,
                "failure_count": state.consecutive_failures,
                "last_failure_at": state.last_failure_at.isoformat() if state.last_failure_at else None,
            }
            for state, check in current_failures
        ],
        "disabled_failures": [
            {
                "check_id": check.id,
                "check_name": check.name,
                "check_type": check.type,
                "failure_count": state.consecutive_failures,
                "last_failure_at": state.last_failure_at.isoformat() if state.last_failure_at else None,
            }
            for state, check in disabled_failures
        ],
        "recent_failed_runs": [
            {
                "run_id": run.id,
                "check_id": check.id,
                "check_name": check.name,
                "error": run.error,
                "created_at": run.created_at.isoformat(),
            }
            for run, check in recent_failed_runs
        ],
        "report_config": {
            "theme_color": settings.get("daily_report_theme_color", "info"),
            "include_sections": settings.get("daily_report_include_sections", []),
            "ai_summary_enabled": settings.get("daily_report_ai_summary_enabled", True),
        },
    }


async def add_ai_summary(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    settings = effective_settings(db)
    if not settings.get("daily_report_ai_summary_enabled", True):
        return payload
    try:
        instance = resolve_instance(db, None)
        base = instance.base_url.rstrip("/")
        prompt = (
            f"{settings.get('daily_report_ai_prompt')}\n\n"
            f"日报数据 JSON：\n{json.dumps(payload, ensure_ascii=False, default=str)[:6000]}"
        )
        request = {
            "model": settings["evaluator_model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 300,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{base}/v1/chat/completions", headers=auth_headers(instance), json=request)
        if response.status_code >= 400:
            payload["ai_summary_error"] = f"Evaluator HTTP error: {response.status_code}; {response.text[:500]}"
            return payload
        payload["ai_summary"] = _extract_summary_content(response.json())[:800]
    except Exception as exc:
        payload["ai_summary_error"] = str(exc)
    return payload


async def send_daily_report(db: Session) -> list[AlertEvent]:
    channels = db.query(AlertChannel).filter(AlertChannel.enabled.is_(True)).all()
    payload = build_daily_report_payload(db)
    payload = await add_ai_summary(db, payload)
    events: list[AlertEvent] = []
    for channel in channels:
        status, error = await _send_webhook(channel, payload)
        event = AlertEvent(
            channel_id=channel.id,
            event_type="daily_report",
            status=status,
            payload=payload,
            error=error,
        )
        db.add(event)
        events.append(event)
    db.commit()
    for event in events:
        db.refresh(event)
    return events
