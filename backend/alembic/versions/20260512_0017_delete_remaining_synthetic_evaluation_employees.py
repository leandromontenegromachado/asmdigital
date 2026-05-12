"""delete remaining synthetic evaluation employees

Revision ID: 20260512_0017
Revises: 20260512_0016
Create Date: 2026-05-12 19:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_0017"
down_revision = "20260512_0016"
branch_labels = None
depends_on = None


SYNTHETIC_NAMES = (
    "RICARDO LAURINI",
    "RICARDO LAURINI SILVA",
    "SAUL SILVA",
    "SAUL SILVA DA LUZ",
)


def upgrade() -> None:
    connection = op.get_bind()
    employee_ids = [
        row.id
        for row in connection.execute(
            sa.text(
                """
                select id
                from employees
                where lower(email) like '%@evaluation.asmdigital.com'
                  and upper(name) = any(:names)
                """
            ),
            {"names": list(SYNTHETIC_NAMES)},
        )
    ]
    if not employee_ids:
        return

    for employee_id in employee_ids:
        connection.execute(
            sa.text("update reviews_360 set evaluated_id = null, updated_at = now() where evaluated_id = :employee_id"),
            {"employee_id": employee_id},
        )
        connection.execute(
            sa.text("update reviews_360 set evaluator_id = null, updated_at = now() where evaluator_id = :employee_id"),
            {"employee_id": employee_id},
        )

        for table_name in (
            "employee_rh_data",
            "performance_indicators",
            "evaluation_scores",
            "potential_scores",
            "ai_feedback_analysis",
            "evaluation_alerts",
        ):
            connection.execute(
                sa.text(f"delete from {table_name} where employee_id = :employee_id"),
                {"employee_id": employee_id},
            )

        connection.execute(
            sa.text("update notifications set employee_id = null where employee_id = :employee_id"),
            {"employee_id": employee_id},
        )
        connection.execute(
            sa.text("update management_events set responsible_id = null where responsible_id = :employee_id"),
            {"employee_id": employee_id},
        )
        connection.execute(
            sa.text("update pending_items set responsible_id = null where responsible_id = :employee_id"),
            {"employee_id": employee_id},
        )
        connection.execute(
            sa.text("update employees set manager_id = null where manager_id = :employee_id"),
            {"employee_id": employee_id},
        )
        connection.execute(sa.text("delete from employees where id = :employee_id"), {"employee_id": employee_id})


def downgrade() -> None:
    # Data deletion cannot be safely reversed.
    pass
