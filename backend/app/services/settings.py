from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AppSetting


SETTING_KEYS = {
    "new_api_base_url",
    "evaluator_model",
    "default_interval_seconds",
    "default_timeout_seconds",
    "default_failure_threshold",
    "alert_cooldown_minutes",
    "daily_report_enabled",
    "daily_report_hour",
    "daily_report_minute",
}


def get_setting_value(db: Session, key: str, default: Any) -> Any:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        return default
    return row.value.get("value", default)


def set_setting_value(db: Session, key: str, value: Any) -> AppSetting:
    if key not in SETTING_KEYS:
        raise ValueError(f"Unsupported setting: {key}")
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        row = AppSetting(key=key, value={"value": value})
        db.add(row)
    else:
        row.value = {"value": value}
    db.commit()
    db.refresh(row)
    return row


def effective_settings(db: Session) -> dict[str, Any]:
    env = get_settings()
    return {
        "new_api_base_url": get_setting_value(db, "new_api_base_url", env.new_api_base_url),
        "new_api_key_configured": bool(env.new_api_key),
        "evaluator_model": get_setting_value(db, "evaluator_model", env.evaluator_model),
        "default_interval_seconds": get_setting_value(
            db, "default_interval_seconds", env.default_interval_seconds
        ),
        "default_timeout_seconds": get_setting_value(db, "default_timeout_seconds", env.default_timeout_seconds),
        "default_failure_threshold": get_setting_value(
            db, "default_failure_threshold", env.default_failure_threshold
        ),
        "alert_cooldown_minutes": get_setting_value(db, "alert_cooldown_minutes", env.alert_cooldown_minutes),
        "daily_report_enabled": get_setting_value(db, "daily_report_enabled", True),
        "daily_report_hour": get_setting_value(db, "daily_report_hour", 9),
        "daily_report_minute": get_setting_value(db, "daily_report_minute", 0),
        "database_url": env.database_url,
    }
