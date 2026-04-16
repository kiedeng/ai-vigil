"""
Tests for config_import service and API endpoint.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database import Base
from backend.app.main import app
from backend.app.models import AlertChannel, Check, GoldenCase, GoldenSet, NewApiInstance
from backend.app.services.config_import import (
    ImportResult,
    import_all,
    import_alert_channels,
    import_checks,
    import_instances,
    import_golden_sets,
    load_config_file,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# load_config_file
# ---------------------------------------------------------------------------

def test_load_config_file_parses_yaml(tmp_path: Path):
    config_file = tmp_path / "test.yaml"
    config_file.write_text(yaml.dump({"instances": [{"name": "test", "base_url": "http://x.com"}]}))
    config = load_config_file(config_file)
    assert config["instances"][0]["name"] == "test"
    assert config["instances"][0]["base_url"] == "http://x.com"


def test_load_config_file_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config_file(Path("/nonexistent/path.yaml"))


# ---------------------------------------------------------------------------
# import_instances
# ---------------------------------------------------------------------------

def test_import_instances_creates_new(db_session: Session):
    instances = [{"name": "prod", "base_url": "https://api.example.com", "is_default": True}]
    result = ImportResult()
    name_map = import_instances(db_session, instances, result)

    assert len(name_map) == 1
    assert name_map["prod"].name == "prod"
    assert name_map["prod"].base_url == "https://api.example.com"
    assert name_map["prod"].is_default is True
    assert result.instances_created == 1
    assert result.instances_updated == 0


def test_import_instances_updates_existing(db_session: Session):
    # Pre-seed an instance
    inst = NewApiInstance(name="prod", base_url="http://old.com")
    db_session.add(inst)
    db_session.commit()

    instances = [{"name": "prod", "base_url": "https://new.com"}]
    result = ImportResult()
    name_map = import_instances(db_session, instances, result)

    assert result.instances_created == 0
    assert result.instances_updated == 1
    assert name_map["prod"].base_url == "https://new.com"


def test_import_instances_preserves_existing_api_key_when_yaml_empty(db_session: Session):
    inst = NewApiInstance(name="prod", base_url="http://x.com", api_key="sk-old")
    db_session.add(inst)
    db_session.commit()

    instances = [{"name": "prod", "base_url": "http://x.com"}]  # no api_key
    result = ImportResult()
    import_instances(db_session, instances, result)

    db_session.expire_all()
    inst = db_session.query(NewApiInstance).filter_by(name="prod").first()
    assert inst.api_key == "sk-old"


def test_import_instances_updates_api_key_when_provided(db_session: Session):
    inst = NewApiInstance(name="prod", base_url="http://x.com", api_key="sk-old")
    db_session.add(inst)
    db_session.commit()

    instances = [{"name": "prod", "base_url": "http://x.com", "api_key": "sk-new"}]
    result = ImportResult()
    import_instances(db_session, instances, result)

    db_session.expire_all()
    inst = db_session.query(NewApiInstance).filter_by(name="prod").first()
    assert inst.api_key == "sk-new"


# ---------------------------------------------------------------------------
# import_checks
# ---------------------------------------------------------------------------

def test_import_checks_creates_new(db_session: Session):
    # Seed an instance first
    inst = NewApiInstance(name="prod", base_url="http://x.com")
    db_session.add(inst)
    db_session.commit()

    instance_map = {"prod": inst}
    checks = [
        {
            "name": "gpt-4o check",
            "type": "model_llm_chat",
            "model_name": "gpt-4o",
            "instance": "prod",
            "request": {"messages": [{"role": "user", "content": "hi"}]},
            "validation": {"contains": "hi"},
        }
    ]
    result = ImportResult()
    import_checks(db_session, checks, instance_map, result)

    check = db_session.query(Check).filter_by(name="gpt-4o check").first()
    assert check is not None
    assert check.type == "model_llm_chat"
    assert check.model_name == "gpt-4o"
    assert check.new_api_instance_id == inst.id
    assert check.request_config == {"messages": [{"role": "user", "content": "hi"}]}
    assert check.validation_config == {"contains": "hi"}
    assert result.checks_created == 1


def test_import_checks_resolves_instance_by_name(db_session: Session):
    inst = NewApiInstance(name="staging", base_url="http://staging.com")
    db_session.add(inst)
    db_session.commit()

    instance_map = {"staging": inst}
    checks = [{"name": "test", "type": "http_health", "instance": "staging"}]
    result = ImportResult()
    import_checks(db_session, checks, instance_map, result)

    check = db_session.query(Check).filter_by(name="test").first()
    assert check.new_api_instance_id == inst.id


# ---------------------------------------------------------------------------
# import_alert_channels
# ---------------------------------------------------------------------------

def test_import_alert_channels_creates(db_session: Session):
    channels = [
        {
            "name": "企业微信",
            "channel_type": "wecom_markdown",
            "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
            "cooldown_minutes": 15,
        }
    ]
    result = ImportResult()
    import_alert_channels(db_session, channels, result)

    ch = db_session.query(AlertChannel).filter_by(name="企业微信").first()
    assert ch is not None
    assert ch.channel_type == "wecom_markdown"
    assert ch.cooldown_minutes == 15
    assert result.alert_channels_created == 1


def test_import_alert_channels_updates(db_session: Session):
    ch = AlertChannel(name="wechat", channel_type="generic", webhook_url="http://old.com")
    db_session.add(ch)
    db_session.commit()

    channels = [{"name": "wechat", "channel_type": "wecom_markdown", "webhook_url": "http://new.com"}]
    result = ImportResult()
    import_alert_channels(db_session, channels, result)

    db_session.expire_all()
    ch = db_session.query(AlertChannel).filter_by(name="wechat").first()
    assert ch.channel_type == "wecom_markdown"
    assert result.alert_channels_updated == 1


# ---------------------------------------------------------------------------
# import_golden_sets
# ---------------------------------------------------------------------------

def test_import_golden_sets_with_cases(db_session: Session):
    inst = NewApiInstance(name="prod", base_url="http://x.com")
    db_session.add(inst)
    db_session.commit()
    instance_map = {"prod": inst}

    golden_sets = [
        {
            "name": "Quality Regression",
            "model_name": "gpt-4o",
            "check_type": "model_llm_chat",
            "instance": "prod",
            "evaluator_config": {"min_confidence": 0.7},
            "cases": [
                {
                    "name": "math check",
                    "input": {"messages": [{"role": "user", "content": "1+1"}]},
                    "expected": {"contains": "2"},
                }
            ],
        }
    ]
    result = ImportResult()
    import_golden_sets(db_session, golden_sets, instance_map, result)

    gs = db_session.query(GoldenSet).filter_by(name="Quality Regression").first()
    assert gs is not None
    assert gs.model_name == "gpt-4o"
    assert gs.evaluator_config == {"min_confidence": 0.7}
    assert result.golden_sets_created == 1

    case = db_session.query(GoldenCase).filter_by(name="math check").first()
    assert case is not None
    assert case.golden_set_id == gs.id
    assert result.golden_cases_created == 1


# ---------------------------------------------------------------------------
# import_all (end-to-end)
# ---------------------------------------------------------------------------

def test_import_all_end_to_end(tmp_path: Path, db_session: Session):
    config = {
        "instances": [
            {"name": "prod", "base_url": "https://api.example.com", "is_default": True}
        ],
        "checks": [
            {
                "name": "gpt-4o check",
                "type": "model_llm_chat",
                "model_name": "gpt-4o",
                "instance": "prod",
                "request": {"messages": [{"role": "user", "content": "hi"}]},
                "validation": {"contains": "hi"},
            }
        ],
        "alert_channels": [
            {
                "name": "企业微信",
                "channel_type": "wecom_markdown",
                "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
            }
        ],
        "golden_sets": [
            {
                "name": "Quality",
                "model_name": "gpt-4o",
                "check_type": "model_llm_chat",
                "instance": "prod",
                "cases": [
                    {
                        "name": "math",
                        "input": {"messages": [{"role": "user", "content": "1+1"}]},
                        "expected": {"contains": "2"},
                    }
                ],
            }
        ],
    }
    config_file = tmp_path / "ai-vigil.yaml"
    config_file.write_text(yaml.dump(config))

    result = import_all(db_session, config_file)

    assert result.instances_created == 1
    assert result.checks_created == 1
    assert result.alert_channels_created == 1
    assert result.golden_sets_created == 1
    assert result.golden_cases_created == 1
    assert not any(result.errors.instances)
    assert not any(result.errors.checks)
    assert not any(result.errors.alert_channels)
    assert not any(result.errors.golden_sets)


def test_import_all_idempotent(tmp_path: Path, db_session: Session):
    config = {
        "instances": [{"name": "prod", "base_url": "https://api.example.com"}],
        "checks": [{"name": "check1", "type": "model_llm_chat"}],
    }
    config_file = tmp_path / "ai-vigil.yaml"
    config_file.write_text(yaml.dump(config))

    # Import once
    result1 = import_all(db_session, config_file)
    assert result1.instances_created == 1
    assert result1.checks_created == 1

    # Import again — should update, not create
    result2 = import_all(db_session, config_file)
    assert result2.instances_created == 0
    assert result2.instances_updated == 1
    assert result2.checks_created == 0
    assert result2.checks_updated == 1
