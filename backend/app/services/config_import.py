"""
YAML configuration import service.

Supports upserting NewApiInstance, Check, AlertChannel, and GoldenSet/GoldenCase
from a YAML config file into the database.

Upsert semantics: entities are matched by name. Existing entities are updated
(preserving id and historical data); new entities are created.
Entities present in the DB but not in the YAML are left untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from ..models import (
    AlertChannel,
    Check,
    GoldenCase,
    GoldenSet,
    NewApiInstance,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class ImportErrors:
    def __init__(self) -> None:
        self.instances: list[str] = []
        self.checks: list[str] = []
        self.alert_channels: list[str] = []
        self.golden_sets: list[str] = []


class ImportResult:
    def __init__(self) -> None:
        self.instances_created = 0
        self.instances_updated = 0
        self.checks_created = 0
        self.checks_updated = 0
        self.alert_channels_created = 0
        self.alert_channels_updated = 0
        self.golden_sets_created = 0
        self.golden_sets_updated = 0
        self.golden_cases_created = 0
        self.golden_cases_updated = 0
        self.errors = ImportErrors()

    def to_dict(self) -> dict[str, Any]:
        return {
            "instances": {"created": self.instances_created, "updated": self.instances_updated},
            "checks": {"created": self.checks_created, "updated": self.checks_updated},
            "alert_channels": {
                "created": self.alert_channels_created,
                "updated": self.alert_channels_updated,
            },
            "golden_sets": {
                "created": self.golden_sets_created,
                "updated": self.golden_sets_updated,
            },
            "golden_cases": {
                "created": self.golden_cases_created,
                "updated": self.golden_cases_updated,
            },
            "errors": {
                "instances": self.errors.instances,
                "checks": self.errors.checks,
                "alert_channels": self.errors.alert_channels,
                "golden_sets": self.errors.golden_sets,
            },
        }


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def load_config_file(path: Path) -> dict[str, Any]:
    """Load and parse a YAML config file. Raises on parse errors."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# NewApiInstance
# ---------------------------------------------------------------------------


def _upsert_instance(db: Session, data: dict[str, Any]) -> tuple[NewApiInstance, bool]:
    """Upsert a NewApiInstance by name. Returns (instance, was_created)."""
    name = data.get("name", "")
    if not name:
        raise ValueError("instance is missing required field 'name'")

    instance = db.query(NewApiInstance).filter(NewApiInstance.name == name).first()
    created = instance is None
    if created:
        instance = NewApiInstance()

    instance.name = name
    instance.base_url = data.get("base_url", instance.base_url or "")
    instance.enabled = data.get("enabled", instance.enabled if not created else True)
    instance.is_default = data.get("is_default", instance.is_default if not created else False)
    instance.description = data.get("description", instance.description)

    # Only update api_key if provided and non-empty
    if data.get("api_key"):
        instance.api_key = data["api_key"]

    if created:
        db.add(instance)

    return instance, created


def import_instances(db: Session, instances: list[dict[str, Any]], result: ImportResult) -> dict[str, NewApiInstance]:
    """Import all instances. Returns name -> instance map for dependency resolution."""
    name_map: dict[str, NewApiInstance] = {}
    for item in instances or []:
        try:
            instance, created = _upsert_instance(db, item)
            name_map[instance.name] = instance
            if created:
                result.instances_created += 1
            else:
                result.instances_updated += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.instances.append(f"{item.get('name', '?')}: {exc}")
    db.commit()
    # Refresh to get ids
    for name, inst in name_map.items():
        db.refresh(inst)
    return name_map


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _upsert_check(
    db: Session,
    data: dict[str, Any],
    instance_map: dict[str, NewApiInstance],
    result: ImportResult,
) -> None:
    """Upsert a Check by name."""
    name = data.get("name", "")
    if not name:
        result.errors.checks.append("<unnamed>: missing required field 'name'")
        return

    check = db.query(Check).filter(Check.name == name).first()
    created = check is None
    if created:
        check = Check()

    check.name = name
    check.type = data.get("type", check.type or "model_llm_chat")
    check.enabled = data.get("enabled", check.enabled if not created else True)
    check.interval_seconds = data.get("interval_seconds", check.interval_seconds or 300)
    check.timeout_seconds = data.get("timeout_seconds", check.timeout_seconds or 30)
    check.failure_threshold = data.get("failure_threshold", check.failure_threshold or 3)
    check.model_name = data.get("model_name", check.model_name)

    # Resolve instance by name
    instance_name = data.get("instance")
    if instance_name and instance_name in instance_map:
        check.new_api_instance_id = instance_map[instance_name].id
    elif instance_name:
        # Try to find by name in DB directly
        inst = db.query(NewApiInstance).filter(NewApiInstance.name == instance_name).first()
        if inst:
            check.new_api_instance_id = inst.id

    check.request_config = data.get("request_config", data.get("request", check.request_config or {}))
    check.validation_config = data.get("validation_config", data.get("validation", check.validation_config or {}))
    check.ai_config = data.get("ai_config", check.ai_config or {})

    if created:
        db.add(check)

    if created:
        result.checks_created += 1
    else:
        result.checks_updated += 1


def import_checks(
    db: Session,
    checks: list[dict[str, Any]],
    instance_map: dict[str, NewApiInstance],
    result: ImportResult,
) -> None:
    """Import all checks."""
    for item in checks or []:
        try:
            _upsert_check(db, item, instance_map, result)
        except Exception as exc:  # noqa: BLE001
            result.errors.checks.append(f"{item.get('name', '?')}: {exc}")
    db.commit()


# ---------------------------------------------------------------------------
# AlertChannel
# ---------------------------------------------------------------------------


def _upsert_alert_channel(db: Session, data: dict[str, Any], result: ImportResult) -> None:
    """Upsert an AlertChannel by name."""
    name = data.get("name", "")
    if not name:
        result.errors.alert_channels.append("<unnamed>: missing required field 'name'")
        return

    channel = db.query(AlertChannel).filter(AlertChannel.name == name).first()
    created = channel is None
    if created:
        channel = AlertChannel()

    channel.name = name
    channel.channel_type = data.get("channel_type", channel.channel_type or "generic")
    channel.enabled = data.get("enabled", channel.enabled if not created else True)
    channel.webhook_url = data.get("webhook_url", channel.webhook_url or "")
    channel.headers = data.get("headers", channel.headers or {})
    channel.cooldown_minutes = data.get("cooldown_minutes", channel.cooldown_minutes or 30)

    # Only update secret if provided and non-empty
    if data.get("secret"):
        channel.secret = data["secret"]

    if created:
        db.add(channel)

    if created:
        result.alert_channels_created += 1
    else:
        result.alert_channels_updated += 1


def import_alert_channels(db: Session, channels: list[dict[str, Any]], result: ImportResult) -> None:
    """Import all alert channels."""
    for item in channels or []:
        try:
            _upsert_alert_channel(db, item, result)
        except Exception as exc:  # noqa: BLE001
            result.errors.alert_channels.append(f"{item.get('name', '?')}: {exc}")
    db.commit()


# ---------------------------------------------------------------------------
# GoldenSet + GoldenCase
# ---------------------------------------------------------------------------


def _upsert_golden_set(
    db: Session,
    data: dict[str, Any],
    instance_map: dict[str, NewApiInstance],
    result: ImportResult,
) -> None:
    """Upsert a GoldenSet and its cases by name."""
    name = data.get("name", "")
    if not name:
        result.errors.golden_sets.append("<unnamed>: missing required field 'name'")
        return

    golden_set = db.query(GoldenSet).filter(GoldenSet.name == name).first()
    created = golden_set is None
    if created:
        golden_set = GoldenSet()

    golden_set.name = name
    golden_set.description = data.get("description", golden_set.description)
    golden_set.model_name = data.get("model_name", golden_set.model_name or "")
    golden_set.check_type = data.get("check_type", golden_set.check_type or "model_llm_chat")
    golden_set.enabled = data.get("enabled", golden_set.enabled if not created else True)
    golden_set.evaluator_config = data.get(
        "evaluator_config", golden_set.evaluator_config or {}
    )

    # Resolve instance
    instance_name = data.get("instance")
    if instance_name and instance_name in instance_map:
        golden_set.new_api_instance_id = instance_map[instance_name].id
    elif instance_name:
        inst = db.query(NewApiInstance).filter(NewApiInstance.name == instance_name).first()
        if inst:
            golden_set.new_api_instance_id = inst.id

    if created:
        db.add(golden_set)

    if created:
        result.golden_sets_created += 1
    else:
        result.golden_sets_updated += 1

    db.flush()  # Get the id

    # Import cases
    for case_data in data.get("cases") or []:
        _upsert_golden_case(db, golden_set.id, case_data, result)


def _upsert_golden_case(
    db: Session,
    golden_set_id: int,
    data: dict[str, Any],
    result: ImportResult,
) -> None:
    """Upsert a GoldenCase by (golden_set_id, name)."""
    name = data.get("name", "")
    if not name:
        result.errors.golden_sets.append(f"<case without name in golden_set {golden_set_id}>")
        return

    case = (
        db.query(GoldenCase)
        .filter(GoldenCase.golden_set_id == golden_set_id, GoldenCase.name == name)
        .first()
    )
    created = case is None
    if created:
        case = GoldenCase()

    case.golden_set_id = golden_set_id
    case.name = name
    case.enabled = data.get("enabled", case.enabled if not created else True)
    case.input_config = data.get("input_config", data.get("input", case.input_config or {}))
    case.expected_config = data.get("expected_config", data.get("expected", case.expected_config or {}))

    if created:
        db.add(case)

    if created:
        result.golden_cases_created += 1
    else:
        result.golden_cases_updated += 1


def import_golden_sets(
    db: Session,
    golden_sets: list[dict[str, Any]],
    instance_map: dict[str, NewApiInstance],
    result: ImportResult,
) -> None:
    """Import all golden sets and their cases."""
    for item in golden_sets or []:
        try:
            _upsert_golden_set(db, item, instance_map, result)
        except Exception as exc:  # noqa: BLE001
            result.errors.golden_sets.append(f"{item.get('name', '?')}: {exc}")
    db.commit()


# ---------------------------------------------------------------------------
# Top-level import
# ---------------------------------------------------------------------------


def import_all(db: Session, config_path: Path) -> ImportResult:
    """
    Load a YAML config file and upsert all entities into the database.

    Returns an ImportResult with counts and any errors encountered.
    """
    config = load_config_file(config_path)

    result = ImportResult()

    # 1. Instances first (other entities depend on them)
    instance_map = import_instances(db, config.get("instances", []), result)

    # 2. Checks
    import_checks(db, config.get("checks", []), instance_map, result)

    # 3. Alert channels (no dependencies)
    import_alert_channels(db, config.get("alert_channels", []), result)

    # 4. Golden sets (may reference instances)
    import_golden_sets(db, config.get("golden_sets", []), instance_map, result)

    return result
