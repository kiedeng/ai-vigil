from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..models import AlertChannel, AlertEvent, Check, CheckRun, CheckState


def _payload(check: Check, run: CheckRun, state: CheckState, event_type: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "check_id": check.id,
        "check_name": check.name,
        "check_type": check.type,
        "status": run.status,
        "failure_count": state.consecutive_failures,
        "duration_ms": run.duration_ms,
        "error": run.error,
        "run_id": run.id,
        "occurred_at": run.created_at.isoformat(),
    }


def _should_send_failure(state: CheckState, channel: AlertChannel, threshold: int) -> bool:
    if state.consecutive_failures < threshold:
        return False
    if not state.alert_open:
        return True
    if state.last_alert_at is None:
        return True
    return datetime.utcnow() - state.last_alert_at >= timedelta(minutes=channel.cooldown_minutes)


async def _send_webhook(channel: AlertChannel, payload: dict[str, Any]) -> tuple[str, str | None]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json", **(channel.headers or {})}
    if channel.secret:
        signature = hmac.new(channel.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Monitor-Signature"] = signature
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(channel.webhook_url, content=body, headers=headers)
            response.raise_for_status()
        return "sent", None
    except Exception as exc:  # pragma: no cover - exact httpx exception is not important here
        return "failed", str(exc)


async def send_test_alert(db: Session, channel: AlertChannel) -> AlertEvent:
    payload = {
        "event_type": "test",
        "check_id": None,
        "check_name": "Webhook test",
        "check_type": "test",
        "status": "test",
        "failure_count": 0,
        "duration_ms": 0,
        "error": None,
        "run_id": None,
        "occurred_at": datetime.utcnow().isoformat(),
    }
    status, error = await _send_webhook(channel, payload)
    event = AlertEvent(channel_id=channel.id, event_type="test", status=status, payload=payload, error=error)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


async def process_alerts(db: Session, check: Check, run: CheckRun, state: CheckState) -> None:
    channels = db.query(AlertChannel).filter(AlertChannel.enabled.is_(True)).all()
    if not channels:
        return

    event_type: str | None = None
    target_channels: list[AlertChannel] = []
    if run.status == "failure":
        for channel in channels:
            if _should_send_failure(state, channel, check.failure_threshold):
                target_channels.append(channel)
        if target_channels:
            event_type = "failure"
    elif run.status == "success" and state.alert_open:
        target_channels = channels
        event_type = "recovery"

    if event_type is None:
        return

    payload = _payload(check, run, state, event_type)
    for channel in target_channels:
        status, error = await _send_webhook(channel, payload)
        db.add(
            AlertEvent(
                channel_id=channel.id,
                check_id=check.id,
                run_id=run.id,
                event_type=event_type,
                status=status,
                payload=payload,
                error=error,
            )
        )

    if event_type == "failure":
        state.alert_open = True
        state.last_alert_at = datetime.utcnow()
    elif event_type == "recovery":
        state.alert_open = False
        state.last_alert_at = datetime.utcnow()
    db.commit()

