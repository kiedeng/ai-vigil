from __future__ import annotations

from datetime import datetime
from fnmatch import fnmatchcase
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Check, ModelRule, NewApiInstance, NewApiModel
from .new_api_instances import accept_headers, resolve_instance


def _category_from_check_type(check_type: str | None) -> str:
    if check_type in {"model_llm_chat", "model_llm_completion"}:
        return "llm"
    if check_type == "model_vision_chat":
        return "vision"
    if check_type == "model_embedding":
        return "embedding"
    if check_type == "model_rerank":
        return "rerank"
    if check_type in {"model_audio_transcription", "model_audio_translation", "model_audio_speech"}:
        return "audio"
    if check_type in {"model_image_generation", "model_image_edit"}:
        return "image"
    if check_type == "model_moderation":
        return "moderation"
    if check_type == "model_custom_http":
        return "custom"
    return "unmatched"


def match_rule(model_id: str, rules: list[ModelRule]) -> ModelRule | None:
    for rule in sorted(rules, key=lambda item: item.priority):
        if rule.enabled is False:
            continue
        if rule.match_type == "exact" and model_id == rule.pattern:
            return rule
        if rule.match_type == "glob" and fnmatchcase(model_id.lower(), rule.pattern.lower()):
            return rule
        if rule.match_type == "regex" and re.search(rule.pattern, model_id):
            return rule
    return None


def _ensure_check(db: Session, instance: NewApiInstance, model_id: str, rule: ModelRule) -> Check:
    check = (
        db.query(Check)
        .filter(Check.new_api_instance_id == instance.id, Check.model_name == model_id, Check.type == rule.check_type)
        .first()
    )
    if check:
        return check
    check = Check(
        name=f"{instance.name} {model_id}",
        type=rule.check_type,
        enabled=True,
        interval_seconds=get_settings().default_interval_seconds,
        timeout_seconds=get_settings().default_timeout_seconds,
        failure_threshold=get_settings().default_failure_threshold,
        new_api_instance_id=instance.id,
        model_name=model_id,
        request_config=rule.request_config or {},
        validation_config=rule.validation_config or {},
    )
    db.add(check)
    db.flush()
    return check


async def fetch_models(db: Session, instance_id: int | None = None) -> list[str]:
    instance = resolve_instance(db, instance_id)
    base = instance.base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{base}/v1/models", headers=accept_headers(instance))
        response.raise_for_status()
    payload: dict[str, Any] = response.json()
    models = []
    for item in payload.get("data", []):
        model_id = item.get("id") or item.get("model")
        if model_id:
            models.append(str(model_id))
    return sorted(set(models))


async def sync_new_api_models(db: Session, instance_id: int | None = None) -> list[NewApiModel]:
    instance = resolve_instance(db, instance_id)
    model_ids = await fetch_models(db, instance.id)
    rules = db.query(ModelRule).filter(ModelRule.enabled.is_(True)).order_by(ModelRule.priority.asc()).all()
    synced: list[NewApiModel] = []
    now = datetime.utcnow()
    for model_id in model_ids:
        rule = match_rule(model_id, rules)
        row = db.query(NewApiModel).filter(NewApiModel.instance_id == instance.id, NewApiModel.model_id == model_id).first()
        if row is None:
            row = NewApiModel(instance_id=instance.id, model_id=model_id)
            db.add(row)
        row.last_seen_at = now
        if rule:
            check = _ensure_check(db, instance, model_id, rule)
            row.category = _category_from_check_type(rule.check_type)
            row.check_type = rule.check_type
            row.matched_rule_id = rule.id
            row.check_id = check.id
        else:
            row.category = "unmatched"
            row.check_type = None
            row.matched_rule_id = None
            row.check_id = None
        synced.append(row)
    db.commit()
    for row in synced:
        db.refresh(row)
    return synced


async def sync_all_new_api_models(db: Session) -> list[NewApiModel]:
    instances = db.query(NewApiInstance).filter(NewApiInstance.enabled.is_(True)).order_by(NewApiInstance.id.asc()).all()
    rows: list[NewApiModel] = []
    for instance in instances:
        rows.extend(await sync_new_api_models(db, instance.id))
    return rows
