"""model performance tests

Revision ID: 0007_model_performance_tests
Revises: 0006_run_mode_alert_ssl_report_settings
Create Date: 2026-05-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_model_performance_tests"
down_revision: str | None = "0006_run_mode_alert_ssl_report_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _table_exists("model_performance_tests"):
        op.create_table(
            "model_performance_tests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("new_api_instance_id", sa.Integer(), nullable=True),
            sa.Column("model_name", sa.String(length=255), nullable=False),
            sa.Column("endpoint", sa.String(length=100), nullable=False),
            sa.Column("dataset_config", sa.JSON(), nullable=False),
            sa.Column("load_config", sa.JSON(), nullable=False),
            sa.Column("threshold_config", sa.JSON(), nullable=False),
            sa.Column("extra_args", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["new_api_instance_id"], ["new_api_instances.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_model_performance_tests_id"), "model_performance_tests", ["id"], unique=False)
        op.create_index(op.f("ix_model_performance_tests_name"), "model_performance_tests", ["name"], unique=False)
        op.create_index(
            op.f("ix_model_performance_tests_new_api_instance_id"),
            "model_performance_tests",
            ["new_api_instance_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_model_performance_tests_model_name"),
            "model_performance_tests",
            ["model_name"],
            unique=False,
        )

    if not _table_exists("model_performance_runs"):
        op.create_table(
            "model_performance_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("test_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("output_dir", sa.Text(), nullable=True),
            sa.Column("log_path", sa.Text(), nullable=True),
            sa.Column("command", sa.JSON(), nullable=False),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("chart_data", sa.JSON(), nullable=False),
            sa.Column("analysis", sa.JSON(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["test_id"], ["model_performance_tests.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_model_performance_runs_id"), "model_performance_runs", ["id"], unique=False)
        op.create_index(op.f("ix_model_performance_runs_test_id"), "model_performance_runs", ["test_id"], unique=False)
        op.create_index(op.f("ix_model_performance_runs_status"), "model_performance_runs", ["status"], unique=False)


def downgrade() -> None:
    if _table_exists("model_performance_runs"):
        op.drop_table("model_performance_runs")
    if _table_exists("model_performance_tests"):
        op.drop_table("model_performance_tests")
