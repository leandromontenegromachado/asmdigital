"""fix synthetic evaluation email domain

Revision ID: 20260428_0009
Revises: 20260427_0008
Create Date: 2026-04-28 01:15:00

"""
from alembic import op


revision = "20260428_0009"
down_revision = "20260427_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE employees
        SET email = replace(email, '@evaluation.local', '@evaluation.asmdigital.com')
        WHERE email LIKE '%@evaluation.local'
    """)
    op.execute("""
        UPDATE reviews_360
        SET evaluated_email = replace(evaluated_email, '@evaluation.local', '@evaluation.asmdigital.com')
        WHERE evaluated_email LIKE '%@evaluation.local'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE reviews_360
        SET evaluated_email = replace(evaluated_email, '@evaluation.asmdigital.com', '@evaluation.local')
        WHERE evaluated_email LIKE '%@evaluation.asmdigital.com'
    """)
    op.execute("""
        UPDATE employees
        SET email = replace(email, '@evaluation.asmdigital.com', '@evaluation.local')
        WHERE email LIKE '%@evaluation.asmdigital.com'
    """)
