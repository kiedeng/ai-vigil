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
    "daily_report_ai_summary_enabled",
    "daily_report_theme_color",
    "daily_report_include_sections",
    "daily_report_ai_prompt",
}

DEFAULT_REPORT_SECTIONS = [
    "summary",
    "ai_summary",
    "instances",
    "current_failures",
    "recent_failures",
    "disabled_failures",
]

DEFAULT_REPORT_AI_PROMPT = (
    "请作为资深 SRE/AI 平台负责人，根据下面 AI Vigil 监控日报数据，"
    "用中文输出一段适合发给管理者的简短总结。要求：1）先给总体判断；"
    "2）列出主要风险；3）给出建议动作；4）控制在 180 字以内。"
)


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
        "daily_report_ai_summary_enabled": get_setting_value(db, "daily_report_ai_summary_enabled", True),
        "daily_report_theme_color": get_setting_value(db, "daily_report_theme_color", "info"),
        "daily_report_include_sections": get_setting_value(
            db, "daily_report_include_sections", DEFAULT_REPORT_SECTIONS
        ),
        "daily_report_ai_prompt": get_setting_value(db, "daily_report_ai_prompt", DEFAULT_REPORT_AI_PROMPT),
        "database_url": env.database_url,
    }
