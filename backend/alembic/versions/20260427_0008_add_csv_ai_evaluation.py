"""add csv import and ai qualitative analysis to evaluation

Revision ID: 20260427_0008
Revises: 20260427_0007
Create Date: 2026-04-27 16:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260427_0008"
down_revision = "20260427_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="UPLOADED"),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("column_mapping_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_evaluation_imports_id", "evaluation_imports", ["id"])
    op.create_index("ix_evaluation_imports_cycle_id", "evaluation_imports", ["cycle_id"])
    op.create_index("ix_evaluation_imports_status", "evaluation_imports", ["status"])

    op.create_table(
        "evaluation_import_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_id", sa.Integer(), sa.ForeignKey("evaluation_imports.id"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_evaluation_import_rows_id", "evaluation_import_rows", ["id"])
    op.create_index("ix_evaluation_import_rows_import_id", "evaluation_import_rows", ["import_id"])
    op.create_index("ix_evaluation_import_rows_status", "evaluation_import_rows", ["status"])

    op.add_column("reviews_360", sa.Column("import_id", sa.Integer(), nullable=True))
    op.add_column("reviews_360", sa.Column("import_row_id", sa.Integer(), nullable=True))
    op.add_column("reviews_360", sa.Column("evaluator_email", sa.String(length=200), nullable=True))
    op.add_column("reviews_360", sa.Column("evaluator_name", sa.String(length=200), nullable=True))
    op.add_column("reviews_360", sa.Column("evaluated_email", sa.String(length=200), nullable=True))
    op.add_column("reviews_360", sa.Column("evaluated_name", sa.String(length=200), nullable=True))
    op.add_column("reviews_360", sa.Column("general_score", sa.Float(), nullable=True))
    op.add_column("reviews_360", sa.Column("communication_score", sa.Float(), nullable=True))
    op.add_column("reviews_360", sa.Column("teamwork_score", sa.Float(), nullable=True))
    op.add_column("reviews_360", sa.Column("commitment_score", sa.Float(), nullable=True))
    op.add_column("reviews_360", sa.Column("autonomy_score", sa.Float(), nullable=True))
    op.add_column("reviews_360", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column("reviews_360", sa.Column("problem_solving_score", sa.Float(), nullable=True))
    op.add_column("reviews_360", sa.Column("strengths_comment", sa.Text(), nullable=True))
    op.add_column("reviews_360", sa.Column("improvement_comment", sa.Text(), nullable=True))
    op.add_column("reviews_360", sa.Column("general_comment", sa.Text(), nullable=True))
    op.alter_column("reviews_360", "evaluator_id", nullable=True)
    op.alter_column("reviews_360", "evaluated_id", nullable=True)
    op.alter_column("reviews_360", "score", nullable=True)
    op.create_foreign_key("fk_reviews_360_import_id", "reviews_360", "evaluation_imports", ["import_id"], ["id"])
    op.create_foreign_key("fk_reviews_360_import_row_id", "reviews_360", "evaluation_import_rows", ["import_row_id"], ["id"])
    op.create_index("ix_reviews_360_import_id", "reviews_360", ["import_id"])
    op.create_index("ix_reviews_360_import_row_id", "reviews_360", ["import_row_id"])

    op.execute("UPDATE reviews_360 SET general_score = score WHERE general_score IS NULL")

    op.create_table(
        "ai_feedback_analysis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("evaluation_cycles.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attention_points_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recurring_themes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("qualitative_alerts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_feedback", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=120), nullable=True),
        sa.Column("raw_response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cycle_id", "employee_id", name="uq_ai_feedback_analysis_cycle_employee"),
    )
    op.create_index("ix_ai_feedback_analysis_id", "ai_feedback_analysis", ["id"])
    op.create_index("ix_ai_feedback_analysis_cycle_id", "ai_feedback_analysis", ["cycle_id"])
    op.create_index("ix_ai_feedback_analysis_employee_id", "ai_feedback_analysis", ["employee_id"])
    op.create_index("ix_ai_feedback_analysis_status", "ai_feedback_analysis", ["status"])


def downgrade() -> None:
    op.drop_table("ai_feedback_analysis")
    op.drop_index("ix_reviews_360_import_row_id", table_name="reviews_360")
    op.drop_index("ix_reviews_360_import_id", table_name="reviews_360")
    op.drop_constraint("fk_reviews_360_import_row_id", "reviews_360", type_="foreignkey")
    op.drop_constraint("fk_reviews_360_import_id", "reviews_360", type_="foreignkey")
    for column in [
        "general_comment",
        "improvement_comment",
        "strengths_comment",
        "problem_solving_score",
        "quality_score",
        "autonomy_score",
        "commitment_score",
        "teamwork_score",
        "communication_score",
        "general_score",
        "evaluated_name",
        "evaluated_email",
        "evaluator_name",
        "evaluator_email",
        "import_row_id",
        "import_id",
    ]:
        op.drop_column("reviews_360", column)
    op.alter_column("reviews_360", "score", nullable=False)
    op.alter_column("reviews_360", "evaluated_id", nullable=False)
    op.alter_column("reviews_360", "evaluator_id", nullable=False)
    op.drop_table("evaluation_import_rows")
    op.drop_table("evaluation_imports")
