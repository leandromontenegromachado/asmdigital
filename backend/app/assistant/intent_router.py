from __future__ import annotations

import json
import re
import unicodedata
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.assistant.schemas import AssistantPlan
from app.services.ai_model_service import generate_ai_text, resolve_ai_model


class AssistantIntent(StrEnum):
    HELP = "help"
    LIST_LATE_PROJECTS = "list_late_projects"
    LIST_ROUTINES = "list_routines"
    LIST_PENDING_ITEMS = "list_pending_items"
    LIST_EMPLOYEES = "list_employees"
    RUN_REPORT = "run_report"
    SEND_NOTIFICATION = "send_notification"
    CREATE_EMPLOYEE = "create_employee"
    RESOLVE_PENDING_ITEM = "resolve_pending_item"
    CREATE_ROUTINE = "create_routine"
    CREATE_MEETING = "create_meeting"
    UNKNOWN = "unknown"


CONFIRMATION_ACTIONS = {
    ("reports_redmine", "run_report"),
    ("reports_ai", "run_report"),
    ("notifications", "send"),
    ("employees", "create"),
    ("pending_items", "resolve"),
    ("pending_items", "ignore"),
    ("pending_items", "escalate"),
    ("routines", "create"),
    ("routines", "update"),
    ("routines", "delete"),
    ("meetings", "create"),
    ("connectors", "update"),
    ("ai_models", "update"),
}

REPORT_RUN_ACTION_ALIASES = {
    "execute_report",
    "create_demands_report",
    "generate_demands_report",
    "generate_report",
    "run_redmine_report",
    "run_ai_report",
    "list_open_demands",
    "list_open_demands_by_user",
    "list_demands_by_user",
    "list_redmine_demands",
    "query_redmine_demands",
}

REPORT_LIST_ACTION_ALIASES = {
    "list_reports",
    "list_recent_reports",
    "recent_reports",
}


def interpret_command(text: str, db: Session | None = None) -> AssistantPlan:
    ai_plan = _interpret_with_ai(text, db)
    fallback = deterministic_plan(text)
    if ai_plan and ai_plan.confidence >= 0.65 and ai_plan.intent != AssistantIntent.UNKNOWN.value:
        return _normalize_plan(ai_plan)
    return fallback


def detect_intent(text: str) -> AssistantIntent:
    intent = deterministic_plan(text).intent
    try:
        return AssistantIntent(intent)
    except ValueError:
        return AssistantIntent.UNKNOWN


def deterministic_plan(text: str) -> AssistantPlan:
    normalized = _normalize(text)
    if not normalized:
        return AssistantPlan()

    if normalized in {"ajuda", "help", "/help"} or "o que voce consegue fazer" in normalized or "o que voce pode fazer" in normalized:
        return AssistantPlan(
            intent=AssistantIntent.HELP.value,
            domain="general",
            action="capabilities",
            confidence=0.98,
            summary_for_user="Vou listar as funcionalidades que consigo operar.",
            permission_required="funcionario",
        )

    if any(word in normalized for word in ("reuniao", "agenda", "agende", "marque", "marcar")):
        return AssistantPlan(
            intent=AssistantIntent.CREATE_MEETING.value,
            domain="meetings",
            action="create",
            requires_confirmation=True,
            confidence=0.86,
            extracted_params={"text": text},
            summary_for_user="Vou preparar uma proposta de agendamento para confirmacao.",
            risk_level="medium",
            permission_required="funcionario",
        )

    if any(word in normalized for word in ("rotina", "rotinas")):
        if any(word in normalized for word in ("crie", "criar", "cadastre", "nova")):
            return AssistantPlan(
                intent=AssistantIntent.CREATE_ROUTINE.value,
                domain="routines",
                action="create",
                requires_confirmation=True,
                confidence=0.82,
                extracted_params=_routine_params(text),
                missing_params=[],
                summary_for_user="Vou criar uma rotina com a agenda e tarefas identificadas.",
                risk_level="medium",
                permission_required="manager",
            )
        return AssistantPlan(
            intent=AssistantIntent.LIST_ROUTINES.value,
            domain="routines",
            action="list",
            confidence=0.9,
            extracted_params={"status": "active" if "ativa" in normalized or "ativas" in normalized else None},
            summary_for_user="Vou listar as rotinas cadastradas.",
            permission_required="funcionario",
        )

    if any(word in normalized for word in ("pendencia", "pendencias")):
        pending_id = _first_int(normalized)
        if any(word in normalized for word in ("resolva", "resolver", "tratado", "concluir")):
            return AssistantPlan(
                intent=AssistantIntent.RESOLVE_PENDING_ITEM.value,
                domain="pending_items",
                action="resolve",
                requires_confirmation=True,
                confidence=0.86,
                extracted_params={"pending_item_id": pending_id, "comment": _comment_from_text(text)},
                missing_params=[] if pending_id else ["pending_item_id"],
                summary_for_user="Vou resolver a pendencia indicada com o comentario informado.",
                risk_level="medium",
                permission_required="manager",
            )
        return AssistantPlan(
            intent=AssistantIntent.LIST_PENDING_ITEMS.value,
            domain="pending_items",
            action="list",
            confidence=0.85,
            extracted_params={"status": "open"},
            summary_for_user="Vou listar pendencias abertas.",
            permission_required="funcionario",
        )

    if any(word in normalized for word in ("funcionario", "funcionarios", "colaborador", "colaboradores")):
        if any(word in normalized for word in ("cadastre", "cadastrar", "crie", "adicionar", "inclua")):
            params = _employee_params(text)
            missing = [field for field in ("name", "email") if not params.get(field)]
            return AssistantPlan(
                intent=AssistantIntent.CREATE_EMPLOYEE.value,
                domain="employees",
                action="create",
                requires_confirmation=True,
                confidence=0.84,
                extracted_params=params,
                missing_params=missing,
                summary_for_user="Vou cadastrar o funcionario com os dados identificados.",
                risk_level="medium",
                permission_required="admin",
            )
        return AssistantPlan(
            intent=AssistantIntent.LIST_EMPLOYEES.value,
            domain="employees",
            action="list",
            confidence=0.82,
            summary_for_user="Vou consultar funcionarios cadastrados.",
            permission_required="funcionario",
        )

    if any(word in normalized for word in ("notifique", "notificar", "envie notificacao", "enviar notificacao", "avise")):
        return AssistantPlan(
            intent=AssistantIntent.SEND_NOTIFICATION.value,
            domain="notifications",
            action="send",
            requires_confirmation=True,
            confidence=0.84,
            extracted_params={
                "target": "responsaveis" if "respons" in normalized else None,
                "source": "last_report" if "ultimo relatorio" in normalized or "ultimo relatório" in normalized else None,
                "channel": "email" if "email" in normalized or "e-mail" in normalized else None,
            },
            summary_for_user="Vou preparar o envio de notificacao para confirmacao.",
            risk_level="medium",
            permission_required="manager",
        )

    if "redmine" in normalized and any(word in normalized for word in ("demanda", "demandas", "chamado", "chamados")):
        return AssistantPlan(
            intent=AssistantIntent.RUN_REPORT.value,
            domain="reports_redmine",
            action="run_report",
            requires_confirmation=True,
            confidence=0.82,
            extracted_params={
                "text": text,
                "owner": _owner_from_report_text(text),
                "status": "open" if any(word in normalized for word in ("aberto", "abertos", "aberta", "abertas")) else None,
                "template_id": _template_id_from_text(text),
            },
            summary_for_user="Vou preparar a consulta ao Redmine para confirmacao.",
            risk_level="medium",
            permission_required="manager",
        )

    if any(word in normalized for word in ("relatorio", "relatorios", "report")):
        if any(word in normalized for word in ("rode", "rodar", "execute", "executar", "gerar")):
            return AssistantPlan(
                intent=AssistantIntent.RUN_REPORT.value,
                domain="reports_redmine" if "redmine" in normalized or "demanda" in normalized else "reports_ai",
                action="run_report",
                requires_confirmation=True,
                confidence=0.8,
                extracted_params={"text": text, "owner": _owner_from_report_text(text), "template_id": _template_id_from_text(text)},
                summary_for_user="Vou preparar a execucao do relatorio para confirmacao.",
                risk_level="medium",
                permission_required="manager",
            )
        return AssistantPlan(
            intent="list_reports",
            domain="reports_ai",
            action="list",
            confidence=0.82,
            summary_for_user="Vou listar os relatorios recentes.",
            permission_required="funcionario",
        )

    if (
        "projetos em atraso" in normalized
        or "demandas em atraso" in normalized
        or "demandas atrasadas" in normalized
        or ("demandas" in normalized and "atrasad" in normalized)
    ):
        return AssistantPlan(
            intent=AssistantIntent.LIST_LATE_PROJECTS.value,
            domain="reports_redmine",
            action="list_late_projects",
            confidence=0.85,
            summary_for_user="Vou consultar demandas em atraso.",
            permission_required="funcionario",
        )

    return AssistantPlan(confidence=0.2)


def _interpret_with_ai(text: str, db: Session | None) -> AssistantPlan | None:
    try:
        model = resolve_ai_model(db, "assistant")
        if not isinstance(model.api_key, str) or not model.api_key.strip():
            return None
        raw = generate_ai_text(
            model,
            system_instruction=(
                "Voce interpreta comandos do Assistente ASM Digital e responde apenas JSON valido. "
                "Campos obrigatorios: intent, domain, action, requires_confirmation, confidence, "
                "extracted_params, missing_params, summary_for_user, risk_level, permission_required. "
                "Dominios validos: reports_ai, reports_redmine, routines, notifications, employees, "
                "management_events, pending_items, evaluation, chefia, connectors, meetings, general. "
                "Marque requires_confirmation=true para qualquer acao que altere dados ou dispare efeitos externos."
            ),
            prompt=json.dumps({"text": text}, ensure_ascii=False),
            json_response=True,
            max_tokens=900,
        )
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return AssistantPlan(**parsed)
    except Exception:
        return None
    return None


def _normalize_plan(plan: AssistantPlan) -> AssistantPlan:
    domain = (plan.domain or "general").strip().lower()
    action = (plan.action or "unknown").strip().lower()
    params = dict(plan.extracted_params or {})
    original_action = action

    if domain in {"reports_redmine", "reports_ai"}:
        if action in REPORT_RUN_ACTION_ALIASES:
            action = "run_report"
        elif action in REPORT_LIST_ACTION_ALIASES:
            action = "list"

    if original_action != action:
        params.setdefault("requested_action", original_action)

    requires_confirmation = bool(plan.requires_confirmation or (domain, action) in CONFIRMATION_ACTIONS)
    return plan.model_copy(
        update={
            "domain": domain,
            "action": action,
            "extracted_params": params,
            "requires_confirmation": requires_confirmation,
        }
    )


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().strip().split())


def _first_int(text: str) -> int | None:
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else None


def _comment_from_text(text: str) -> str | None:
    match = re.search(r"coment[aá]rio\s*:\s*(.+)$", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(" .")
    return None


def _employee_params(text: str) -> dict[str, Any]:
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    email = email_match.group(0).lower() if email_match else None
    without_email = text.replace(email, "") if email else text
    name_match = re.search(r"(?:cadastre|cadastrar|crie|adicionar|inclua)\s+(.+?)(?:\s+como\s+funcion[aá]rio|\s+do\s+setor|\s+com\s+e-mail|$)", without_email, flags=re.IGNORECASE)
    setor_match = re.search(r"setor\s+(.+?)(?:\s+com\s+e-mail|$)", text, flags=re.IGNORECASE)
    return {
        "name": name_match.group(1).strip(" .") if name_match else None,
        "email": email,
        "setor": setor_match.group(1).strip(" .") if setor_match else None,
    }


def _routine_params(text: str) -> dict[str, Any]:
    normalized = _normalize(text)
    cron = None
    if "sexta" in normalized and ("9h" in normalized or "9 h" in normalized):
        cron = "0 9 * * fri"
    elif "diaria" in normalized or "diario" in normalized or "todo dia" in normalized:
        cron = "0 9 * * *"
    tasks = []
    if "demandas atrasad" in normalized or "atrasadas" in normalized:
        tasks.append("redmine_report")
    return {
        "name": _routine_name_from_text(text),
        "schedule_cron": cron,
        "tasks": tasks or ["manual_review"],
        "notification_requested": "notificar" in normalized or "notifique" in normalized,
        "simulation": True,
    }


def _routine_name_from_text(text: str) -> str:
    cleaned = re.sub(r"^(crie|criar|cadastre|nova)\s+uma?\s+rotina\s*", "", text, flags=re.IGNORECASE).strip(" .")
    return cleaned[:120] or "Rotina criada pelo assistente"


def _owner_from_report_text(text: str) -> str | None:
    patterns = [
        r"\bem aberto\s+(?:do|da|de)\s+(.+)$",
        r"\babertas?\s+(?:do|da|de)\s+(.+)$",
        r"\babertos?\s+(?:do|da|de)\s+(.+)$",
        r"\b(?:respons[aá]vel|atribu[ií]do para|usuario|usu[aá]rio)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            owner = re.split(
                r"\s+(?:no|na|do|da)\s+(?:redmine|relat[oó]rio)\b",
                match.group(1).strip(" ."),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return owner[:120].strip(" .") or None
    return None


def _template_id_from_text(text: str) -> int | None:
    match = re.search(r"(?:template|modelo|relatorio|relat[oó]rio)\s*#?\s*(\d+)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None
