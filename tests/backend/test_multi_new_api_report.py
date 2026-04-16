import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import AlertChannel, Check, ModelRule, NewApiInstance
from backend.app.services import alerts as alerts_service
from backend.app.services import daily_report as daily_report_service
from backend.app.services.alerts import _send_webhook, _webhook_body
from backend.app.services.daily_report import build_daily_report_payload, send_daily_report
from backend.app.services.new_api import sync_new_api_models


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return session_factory()


def test_wecom_markdown_webhook_body():
    channel = AlertChannel(
        name="wecom",
        channel_type="wecom_markdown",
        webhook_url="http://example.test/webhook",
        headers={},
        enabled=True,
    )
    body = json.loads(
        _webhook_body(
            channel,
            {
                "event_type": "test",
                "check_name": "Webhook test",
                "check_type": "test",
                "status": "test",
                "failure_count": 0,
                "duration_ms": 0,
                "error": None,
                "occurred_at": "2026-04-16T09:00:00",
            },
        )
    )

    assert body["msgtype"] == "markdown"
    assert "AI Vigil 测试消息" in body["markdown"]["content"]


@pytest.mark.asyncio
async def test_wecom_error_response_is_failed(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"errcode": 93000, "errmsg": "invalid webhook"}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, content, headers):
            return FakeResponse()

    channel = AlertChannel(
        name="wecom",
        channel_type="wecom_markdown",
        webhook_url="http://example.test/webhook",
        headers={},
        enabled=True,
    )
    monkeypatch.setattr(alerts_service.httpx, "AsyncClient", FakeClient)

    status, error = await _send_webhook(channel, {"event_type": "test"})

    assert status == "failed"
    assert "WeCom webhook error 93000" in error


@pytest.mark.asyncio
async def test_same_model_can_sync_for_multiple_instances(monkeypatch):
    db = _db()
    try:
        test_instance = NewApiInstance(name="test", base_url="http://test", api_key="test-key", enabled=True)
        prod_instance = NewApiInstance(name="prod", base_url="http://prod", api_key="prod-key", enabled=True)
        rule = ModelRule(
            name="DeepSeek",
            pattern="deepseek*",
            match_type="glob",
            check_type="model_llm_chat",
            enabled=True,
            priority=10,
            request_config={},
            validation_config={},
        )
        db.add_all([test_instance, prod_instance, rule])
        db.commit()

        async def fake_fetch_models(db, instance_id=None):
            return ["deepseek-chat"]

        monkeypatch.setattr("backend.app.services.new_api.fetch_models", fake_fetch_models)

        test_rows = await sync_new_api_models(db, test_instance.id)
        prod_rows = await sync_new_api_models(db, prod_instance.id)

        assert test_rows[0].instance_id == test_instance.id
        assert prod_rows[0].instance_id == prod_instance.id
        assert test_rows[0].model_id == prod_rows[0].model_id
        assert db.query(Check).filter(Check.model_name == "deepseek-chat").count() == 2
        assert test_instance.api_key_configured is True
    finally:
        db.close()


@pytest.mark.asyncio
async def test_daily_report_payload_and_event(monkeypatch):
    db = _db()
    try:
        instance = NewApiInstance(name="prod", base_url="http://prod", enabled=True, is_default=True)
        channel = AlertChannel(name="ops", webhook_url="http://example.test/webhook", headers={}, enabled=True)
        db.add_all([instance, channel])
        db.commit()

        payload = build_daily_report_payload(db)
        assert payload["event_type"] == "daily_report"
        assert payload["status"] == "alive"
        assert payload["new_api_instances"][0]["name"] == "prod"

        async def fake_send_webhook(channel, payload):
            return "sent", None

        monkeypatch.setattr(daily_report_service, "_send_webhook", fake_send_webhook)
        events = await send_daily_report(db)

        assert len(events) == 1
        assert events[0].event_type == "daily_report"
        assert events[0].status == "sent"
    finally:
        db.close()
