"""dedupe synthetic evaluation employees

Revision ID: 20260512_0016
Revises: 20260508_0015
Create Date: 2026-05-12 18:45:00.000000
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from alembic import op
import sqlalchemy as sa


revision = "20260512_0016"
down_revision = "20260508_0015"
branch_labels = None
depends_on = None


SYNTHETIC_DOMAIN = "@evaluation.asmdigital.com"


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value.strip().upper())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized.casefold()).strip()


def _is_probable_same_person(left: str | None, right: str | None) -> bool:
    left_normalized = _normalize(left)
    right_normalized = _normalize(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True

    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    min_token_count = min(len(left_tokens), len(right_tokens))
    if min_token_count >= 2 and len(left_tokens & right_tokens) / min_token_count >= 0.85:
        return True

    compact_left = left_normalized.replace(" ", "")
    compact_right = right_normalized.replace(" ", "")
    return SequenceMatcher(None, compact_left, compact_right).ratio() >= 0.88


def _find_merge_pairs(connection) -> list[tuple[int, int]]:
    rows = connection.execute(sa.text("select id, name, email from employees order by id")).mappings().all()
    synthetic_rows = [row for row in rows if (row["email"] or "").lower().endswith(SYNTHETIC_DOMAIN)]
    real_rows = [row for row in rows if not (row["email"] or "").lower().endswith(SYNTHETIC_DOMAIN)]

    pairs: list[tuple[int, int]] = []
    used_old_ids: set[int] = set()
    for old in synthetic_rows:
        matches = [candidate for candidate in real_rows if _is_probable_same_person(candidate["name"], old["name"])]
        if len(matches) != 1:
            continue
        old_id = int(old["id"])
        new_id = int(matches[0]["id"])
        if old_id != new_id and old_id not in used_old_ids:
            pairs.append((old_id, new_id))
            used_old_ids.add(old_id)
    return pairs


def _merge_employee(connection, old_id: int, new_id: int) -> None:
    # Preserve useful notification/profile fields from the synthetic row only when the real row lacks them.
    connection.execute(
        sa.text(
            """
            update employees target
            set
                teams_user_id = coalesce(target.teams_user_id, source.teams_user_id),
                matricula = coalesce(target.matricula, source.matricula),
                cargo = coalesce(target.cargo, source.cargo),
                setor = coalesce(target.setor, source.setor),
                department = coalesce(target.department, source.department),
                position = coalesce(target.position, source.position),
                manager_id = coalesce(target.manager_id, nullif(source.manager_id, :new_id)),
                recebe_notificacao = target.recebe_notificacao or source.recebe_notificacao,
                participa_avaliacao = target.participa_avaliacao or source.participa_avaliacao,
                updated_at = now()
            from employees source
            where target.id = :new_id and source.id = :old_id
            """
        ),
        {"old_id": old_id, "new_id": new_id},
    )

    connection.execute(
        sa.text(
            """
            update reviews_360
            set evaluated_id = :new_id,
                evaluated_email = employee.email,
                evaluated_name = employee.name,
                updated_at = now()
            from employees employee
            where reviews_360.evaluated_id = :old_id and employee.id = :new_id
            """
        ),
        {"old_id": old_id, "new_id": new_id},
    )
    connection.execute(
        sa.text(
            """
            update reviews_360
            set evaluator_id = :new_id,
                evaluator_email = employee.email,
                evaluator_name = employee.name,
                updated_at = now()
            from employees employee
            where reviews_360.evaluator_id = :old_id and employee.id = :new_id
            """
        ),
        {"old_id": old_id, "new_id": new_id},
    )

    for table_name in (
        "employee_rh_data",
        "performance_indicators",
        "evaluation_scores",
        "potential_scores",
        "ai_feedback_analysis",
    ):
        connection.execute(
            sa.text(
                f"""
                delete from {table_name} old_row
                using {table_name} new_row
                where old_row.employee_id = :old_id
                  and new_row.employee_id = :new_id
                  and old_row.cycle_id = new_row.cycle_id
                """
            ),
            {"old_id": old_id, "new_id": new_id},
        )
        connection.execute(
            sa.text(f"update {table_name} set employee_id = :new_id where employee_id = :old_id"),
            {"old_id": old_id, "new_id": new_id},
        )

    for table_name in ("evaluation_alerts", "notifications"):
        connection.execute(
            sa.text(f"update {table_name} set employee_id = :new_id where employee_id = :old_id"),
            {"old_id": old_id, "new_id": new_id},
        )

    for table_name in ("management_events", "pending_items"):
        connection.execute(
            sa.text(f"update {table_name} set responsible_id = :new_id where responsible_id = :old_id"),
            {"old_id": old_id, "new_id": new_id},
        )

    connection.execute(
        sa.text("update employees set manager_id = :new_id where manager_id = :old_id"),
        {"old_id": old_id, "new_id": new_id},
    )
    connection.execute(sa.text("delete from employees where id = :old_id"), {"old_id": old_id})


def upgrade() -> None:
    connection = op.get_bind()
    for old_id, new_id in _find_merge_pairs(connection):
        _merge_employee(connection, old_id, new_id)


def downgrade() -> None:
    # Data consolidation cannot be safely reversed.
    pass
