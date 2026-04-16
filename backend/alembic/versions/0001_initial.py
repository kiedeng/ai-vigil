"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("failure_threshold", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("request_config", sa.JSON(), nullable=False),
        sa.Column("validation_config", sa.JSON(), nullable=False),
        sa.Column("ai_config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checks_id"), "checks", ["id"], unique=False)
    op.create_index(op.f("ix_checks_model_name"), "checks", ["model_name"], unique=False)
    op.create_index(op.f("ix_checks_name"), "checks", ["name"], unique=False)
    op.create_index(op.f("ix_checks_type"), "checks", ["type"], unique=False)

    op.create_table(
        "check_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("check_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("ai_result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["check_id"], ["checks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_check_runs_check_id"), "check_runs", ["check_id"], unique=False)
    op.create_index(op.f("ix_check_runs_id"), "check_runs", ["id"], unique=False)
    op.create_index(op.f("ix_check_runs_status"), "check_runs", ["status"], unique=False)

    op.create_table(
        "check_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("check_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_id", sa.Integer(), nullable=True),
        sa.Column("alert_open", sa.Boolean(), nullable=False),
        sa.Column("last_alert_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["check_id"], ["checks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("check_id", name="uq_check_states_check_id"),
    )
    op.create_index(op.f("ix_check_states_check_id"), "check_states", ["check_id"], unique=False)
    op.create_index(op.f("ix_check_states_id"), "check_states", ["id"], unique=False)
    op.create_index(op.f("ix_check_states_status"), "check_states", ["status"], unique=False)

    op.create_table(
        "new_api_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("check_type", sa.String(length=50), nullable=True),
        sa.Column("matched_rule_id", sa.Integer(), nullable=True),
        sa.Column("check_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", name="uq_new_api_models_model_id"),
    )
    op.create_index(op.f("ix_new_api_models_id"), "new_api_models", ["id"], unique=False)
    op.create_index(op.f("ix_new_api_models_model_id"), "new_api_models", ["model_id"], unique=False)

    op.create_table(
        "model_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("pattern", sa.String(length=255), nullable=False),
        sa.Column("match_type", sa.String(length=20), nullable=False),
        sa.Column("check_type", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("request_config", sa.JSON(), nullable=False),
        sa.Column("validation_config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_rules_id"), "model_rules", ["id"], unique=False)

    op.create_table(
        "alert_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("secret", sa.Text(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_channels_id"), "alert_channels", ["id"], unique=False)

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=True),
        sa.Column("check_id", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_events_channel_id"), "alert_events", ["channel_id"], unique=False)
    op.create_index(op.f("ix_alert_events_check_id"), "alert_events", ["check_id"], unique=False)
    op.create_index(op.f("ix_alert_events_id"), "alert_events", ["id"], unique=False)

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_settings_key"),
    )
    op.create_index(op.f("ix_settings_id"), "settings", ["id"], unique=False)
    op.create_index(op.f("ix_settings_key"), "settings", ["key"], unique=False)

    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("availability", sa.Float(), nullable=False),
        sa.Column("total_checks", sa.Integer(), nullable=False),
        sa.Column("healthy_checks", sa.Integer(), nullable=False),
        sa.Column("failing_checks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_metric_snapshots_id"), "metric_snapshots", ["id"], unique=False)


def downgrade() -> None:
    op.drop_table("metric_snapshots")
    op.drop_table("settings")
    op.drop_table("alert_events")
    op.drop_table("alert_channels")
    op.drop_table("model_rules")
    op.drop_table("new_api_models")
    op.drop_table("check_states")
    op.drop_table("check_runs")
    op.drop_table("checks")

