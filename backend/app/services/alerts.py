from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import json
import ssl
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


def _markdown_line(label: str, value: Any) -> str:
    text = "" if value is None else str(value)
    return f">**{label}**：{text}"


def _font(text: Any, color: str = "info") -> str:
    return f'<font color="{color}">{text}</font>'


def _wecom_markdown_content(payload: dict[str, Any]) -> str:
    event_type = payload.get("event_type", "event")
    if event_type == "daily_report":
        summary = payload.get("summary") or {}
        config = payload.get("report_config") or {}
        sections = set(config.get("include_sections") or [])
        failures = payload.get("current_failures") or []
        recent_failed = payload.get("recent_failed_runs") or []
        disabled_failures = payload.get("disabled_failures") or []
        instances = payload.get("new_api_instances") or []
        status_color = "warning" if summary.get("failing_checks", 0) else "info"
        lines = [
            f"# {_font('AI Vigil 每日巡检报告', config.get('theme_color') or 'info')}",
            _markdown_line("系统状态", _font("在线", "info")),
            _markdown_line("生成时间", payload.get("generated_at")),
            _markdown_line("统计窗口", f"最近 {payload.get('window_hours', 24)} 小时"),
            "\n## 核心摘要",
            _markdown_line(
                "检查项",
                f"总计 {summary.get('total_checks', 0)} 个，启用 {summary.get('enabled_checks', 0)} 个，"
                f"健康 {_font(summary.get('healthy_checks', 0), 'info')} 个，"
                f"失败 {_font(summary.get('failing_checks', 0), status_color)} 个，未知 {summary.get('unknown_checks', 0)} 个",
            ),
            _markdown_line("近24小时可用率", f"{summary.get('availability', 0)}%"),
            _markdown_line("近24小时失败次数", summary.get("failure_runs", 0)),
            _markdown_line("P95 延迟", summary.get("p95_ms")),
            _markdown_line("Golden 通过率", f"{summary.get('golden_pass_rate', 0)}%"),
        ]
        if "ai_summary" in sections and payload.get("ai_summary"):
            lines.extend(["\n## AI 总结", f">{payload.get('ai_summary')}"])
        elif "ai_summary" in sections and payload.get("ai_summary_error"):
            lines.extend(["\n## AI 总结", f">{_font('AI 总结暂不可用', 'comment')}：{payload.get('ai_summary_error')}"])
        if "instances" in sections and instances:
            lines.append("\n## new-api 实例")
            for item in instances[:10]:
                enabled = _font("启用", "info") if item.get("enabled") else _font("禁用", "comment")
                default = " / 默认" if item.get("is_default") else ""
                key = "Key 已配置" if item.get("api_key_configured") else _font("Key 未配置", "warning")
                lines.append(f">- {item.get('name')}：{enabled}{default} / {key}")
        if "current_failures" in sections and failures:
            lines.append("\n## 当前失败项")
            for item in failures[:10]:
                lines.append(f">- {_font(item.get('check_name'), 'warning')}：连续失败 {item.get('failure_count')} 次")
        if "recent_failures" in sections and recent_failed:
            lines.append("\n## 最近失败")
            for item in recent_failed[:10]:
                lines.append(f">- {item.get('check_name')}：{item.get('error')}")
        if "disabled_failures" in sections and disabled_failures:
            lines.append("\n## 已禁用但最后失败")
            for item in disabled_failures[:10]:
                lines.append(f">- {item.get('check_name')}：最后连续失败 {item.get('failure_count')} 次")
        return "\n".join(lines)

    title_map = {
        "failure": "AI Vigil 告警",
        "recovery": "AI Vigil 恢复通知",
        "test": "AI Vigil 测试消息",
    }
    lines = [
        f"# {title_map.get(str(event_type), 'AI Vigil 通知')}",
        _markdown_line("事件", event_type),
        _markdown_line("检查项", payload.get("check_name")),
        _markdown_line("类型", payload.get("check_type")),
        _markdown_line("状态", payload.get("status")),
        _markdown_line("连续失败", payload.get("failure_count")),
        _markdown_line("耗时", f"{payload.get('duration_ms')} ms" if payload.get("duration_ms") is not None else None),
        _markdown_line("错误", payload.get("error")),
        _markdown_line("时间", payload.get("occurred_at")),
    ]
    return "\n".join(line for line in lines if not line.endswith("："))


def _webhook_body(channel: AlertChannel, payload: dict[str, Any]) -> bytes:
    if channel.channel_type == "wecom_markdown":
        document = {
            "msgtype": "markdown",
            "markdown": {
                "content": _wecom_markdown_content(payload),
            },
        }
        return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _verify_option(channel: AlertChannel) -> bool | str:
    if not channel.verify_ssl:
        return False
    return channel.ca_bundle_path or True


def _friendly_webhook_error(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in message:
        return (
            f"{message}. HTTPS 证书校验失败：请在服务器安装 CA 证书，或在该告警通道配置 CA bundle，"
            "必要时可仅对该通道关闭 SSL 校验。"
        )
    return message


async def _send_webhook(channel: AlertChannel, payload: dict[str, Any]) -> tuple[str, str | None]:
    body = _webhook_body(channel, payload)
    headers = {"Content-Type": "application/json", **(channel.headers or {})}
    if channel.secret:
        signature = hmac.new(channel.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Monitor-Signature"] = signature
    try:
        async with httpx.AsyncClient(timeout=15, verify=_verify_option(channel)) as client:
            response = await client.post(channel.webhook_url, content=body, headers=headers)
            response.raise_for_status()
        if channel.channel_type == "wecom_markdown":
            result = response.json()
            if result.get("errcode") != 0:
                return "failed", f"WeCom webhook error {result.get('errcode')}: {result.get('errmsg')}"
        return "sent", None
    except Exception as exc:  # pragma: no cover - exact httpx exception is not important here
        return "failed", _friendly_webhook_error(exc)


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
