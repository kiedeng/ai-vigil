"""model performance comparisons

Revision ID: 0008_model_performance_comparisons
Revises: 0007_model_performance_tests
Create Date: 2026-05-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_model_performance_comparisons"
down_revision: str | None = "0007_model_performance_tests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _table_exists("model_performance_comparisons"):
        op.create_table(
            "model_performance_comparisons",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("dataset_config", sa.JSON(), nullable=False),
            sa.Column("load_config", sa.JSON(), nullable=False),
            sa.Column("threshold_config", sa.JSON(), nullable=False),
            sa.Column("extra_args", sa.JSON(), nullable=False),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("chart_data", sa.JSON(), nullable=False),
            sa.Column("analysis", sa.JSON(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_model_performance_comparisons_id"), "model_performance_comparisons", ["id"])
        op.create_index(op.f("ix_model_performance_comparisons_name"), "model_performance_comparisons", ["name"])
        op.create_index(op.f("ix_model_performance_comparisons_status"), "model_performance_comparisons", ["status"])

    if not _table_exists("model_performance_comparison_items"):
        op.create_table(
            "model_performance_comparison_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("comparison_id", sa.Integer(), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("new_api_instance_id", sa.Integer(), nullable=True),
            sa.Column("model_name", sa.String(length=255), nullable=False),
            sa.Column("endpoint", sa.String(length=100), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("test_id", sa.Integer(), nullable=True),
            sa.Column("run_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["comparison_id"], ["model_performance_comparisons.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["new_api_instance_id"], ["new_api_instances.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_model_performance_comparison_items_id"), "model_performance_comparison_items", ["id"])
        op.create_index(
            op.f("ix_model_performance_comparison_items_comparison_id"),
            "model_performance_comparison_items",
            ["comparison_id"],
        )
        op.create_index(
            op.f("ix_model_performance_comparison_items_new_api_instance_id"),
            "model_performance_comparison_items",
            ["new_api_instance_id"],
        )
        op.create_index(
            op.f("ix_model_performance_comparison_items_model_name"),
            "model_performance_comparison_items",
            ["model_name"],
        )
        op.create_index(
            op.f("ix_model_performance_comparison_items_status"),
            "model_performance_comparison_items",
            ["status"],
        )


def downgrade() -> None:
    if _table_exists("model_performance_comparison_items"):
        op.drop_table("model_performance_comparison_items")
    if _table_exists("model_performance_comparisons"):
        op.drop_table("model_performance_comparisons")
