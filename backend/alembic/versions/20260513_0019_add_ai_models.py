"""add ai model registry

Revision ID: 20260513_0019
Revises: 20260512_0018
Create Date: 2026-05-13 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0019"
down_revision = "20260512_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model_id", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("api_key_env", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model_id", name="uq_ai_models_provider_model_id"),
    )
    op.create_index("ix_ai_models_id", "ai_models", ["id"], unique=False)
    op.create_index("ix_ai_models_provider", "ai_models", ["provider"], unique=False)

    op.create_table(
        "ai_model_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feature_key", sa.String(length=80), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["ai_models.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_key"),
    )
    op.create_index("ix_ai_model_assignments_id", "ai_model_assignments", ["id"], unique=False)
    op.create_index("ix_ai_model_assignments_feature_key", "ai_model_assignments", ["feature_key"], unique=False)
    op.create_index("ix_ai_model_assignments_model_id", "ai_model_assignments", ["model_id"], unique=False)

    ai_models = sa.table(
        "ai_models",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("provider", sa.String),
        sa.column("model_id", sa.String),
        sa.column("description", sa.Text),
        sa.column("api_key_env", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("is_default", sa.Boolean),
    )
    assignments = sa.table(
        "ai_model_assignments",
        sa.column("feature_key", sa.String),
        sa.column("model_id", sa.Integer),
    )

    bind = op.get_bind()
    result = bind.execute(
        ai_models.insert().values(
            name="Gemini 3 Flash Preview",
            provider="google_gemini",
            model_id="gemini-3-flash-preview",
            description="Modelo Gemini usado atualmente pelo ASM Digital.",
            api_key_env="FALA_AI_GEMINI_API_KEY",
            is_active=True,
            is_default=True,
        ).returning(ai_models.c.id)
    )
    gemini_id = result.scalar_one()
    bind.execute(
        assignments.insert(),
        [
            {"feature_key": "default", "model_id": gemini_id},
            {"feature_key": "reports", "model_id": gemini_id},
            {"feature_key": "evaluation", "model_id": gemini_id},
            {"feature_key": "chefia", "model_id": gemini_id},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_model_assignments_model_id", table_name="ai_model_assignments")
    op.drop_index("ix_ai_model_assignments_feature_key", table_name="ai_model_assignments")
    op.drop_index("ix_ai_model_assignments_id", table_name="ai_model_assignments")
    op.drop_table("ai_model_assignments")
    op.drop_index("ix_ai_models_provider", table_name="ai_models")
    op.drop_index("ix_ai_models_id", table_name="ai_models")
    op.drop_table("ai_models")
