from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Check, GoldenSet, NewApiInstance, NewApiModel
from .settings import effective_settings


def ensure_default_instance(db: Session) -> NewApiInstance:
    existing = db.query(NewApiInstance).order_by(NewApiInstance.is_default.desc(), NewApiInstance.id.asc()).first()
    if existing:
        if not db.query(NewApiInstance).filter(NewApiInstance.is_default.is_(True)).first():
            existing.is_default = True
            db.commit()
            db.refresh(existing)
        return existing

    settings = effective_settings(db)
    env = get_settings()
    instance = NewApiInstance(
        name="default",
        base_url=str(settings["new_api_base_url"]),
        api_key=env.new_api_key or None,
        enabled=True,
        is_default=True,
        description="Created from legacy new-api settings.",
    )
    db.add(instance)
    db.flush()
    db.query(Check).filter(Check.new_api_instance_id.is_(None)).update({"new_api_instance_id": instance.id})
    db.query(GoldenSet).filter(GoldenSet.new_api_instance_id.is_(None)).update({"new_api_instance_id": instance.id})
    db.query(NewApiModel).filter(NewApiModel.instance_id.is_(None)).update({"instance_id": instance.id})
    db.commit()
    db.refresh(instance)
    return instance


def default_instance(db: Session) -> NewApiInstance:
    instance = db.query(NewApiInstance).filter(NewApiInstance.is_default.is_(True)).first()
    return instance or ensure_default_instance(db)


def resolve_instance(db: Session, instance_id: int | None = None) -> NewApiInstance:
    if instance_id:
        instance = db.query(NewApiInstance).filter(NewApiInstance.id == instance_id).first()
        if instance:
            return instance
    return default_instance(db)


def set_default_instance(db: Session, instance: NewApiInstance) -> NewApiInstance:
    db.query(NewApiInstance).update({"is_default": False})
    instance.is_default = True
    db.commit()
    db.refresh(instance)
    return instance


def can_delete_instance(db: Session, instance_id: int) -> tuple[bool, str | None]:
    checks = db.query(Check).filter(Check.new_api_instance_id == instance_id).count()
    golden_sets = db.query(GoldenSet).filter(GoldenSet.new_api_instance_id == instance_id).count()
    models = db.query(NewApiModel).filter(NewApiModel.instance_id == instance_id).count()
    if checks or golden_sets or models:
        return False, f"Instance is used by {checks} checks, {golden_sets} golden sets, and {models} models"
    return True, None


def auth_headers(instance: NewApiInstance, content_type: str | None = "application/json") -> dict[str, str]:
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    if instance.api_key:
        headers["Authorization"] = f"Bearer {instance.api_key}"
    return headers


def accept_headers(instance: NewApiInstance) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if instance.api_key:
        headers["Authorization"] = f"Bearer {instance.api_key}"
    return headers


async def test_instance(instance: NewApiInstance) -> dict[str, object]:
    started = datetime.utcnow()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{instance.base_url.rstrip('/')}/v1/models", headers=accept_headers(instance))
        response.raise_for_status()
    payload = response.json()
    models = payload.get("data", []) if isinstance(payload, dict) else []
    return {
        "status": "success",
        "model_count": len(models) if isinstance(models, list) else 0,
        "duration_ms": int((datetime.utcnow() - started).total_seconds() * 1000),
    }
