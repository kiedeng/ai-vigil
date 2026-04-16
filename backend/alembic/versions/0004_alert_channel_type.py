"""alert channel type

Revision ID: 0004_alert_channel_type
Revises: 0003_multi_new_api_daily_report
Create Date: 2026-04-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_alert_channel_type"
down_revision: str | None = "0003_multi_new_api_daily_report"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("alert_channels", "channel_type"):
        op.add_column(
            "alert_channels",
            sa.Column("channel_type", sa.String(length=50), nullable=False, server_default="generic"),
        )


def downgrade() -> None:
    if _column_exists("alert_channels", "channel_type"):
        with op.batch_alter_table("alert_channels") as batch:
            batch.drop_column("channel_type")
