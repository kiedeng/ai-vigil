import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models import Check
from backend.app.services.check_runner import _extract_chat_content, run_check_once


def test_extract_chat_content_accepts_compatible_shapes():
    assert _extract_chat_content({"choices": [{"message": {"content": "OK"}}]}) == "OK"
    assert _extract_chat_content({"choices": [{"message": {"content": [{"type": "text", "text": "OK"}]}}]}) == "OK"
    assert _extract_chat_content({"choices": [{"message": {"reasoning_content": "thinking"}}]}) == "thinking"
    assert _extract_chat_content({"choices": [{"text": "legacy"}]}) == "legacy"
    assert _extract_chat_content({"choices": [{"message": {"tool_calls": [{"name": "health"}]}}]})


@pytest.mark.asyncio
async def test_run_check_once_initializes_failure_state():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_factory()
    try:
        check = Check(
            name="bad type",
            type="not_supported",
            enabled=True,
            interval_seconds=300,
            timeout_seconds=1,
            failure_threshold=3,
            request_config={},
            validation_config={},
            ai_config={},
        )
        db.add(check)
        db.commit()
        db.refresh(check)

        run = await run_check_once(db, check)

        db.refresh(check)
        assert run.status == "failure"
        assert check.state is not None
        assert check.state.consecutive_failures == 1
        assert check.state.status == "failure"
    finally:
        db.close()
