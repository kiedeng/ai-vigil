from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NewApiInstance(Base, TimestampMixin):
    __tablename__ = "new_api_instances"
    __table_args__ = (UniqueConstraint("name", name="uq_new_api_instances_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    models: Mapped[list["NewApiModel"]] = relationship(back_populates="instance")

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key)


class Check(Base, TimestampMixin):
    __tablename__ = "checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    new_api_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("new_api_instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    request_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    validation_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ai_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    state: Mapped["CheckState | None"] = relationship(
        back_populates="check", cascade="all, delete-orphan", uselist=False
    )
    runs: Mapped[list["CheckRun"]] = relationship(back_populates="check", cascade="all, delete-orphan")


class CheckRun(Base, TimestampMixin):
    __tablename__ = "check_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    check_id: Mapped[int] = mapped_column(ForeignKey("checks.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    check: Mapped[Check] = relationship(back_populates="runs")


class CheckState(Base, TimestampMixin):
    __tablename__ = "check_states"
    __table_args__ = (UniqueConstraint("check_id", name="uq_check_states_check_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    check_id: Mapped[int] = mapped_column(ForeignKey("checks.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False, index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    check: Mapped[Check] = relationship(back_populates="state")


class NewApiModel(Base, TimestampMixin):
    __tablename__ = "new_api_models"
    __table_args__ = (UniqueConstraint("instance_id", "model_id", name="uq_new_api_models_instance_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("new_api_instances.id", ondelete="CASCADE"), nullable=True, index=True
    )
    model_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), default="unmatched", nullable=False)
    check_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    matched_rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    instance: Mapped[NewApiInstance | None] = relationship(back_populates="models")

    @property
    def instance_name(self) -> str | None:
        return self.instance.name if self.instance else None


class ModelRule(Base, TimestampMixin):
    __tablename__ = "model_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    match_type: Mapped[str] = mapped_column(String(20), default="glob", nullable=False)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    request_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    validation_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AlertChannel(Base, TimestampMixin):
    __tablename__ = "alert_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)


class AlertEvent(Base, TimestampMixin):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    check_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base, TimestampMixin):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("key", name="uq_settings_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MetricSnapshot(Base, TimestampMixin):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    availability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    healthy_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failing_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SampleAsset(Base, TimestampMixin):
    __tablename__ = "sample_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    logical_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class EvaluatorPrompt(Base, TimestampMixin):
    __tablename__ = "evaluator_prompts"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_evaluator_prompts_name_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class GoldenSet(Base, TimestampMixin):
    __tablename__ = "golden_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_api_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("new_api_instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evaluator_prompt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluator_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    cases: Mapped[list["GoldenCase"]] = relationship(back_populates="golden_set", cascade="all, delete-orphan")


class GoldenCase(Base, TimestampMixin):
    __tablename__ = "golden_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    golden_set_id: Mapped[int] = mapped_column(ForeignKey("golden_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sample_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    expected_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    golden_set: Mapped[GoldenSet] = relationship(back_populates="cases")
    runs: Mapped[list["GoldenRun"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class GoldenRun(Base, TimestampMixin):
    __tablename__ = "golden_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    golden_set_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("golden_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rule_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ai_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    case: Mapped[GoldenCase] = relationship(back_populates="runs")
