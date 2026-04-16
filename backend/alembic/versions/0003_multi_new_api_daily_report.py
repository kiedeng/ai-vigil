"""multi new-api instances and daily report settings

Revision ID: 0003_multi_new_api_daily_report
Revises: 0002_quality_samples_trends
Create Date: 2026-04-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_multi_new_api_daily_report"
down_revision: str | None = "0002_quality_samples_trends"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _unique_exists(table_name: str, unique_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(item["name"] == unique_name for item in sa.inspect(op.get_bind()).get_unique_constraints(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if _table_exists(table_name) and not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    if not _table_exists("new_api_instances"):
        op.create_table(
            "new_api_instances",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("base_url", sa.Text(), nullable=False),
            sa.Column("api_key", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_new_api_instances_name"),
        )
    _create_index_if_missing(op.f("ix_new_api_instances_id"), "new_api_instances", ["id"])
    _create_index_if_missing(op.f("ix_new_api_instances_is_default"), "new_api_instances", ["is_default"])
    _create_index_if_missing(op.f("ix_new_api_instances_name"), "new_api_instances", ["name"])

    if not _column_exists("checks", "new_api_instance_id"):
        op.add_column("checks", sa.Column("new_api_instance_id", sa.Integer(), nullable=True))
    _create_index_if_missing(op.f("ix_checks_new_api_instance_id"), "checks", ["new_api_instance_id"])

    if not _column_exists("golden_sets", "new_api_instance_id"):
        op.add_column("golden_sets", sa.Column("new_api_instance_id", sa.Integer(), nullable=True))
    _create_index_if_missing(op.f("ix_golden_sets_new_api_instance_id"), "golden_sets", ["new_api_instance_id"])

    if not _column_exists("new_api_models", "instance_id"):
        op.add_column("new_api_models", sa.Column("instance_id", sa.Integer(), nullable=True))
    _create_index_if_missing(op.f("ix_new_api_models_instance_id"), "new_api_models", ["instance_id"])
    if _unique_exists("new_api_models", "uq_new_api_models_model_id"):
        with op.batch_alter_table("new_api_models") as batch:
            batch.drop_constraint("uq_new_api_models_model_id", type_="unique")
    if not _unique_exists("new_api_models", "uq_new_api_models_instance_model"):
        with op.batch_alter_table("new_api_models") as batch:
            batch.create_unique_constraint("uq_new_api_models_instance_model", ["instance_id", "model_id"])


def downgrade() -> None:
    for table_name, column_name in [
        ("new_api_models", "instance_id"),
        ("golden_sets", "new_api_instance_id"),
        ("checks", "new_api_instance_id"),
    ]:
        if _column_exists(table_name, column_name):
            with op.batch_alter_table(table_name) as batch:
                batch.drop_column(column_name)
    if _table_exists("new_api_instances"):
        op.drop_table("new_api_instances")
