from __future__ import annotations

from sqlalchemy.orm import Session

from app.assistant.actions.base import ActionResult, compact_items
from app.assistant.schemas import AssistantPlan
from app.models import Employee, User


class EmployeesAction:
    domain = "employees"

    def preview(self, db: Session, plan: AssistantPlan, user: User | None) -> dict:
        return {
            "title": "Funcionario",
            "action": plan.action,
            "params": plan.extracted_params,
            "missing_params": plan.missing_params,
            "impact": "O cadastro ficara disponivel para notificacoes, avaliacoes e agendas.",
        }

    def execute(self, db: Session, plan: AssistantPlan, user: User | None) -> ActionResult:
        if plan.action == "list":
            employees = db.query(Employee).filter(Employee.active.is_(True)).order_by(Employee.name.asc()).limit(100).all()
            items = [
                {"id": item.id, "name": item.name, "email": item.email, "setor": item.setor or item.department}
                for item in employees
            ]
            return ActionResult(message=f"Encontrei {len(items)} funcionarios ativos.", data=compact_items(items))

        if plan.action == "create":
            params = plan.extracted_params or {}
            name = str(params.get("name") or "").strip()
            email = str(params.get("email") or "").strip().lower()
            if not name or not email:
                return ActionResult(message="Faltam nome e e-mail para cadastrar o funcionario.", data={}, success=False, errors=["missing_params"])
            exists = db.query(Employee).filter(Employee.email == email).first()
            if exists:
                return ActionResult(message="Ja existe funcionario com este e-mail.", data={"id": exists.id}, success=False, errors=["email_exists"])
            employee = Employee(
                name=name,
                email=email,
                setor=params.get("setor"),
                department=params.get("setor"),
                active=True,
                recebe_notificacao=True,
                participa_avaliacao=True,
                canal_preferencial="email",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)
            return ActionResult(message=f"Funcionario {employee.name} cadastrado.", data={"id": employee.id, "name": employee.name, "email": employee.email})

        return ActionResult(message="Acao de funcionarios nao suportada.", data={}, success=False, errors=["unsupported_action"])
