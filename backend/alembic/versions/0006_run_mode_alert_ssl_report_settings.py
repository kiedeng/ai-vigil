"""run mode alert ssl report settings

Revision ID: 0006_run_mode_alert_ssl_report_settings
Revises: 0005_default_check_timeout_120
Create Date: 2026-04-17 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_run_mode_alert_ssl_report_settings"
down_revision: str | None = "0005_default_check_timeout_120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("check_runs", "run_mode"):
        op.add_column("check_runs", sa.Column("run_mode", sa.String(length=20), nullable=False, server_default="manual"))
        op.create_index(op.f("ix_check_runs_run_mode"), "check_runs", ["run_mode"], unique=False)
    if not _column_exists("alert_channels", "verify_ssl"):
        op.add_column("alert_channels", sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.true()))
    if not _column_exists("alert_channels", "ca_bundle_path"):
        op.add_column("alert_channels", sa.Column("ca_bundle_path", sa.Text(), nullable=True))


def downgrade() -> None:
    if _column_exists("alert_channels", "ca_bundle_path"):
        with op.batch_alter_table("alert_channels") as batch:
            batch.drop_column("ca_bundle_path")
    if _column_exists("alert_channels", "verify_ssl"):
        with op.batch_alter_table("alert_channels") as batch:
            batch.drop_column("verify_ssl")
    if _column_exists("check_runs", "run_mode"):
        with op.batch_alter_table("check_runs") as batch:
            batch.drop_index(op.f("ix_check_runs_run_mode"))
            batch.drop_column("run_mode")
