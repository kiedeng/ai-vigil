from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


CheckType = Literal[
    "model_llm_chat",
    "model_llm_completion",
    "model_vision_chat",
    "model_embedding",
    "model_rerank",
    "model_audio_transcription",
    "model_audio_translation",
    "model_audio_speech",
    "model_image_generation",
    "model_image_edit",
    "model_moderation",
    "model_custom_http",
    "http_health",
    "http_content_ai",
]


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    username: str


class CheckBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: CheckType
    enabled: bool = True
    interval_seconds: int = Field(default=300, ge=10)
    timeout_seconds: int = Field(default=120, ge=1)
    failure_threshold: int = Field(default=3, ge=1)
    new_api_instance_id: int | None = None
    model_name: str | None = None
    request_config: dict[str, Any] = Field(default_factory=dict)
    validation_config: dict[str, Any] = Field(default_factory=dict)
    ai_config: dict[str, Any] = Field(default_factory=dict)


class CheckCreate(CheckBase):
    pass


class CheckUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: CheckType | None = None
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=10)
    timeout_seconds: int | None = Field(default=None, ge=1)
    failure_threshold: int | None = Field(default=None, ge=1)
    new_api_instance_id: int | None = None
    model_name: str | None = None
    request_config: dict[str, Any] | None = None
    validation_config: dict[str, Any] | None = None
    ai_config: dict[str, Any] | None = None


class CheckStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    consecutive_failures: int
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_run_id: int | None = None
    alert_open: bool
    last_alert_at: datetime | None = None


class CheckOut(CheckBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    state: CheckStateOut | None = None


class CheckRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_id: int
    status: str
    run_mode: str = "manual"
    duration_ms: int
    response_status_code: int | None = None
    response_summary: str | None = None
    error: str | None = None
    ai_result: dict[str, Any]
    created_at: datetime


class ModelRuleBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    pattern: str = Field(min_length=1, max_length=255)
    match_type: Literal["glob", "regex", "exact"] = "glob"
    check_type: CheckType
    enabled: bool = True
    priority: int = 100
    request_config: dict[str, Any] = Field(default_factory=dict)
    validation_config: dict[str, Any] = Field(default_factory=dict)


class ModelRuleCreate(ModelRuleBase):
    pass


class ModelRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    pattern: str | None = Field(default=None, min_length=1, max_length=255)
    match_type: Literal["glob", "regex", "exact"] | None = None
    check_type: CheckType | None = None
    enabled: bool | None = None
    priority: int | None = None
    request_config: dict[str, Any] | None = None
    validation_config: dict[str, Any] | None = None


class ModelRuleOut(ModelRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class NewApiInstanceBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=1)
    api_key: str | None = None
    enabled: bool = True
    is_default: bool = False
    description: str | None = None


class NewApiInstanceCreate(NewApiInstanceBase):
    pass


class NewApiInstanceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, min_length=1)
    api_key: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None
    description: str | None = None


class NewApiInstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    enabled: bool
    is_default: bool
    description: str | None = None
    api_key_configured: bool
    created_at: datetime
    updated_at: datetime


class NewApiInstanceTestOut(BaseModel):
    status: str
    model_count: int
    duration_ms: int


class NewApiModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instance_id: int | None = None
    instance_name: str | None = None
    model_id: str
    category: str
    check_type: str | None = None
    matched_rule_id: int | None = None
    check_id: int | None = None
    last_seen_at: datetime
    updated_at: datetime


class AlertChannelBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    channel_type: Literal["generic", "wecom_markdown"] = "generic"
    enabled: bool = True
    webhook_url: str
    secret: str | None = None
    headers: dict[str, Any] = Field(default_factory=dict)
    cooldown_minutes: int = Field(default=30, ge=1)
    verify_ssl: bool = True
    ca_bundle_path: str | None = None


class AlertChannelCreate(AlertChannelBase):
    pass


class AlertChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    channel_type: Literal["generic", "wecom_markdown"] | None = None
    enabled: bool | None = None
    webhook_url: str | None = None
    secret: str | None = None
    headers: dict[str, Any] | None = None
    cooldown_minutes: int | None = Field(default=None, ge=1)
    verify_ssl: bool | None = None
    ca_bundle_path: str | None = None


class AlertChannelOut(AlertChannelBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AlertEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int | None
    check_id: int | None
    run_id: int | None
    event_type: str
    status: str
    payload: dict[str, Any]
    error: str | None
    created_at: datetime


class SettingsOut(BaseModel):
    new_api_base_url: str
    new_api_key_configured: bool
    evaluator_model: str
    default_interval_seconds: int
    default_timeout_seconds: int
    default_failure_threshold: int
    alert_cooldown_minutes: int
    daily_report_enabled: bool
    daily_report_hour: int
    daily_report_minute: int
    daily_report_ai_summary_enabled: bool
    daily_report_theme_color: str
    daily_report_include_sections: list[str]
    daily_report_ai_prompt: str
    database_url: str


class SettingsUpdate(BaseModel):
    evaluator_model: str | None = None
    default_interval_seconds: int | None = Field(default=None, ge=10)
    default_timeout_seconds: int | None = Field(default=None, ge=1)
    default_failure_threshold: int | None = Field(default=None, ge=1)
    alert_cooldown_minutes: int | None = Field(default=None, ge=1)
    daily_report_enabled: bool | None = None
    daily_report_hour: int | None = Field(default=None, ge=0, le=23)
    daily_report_minute: int | None = Field(default=None, ge=0, le=59)
    daily_report_ai_summary_enabled: bool | None = None
    daily_report_theme_color: str | None = None
    daily_report_include_sections: list[str] | None = None
    daily_report_ai_prompt: str | None = None


class EvaluatorTestOut(BaseModel):
    status: str
    passed: bool
    reason: str
    model: str


class DashboardSummary(BaseModel):
    total_checks: int
    enabled_checks: int
    healthy_checks: int
    failing_checks: int
    unknown_checks: int
    availability: float
    model_total: int
    model_unmatched: int
    recent_runs: list[CheckRunOut]
    recent_alerts: list[AlertEventOut]


class SampleAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    logical_name: str
    version: int
    filename: str
    content_type: str | None = None
    file_path: str
    size_bytes: int
    description: str | None = None
    sample_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EvaluatorPromptBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: int = Field(default=1, ge=1)
    active: bool = True
    prompt_template: str = Field(min_length=1)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class EvaluatorPromptCreate(EvaluatorPromptBase):
    pass


class EvaluatorPromptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    version: int | None = Field(default=None, ge=1)
    active: bool | None = None
    prompt_template: str | None = Field(default=None, min_length=1)
    output_schema: dict[str, Any] | None = None


class EvaluatorPromptOut(EvaluatorPromptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class GoldenSetBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    new_api_instance_id: int | None = None
    model_name: str = Field(min_length=1, max_length=255)
    check_type: CheckType
    enabled: bool = True
    evaluator_prompt_id: int | None = None
    evaluator_config: dict[str, Any] = Field(default_factory=dict)


class GoldenSetCreate(GoldenSetBase):
    pass


class GoldenSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    new_api_instance_id: int | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=255)
    check_type: CheckType | None = None
    enabled: bool | None = None
    evaluator_prompt_id: int | None = None
    evaluator_config: dict[str, Any] | None = None


class GoldenSetOut(GoldenSetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class GoldenCaseBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    sample_asset_id: int | None = None
    input_config: dict[str, Any] = Field(default_factory=dict)
    expected_config: dict[str, Any] = Field(default_factory=dict)


class GoldenCaseCreate(GoldenCaseBase):
    pass


class GoldenCaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    sample_asset_id: int | None = None
    input_config: dict[str, Any] | None = None
    expected_config: dict[str, Any] | None = None


class GoldenCaseOut(GoldenCaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    golden_set_id: int
    created_at: datetime
    updated_at: datetime


class GoldenRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    golden_set_id: int
    case_id: int
    status: str
    duration_ms: int
    response_summary: str | None = None
    error: str | None = None
    score: float | None = None
    confidence: float | None = None
    rule_result: dict[str, Any]
    ai_result: dict[str, Any]
    created_at: datetime


class GoldenSetDetail(GoldenSetOut):
    cases: list[GoldenCaseOut] = Field(default_factory=list)


class TrendBucket(BaseModel):
    label: str
    total: int
    success: int
    failure: int
    availability: float
    error_rate: float
    p50_ms: float | None = None
    p90_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None


class TrendSummary(BaseModel):
    windows: dict[str, TrendBucket]
    current_failures: list[dict[str, Any]]
    golden: dict[str, Any]
