"""raise default check timeout data

Revision ID: 0005_default_check_timeout_120
Revises: 0004_alert_channel_type
Create Date: 2026-04-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0005_default_check_timeout_120"
down_revision: str | None = "0004_alert_channel_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE checks SET timeout_seconds = 120 WHERE timeout_seconds = 30")


def downgrade() -> None:
    op.execute("UPDATE checks SET timeout_seconds = 30 WHERE timeout_seconds = 120")
