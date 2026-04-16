"""quality regression, evaluator prompts, and samples

Revision ID: 0002_quality_samples_trends
Revises: 0001_initial
Create Date: 2026-04-16 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_quality_samples_trends"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if _table_exists(table_name) and not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    if not _table_exists("sample_assets"):
        op.create_table(
            "sample_assets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("logical_name", sa.String(length=200), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=True),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sample_metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(op.f("ix_sample_assets_id"), "sample_assets", ["id"])
    _create_index_if_missing(op.f("ix_sample_assets_logical_name"), "sample_assets", ["logical_name"])

    if not _table_exists("evaluator_prompts"):
        op.create_table(
            "evaluator_prompts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("prompt_template", sa.Text(), nullable=False),
            sa.Column("output_schema", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", "version", name="uq_evaluator_prompts_name_version"),
        )
    _create_index_if_missing(op.f("ix_evaluator_prompts_id"), "evaluator_prompts", ["id"])
    _create_index_if_missing(op.f("ix_evaluator_prompts_name"), "evaluator_prompts", ["name"])

    if not _table_exists("golden_sets"):
        op.create_table(
            "golden_sets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("model_name", sa.String(length=255), nullable=False),
            sa.Column("check_type", sa.String(length=50), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("evaluator_prompt_id", sa.Integer(), nullable=True),
            sa.Column("evaluator_config", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(op.f("ix_golden_sets_check_type"), "golden_sets", ["check_type"])
    _create_index_if_missing(op.f("ix_golden_sets_id"), "golden_sets", ["id"])
    _create_index_if_missing(op.f("ix_golden_sets_model_name"), "golden_sets", ["model_name"])
    _create_index_if_missing(op.f("ix_golden_sets_name"), "golden_sets", ["name"])

    if not _table_exists("golden_cases"):
        op.create_table(
            "golden_cases",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("golden_set_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("sample_asset_id", sa.Integer(), nullable=True),
            sa.Column("input_config", sa.JSON(), nullable=False),
            sa.Column("expected_config", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["golden_set_id"], ["golden_sets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(op.f("ix_golden_cases_golden_set_id"), "golden_cases", ["golden_set_id"])
    _create_index_if_missing(op.f("ix_golden_cases_id"), "golden_cases", ["id"])

    if not _table_exists("golden_runs"):
        op.create_table(
            "golden_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("golden_set_id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.Column("response_summary", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("rule_result", sa.JSON(), nullable=False),
            sa.Column("ai_result", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["golden_cases.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(op.f("ix_golden_runs_case_id"), "golden_runs", ["case_id"])
    _create_index_if_missing(op.f("ix_golden_runs_golden_set_id"), "golden_runs", ["golden_set_id"])
    _create_index_if_missing(op.f("ix_golden_runs_id"), "golden_runs", ["id"])
    _create_index_if_missing(op.f("ix_golden_runs_status"), "golden_runs", ["status"])


def downgrade() -> None:
    for table_name in ["golden_runs", "golden_cases", "golden_sets", "evaluator_prompts", "sample_assets"]:
        if _table_exists(table_name):
            op.drop_table(table_name)
