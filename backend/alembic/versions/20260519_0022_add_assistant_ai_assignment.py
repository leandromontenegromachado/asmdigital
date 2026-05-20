"""add assistant ai assignment

Revision ID: 20260519_0022
Revises: 20260519_0021
Create Date: 2026-05-19 12:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260519_0022"
down_revision = "20260519_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    default_model_id = connection.execute(
        sa.text(
            """
            select model_id
            from ai_model_assignments
            where feature_key = 'default'
            limit 1
            """
        )
    ).scalar()
    if default_model_id is None:
        default_model_id = connection.execute(
            sa.text(
                """
                select id
                from ai_models
                where is_active = true
                order by is_default desc, id asc
                limit 1
                """
            )
        ).scalar()
    if default_model_id is not None:
        connection.execute(
            sa.text(
                """
                insert into ai_model_assignments (feature_key, model_id)
                values ('assistant', :model_id)
                on conflict (feature_key) do nothing
                """
            ),
            {"model_id": default_model_id},
        )


def downgrade() -> None:
    op.execute("delete from ai_model_assignments where feature_key = 'assistant'")
