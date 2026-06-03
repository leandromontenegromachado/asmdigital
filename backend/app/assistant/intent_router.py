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
    GET_EVALUATION_360 = "get_evaluation_360"
    ANALYZE_REDMINE_PROJECT = "analyze_redmine_project"
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

EVALUATION_STATUS_ACTION_ALIASES = {
    "consult",
    "consult_status",
    "status",
    "get_status",
    "get_employee_evaluation",
    "get_360_evaluation",
    "consult_evaluation_360",
    "evaluation_status",
    "employee_evaluation_status",
}

MEETING_CREATE_ACTION_ALIASES = {
    "schedule",
    "schedule_meeting",
    "create",
    "create_meeting",
    "book",
    "book_meeting",
    "agenda",
    "agendar",
}

PROJECT_ADVISOR_ACTION_ALIASES = {
    "analyze",
    "analyze_project",
    "analyze_projects",
    "consult",
    "consult_project",
    "consult_projects",
    "list_projects",
    "query_project",
    "query_projects",
    "query_redmine_project",
    "query_redmine_projects",
    "consult_redmine_project",
    "consult_redmine_projects",
}


def interpret_command(text: str, db: Session | None = None, knowledge_context: str | None = None) -> AssistantPlan:
    fallback = deterministic_plan(text)

    ai_plan, routing_metadata = _interpret_with_ai(text, db, knowledge_context=knowledge_context)
    if ai_plan and ai_plan.confidence >= 0.65:
        normalized_ai_plan = _normalize_plan(ai_plan)
        return _with_routing_metadata(normalized_ai_plan, {**routing_metadata, "decision": "ai"})

    fallback_reason = "ai_low_confidence" if ai_plan else routing_metadata.get("reason") or "ai_unavailable"
    fallback_metadata = {
        **routing_metadata,
        "decision": "fallback",
        "fallback_reason": fallback_reason,
    }
    if ai_plan:
        fallback_metadata["ai_plan"] = ai_plan.model_dump()
    return _with_routing_metadata(fallback, fallback_metadata)


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

    if (
        normalized in {"ajuda", "help", "/help"}
        or "o que voce consegue fazer" in normalized
        or "o que vc consegue fazer" in normalized
        or "o que voce pode fazer" in normalized
        or "o que vc pode fazer" in normalized
        or "o que mais voce pode fazer" in normalized
        or "o que mais vc pode fazer" in normalized
        or "o que mais pode fazer" in normalized
    ):
        return AssistantPlan(
            message_type="system_question",
            should_execute=False,
            intent=AssistantIntent.HELP.value,
            domain="general",
            action="capabilities",
            confidence=0.98,
            answer_to_user=(
                "Posso conversar sobre o ASM Digital, explicar telas e processos com base na documentacao, "
                "consultar informacoes e preparar acoes do sistema. Quando a acao alterar dados ou disparar algo externo, "
                "eu mostro uma previa e peco confirmacao antes de executar."
            ),
            summary_for_user="Vou listar as funcionalidades que consigo operar.",
            permission_required="funcionario",
        )

    if _looks_like_capability_question(normalized):
        return AssistantPlan(
            message_type="capability_question",
            should_execute=False,
            intent="capability_question",
            domain=_capability_domain(normalized),
            action="answer",
            confidence=0.78,
            answer_to_user=_capability_answer(normalized),
            summary_for_user="Vou responder a pergunta sem executar nenhuma acao.",
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

    if "avaliacao 360" in normalized or ("avaliacao" in normalized and "360" in normalized):
        employee_name = _evaluation_employee_from_text(text)
        return AssistantPlan(
            intent=AssistantIntent.GET_EVALUATION_360.value,
            domain="evaluation",
            action="status",
            confidence=0.88,
            extracted_params={"employee_name": employee_name, "text": text},
            missing_params=[] if employee_name else ["employee_name"],
            summary_for_user="Vou consultar a avaliacao 360 do funcionario informado.",
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
                "source": "last_report" if "ultimo relatorio" in normalized or "ultimo relatÃ³rio" in normalized else None,
                "channel": "email" if "email" in normalized or "e-mail" in normalized else None,
            },
            summary_for_user="Vou preparar o envio de notificacao para confirmacao.",
            risk_level="medium",
            permission_required="manager",
        )

    if _looks_like_project_advisor_request(normalized):
        project_id = _project_id_from_advisor_text(text)
        is_project_collection = _looks_like_project_collection_request(normalized)
        if is_project_collection:
            project_id = None
        missing_params = [] if is_project_collection else ([] if project_id else ["project_id"])
        return AssistantPlan(
            intent=AssistantIntent.ANALYZE_REDMINE_PROJECT.value,
            domain="project_advisor",
            action="analyze",
            requires_confirmation=False,
            confidence=0.86,
            extracted_params={"project_id": project_id, "days_stale": _days_stale_from_text(text)},
            missing_params=missing_params,
            summary_for_user="Vou avaliar o projeto no Redmine em modo somente leitura.",
            permission_required="funcionario",
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


def _interpret_with_ai(text: str, db: Session | None, knowledge_context: str | None = None) -> tuple[AssistantPlan | None, dict[str, Any]]:
    metadata: dict[str, Any] = {
        "source": "assistant_orchestrator",
        "feature_key": "assistant_orchestrator",
    }
    try:
        model = resolve_ai_model(db, "assistant_orchestrator")
        metadata.update(
            {
                "model_name": getattr(model, "name", None),
                "provider": getattr(model, "provider", None),
                "model_id": getattr(model, "model_id", None),
            }
        )
        if not isinstance(model.api_key, str) or not model.api_key.strip():
            metadata["reason"] = "missing_api_key"
            return None, metadata
        raw = generate_ai_text(
            model,
            system_instruction=(
                "Voce e o orquestrador conversacional do Assistente ASM Digital e responde apenas JSON valido. "
                "Campos obrigatorios: message_type, should_execute, answer_to_user, intent, domain, action, "
                "requires_confirmation, confidence, extracted_params, missing_params, summary_for_user, "
                "risk_level, permission_required. "
                "Mantenha valores curtos. answer_to_user deve ser null quando should_execute=true. "
                "summary_for_user deve ter no maximo uma frase curta. extracted_params deve conter apenas parametros objetivos. "
                "message_type deve ser um de: greeting, system_question, capability_question, knowledge_question, "
                "read_query, action_request, action_correction, confirmation, cancellation, unknown. "
                "should_execute=false para saudacoes, perguntas, duvidas, perguntas de capacidade como 'consegue...', "
                "'voce pode...', 'como faco...', ou conversas sem pedido claro de executar. Nesses casos preencha "
                "answer_to_user com uma resposta util e curta. "
                "should_execute=true quando o usuario pedir o resultado de uma acao ou consulta operacional. "
                "Pedidos na forma 'pode fazer', 'pode analisar', 'pode consultar', 'pode verificar' ou equivalente, "
                "seguidos de um objeto de negocio concreto, devem ser action_request e should_execute=true. "
                "Perguntas sobre capacidade, como se o sistema tem ou consegue fazer algo em geral, devem ser "
                "capability_question e should_execute=false. "
                "Dominios validos: reports_ai, reports_redmine, project_advisor, routines, notifications, employees, "
                "management_events, pending_items, evaluation, chefia, connectors, meetings, general. "
                "Escolha domain e action pela intencao, nao por palavra-chave isolada. "
                "Use project_advisor/analyze para consulta, verificacao ou analise somente leitura de projetos Redmine, "
                "incluindo analise de risco, saude, diagnostico, sinais de atraso, demandas sem atualizacao e prioridades. "
                "O project_advisor nunca pode criar, editar, comentar, atribuir, fechar ou alterar demandas no Redmine. "
                "Quando houver contexto recente de uma analise project_advisor e o usuario perguntar quais/listar/mostrar "
                "demandas de um sinal, risco, grupo ou metrica ja citada nessa analise, trate como continuacao operacional "
                "e escolha reports_redmine/run_report com os filtros inferidos do contexto. "
                "Exemplos de filtros inferiveis por significado, nao por frase fixa: atraso/vencimento, prioridade alta, "
                "responsavel, ausencia de atualizacao/movimentacao por N dias, status e projeto. "
                "Inclua em extracted_params um texto de consulta claro para o relatorio e, quando possivel, project_ids, "
                "owner, status, days_stale ou risk_title. "
                "Use reports_redmine/run_report quando o usuario pedir gerar, executar ou criar uma nova consulta/relatorio "
                "de demandas Redmine que produza uma execucao de relatorio. "
                "Use reports_ai/list apenas quando o usuario pedir relatorios recentes, historico ou relatorios existentes. "
                "Se o usuario negar relatorio e pedir agente Redmine ou consulta de projetos, prefira project_advisor/analyze. "
                "Consultas somente leitura devem ter requires_confirmation=false. "
                "Marque requires_confirmation=true para qualquer acao que altere dados ou dispare efeitos externos. "
                "Use a base de conhecimento fornecida para escolher melhor dominio e acao, mas nunca invente execucao fora dos dominios validos."
            ),
            prompt=json.dumps({"text": text, "knowledge_context": knowledge_context or ""}, ensure_ascii=False),
            json_response=True,
            max_tokens=1800,
        )
        metadata["raw_response"] = raw
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = _sanitize_ai_plan_payload(parsed)
            plan = AssistantPlan(**parsed)
            metadata["confidence"] = plan.confidence
            return plan, metadata
        metadata["reason"] = "invalid_json_shape"
    except Exception as exc:  # noqa: BLE001
        metadata["reason"] = "ai_error"
        metadata["error"] = str(exc)
    return None, metadata


def _sanitize_ai_plan_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    data = dict(parsed)
    if not isinstance(data.get("permission_required"), str) or not data.get("permission_required"):
        data["permission_required"] = "funcionario"
    if not isinstance(data.get("risk_level"), str) or not data.get("risk_level"):
        data["risk_level"] = "low"
    if not isinstance(data.get("missing_params"), list):
        data["missing_params"] = []
    if not isinstance(data.get("extracted_params"), dict):
        data["extracted_params"] = {}
    if not isinstance(data.get("confidence"), (int, float)):
        data["confidence"] = 0.0
    return data


def _normalize_plan(plan: AssistantPlan) -> AssistantPlan:
    domain = (plan.domain or "general").strip().lower()
    action = (plan.action or "unknown").strip().lower()
    params = dict(plan.extracted_params or {})
    original_action = action
    risk_level = plan.risk_level
    permission_required = plan.permission_required

    if domain in {"reports_redmine", "reports_ai"}:
        if action in REPORT_RUN_ACTION_ALIASES:
            action = "run_report"
        elif action in REPORT_LIST_ACTION_ALIASES:
            action = "list"
    elif domain == "evaluation" and action in EVALUATION_STATUS_ACTION_ALIASES:
        action = "status"
    elif domain == "meetings" and action in MEETING_CREATE_ACTION_ALIASES:
        action = "create"
        if plan.intent in {AssistantIntent.UNKNOWN.value, "schedule_meeting", "schedule"}:
            plan = plan.model_copy(update={"intent": AssistantIntent.CREATE_MEETING.value})
    elif domain == "project_advisor" and (plan.should_execute or action != "answer"):
        action = "analyze"
        params["read_only"] = True
        params["read_only_enforced"] = True
        risk_level = "low"
        permission_required = "funcionario"
        plan = plan.model_copy(update={"intent": AssistantIntent.ANALYZE_REDMINE_PROJECT.value})

    if original_action != action:
        params.setdefault("requested_action", original_action)

    should_execute = bool(plan.should_execute)
    if plan.message_type in {"greeting", "system_question", "capability_question", "knowledge_question"}:
        should_execute = False

    requires_confirmation = bool(should_execute and (plan.requires_confirmation or (domain, action) in CONFIRMATION_ACTIONS))
    if domain == "project_advisor" and action == "analyze":
        requires_confirmation = False
    return plan.model_copy(
        update={
            "domain": domain,
            "action": action,
            "extracted_params": params,
            "should_execute": should_execute,
            "requires_confirmation": requires_confirmation,
            "risk_level": risk_level,
            "permission_required": permission_required,
        }
    )


def _with_routing_metadata(plan: AssistantPlan, metadata: dict[str, Any]) -> AssistantPlan:
    current = dict(plan.routing_metadata or {})
    return plan.model_copy(update={"routing_metadata": {**current, **metadata}})


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().strip().split())


def _first_int(text: str) -> int | None:
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else None


def _evaluation_employee_from_text(text: str) -> str | None:
    patterns = [
        r"(?:avaliacao|avalia[cÃ§][aÃ£]o)\s*360\s+(?:do|da|de)\s+(.+)$",
        r"\b360\s+(?:do|da|de)\s+(.+)$",
        r"\b(?:do|da|de)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = re.split(
                r"\s+(?:no|na|em)\s+(?:ciclo|periodo|per[iÃ­]odo)\b",
                match.group(1).strip(" .?"),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return value[:160].strip(" .?") or None
    return None


def _comment_from_text(text: str) -> str | None:
    match = re.search(r"coment[aÃ¡]rio\s*:\s*(.+)$", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(" .")
    return None


def _employee_params(text: str) -> dict[str, Any]:
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
    email = email_match.group(0).lower() if email_match else None
    without_email = text.replace(email, "") if email else text
    name_match = re.search(r"(?:cadastre|cadastrar|crie|adicionar|inclua)\s+(.+?)(?:\s+como\s+funcion[aÃ¡]rio|\s+do\s+setor|\s+com\s+e-mail|$)", without_email, flags=re.IGNORECASE)
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
        r"\b(?:respons[aÃ¡]vel|atribu[iÃ­]do para|usuario|usu[aÃ¡]rio)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            owner = re.split(
                r"\s+(?:no|na|do|da)\s+(?:redmine|relat[oÃ³]rio)\b",
                match.group(1).strip(" ."),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return owner[:120].strip(" .") or None
    return None


def _template_id_from_text(text: str) -> int | None:
    match = re.search(r"(?:template|modelo|relatorio|relat[oÃ³]rio)\s*#?\s*(\d+)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _looks_like_capability_question(normalized: str) -> bool:
    prefixes = (
        "consegue",
        "vc consegue",
        "voce consegue",
        "vocÃª consegue",
        "pode",
        "vc pode",
        "voce pode",
        "vocÃª pode",
        "sabe",
        "da para",
        "dÃ¡ para",
        "e possivel",
        "Ã© possivel",
        "Ã© possÃ­vel",
    )
    direct_markers = (
        "me liste",
        "me listar",
        "me mostra",
        "me mostrar",
        "me traga",
        "me trazer",
        "consulte ",
        "consultar ",
        "consulta ",
        "liste ",
        "listar ",
        "rode ",
        "execute ",
        "crie ",
        "cadastre ",
        "envie ",
        "resolva ",
        "agende ",
    )
    return normalized.startswith(prefixes) and not any(marker in normalized for marker in direct_markers)


def _capability_domain(normalized: str) -> str:
    if any(word in normalized for word in ("agendar", "agenda", "reuniao", "reuniÃ£o")):
        return "meetings"
    if "360" in normalized or "avaliacao" in normalized:
        return "evaluation"
    if _looks_like_project_advisor_request(normalized):
        return "project_advisor"
    if "redmine" in normalized or "relatorio" in normalized or "demandas" in normalized:
        return "reports_redmine"
    if "rotina" in normalized:
        return "routines"
    if "notificacao" in normalized or "notificar" in normalized:
        return "notifications"
    return "general"


def _capability_answer(normalized: str) -> str:
    domain = _capability_domain(normalized)
    if domain == "meetings":
        return "Sim, posso ajudar com agendamento de reunioes. Como voce perguntou, nao vou criar nada agora. Para iniciar, peca diretamente: agende uma reuniao amanha as 10h com Maria sobre demandas atrasadas."
    if domain == "evaluation":
        return "Sim, posso consultar Avaliacao 360 por funcionario e resumir ciclo, notas, feedbacks, analise IA e alertas quando houver dados."
    if domain == "reports_redmine":
        return "Sim, posso consultar dados do Redmine em modo somente leitura ou preparar relatorios. Consulta direta de projetos usa o agente consultivo; nova execucao de relatorio pede confirmacao antes de rodar."
    if domain == "routines":
        return "Sim, posso consultar rotinas e preparar criacao, edicao ou execucao. Acoes com impacto exigem confirmacao."
    if domain == "notifications":
        return "Sim, posso preparar notificacoes. Envio de notificacao sempre exige previa e confirmacao."
    return "Sim, posso responder duvidas sobre o ASM Digital e operar funcionalidades do sistema quando voce pedir uma acao especifica."



def _looks_like_project_advisor_request(normalized: str) -> bool:
    advisor_markers = (
        "avalie o projeto",
        "avalie os projetos",
        "avaliar o projeto",
        "avaliar os projetos",
        "analise o projeto",
        "analise os projetos",
        "analisar o projeto",
        "analisar os projetos",
        "consulte o projeto",
        "consulte os projetos",
        "consultar o projeto",
        "consultar os projetos",
        "consulta o projeto",
        "consulta os projetos",
        "diagnostico do projeto",
        "diagnóstico do projeto",
        "risco do projeto",
        "riscos do projeto",
        "saude do projeto",
        "saúde do projeto",
        "agente do redmine consulte",
        "agente redmine consulte",
    )
    if any(marker in normalized for marker in advisor_markers) and "redmine" in normalized:
        return True
    return (
        "redmine" in normalized
        and "projetos" in normalized
        and any(word in normalized for word in ("consulte", "consultar", "consulta", "analise", "analisar", "avalie", "avaliar"))
    )


def _looks_like_project_collection_request(normalized: str) -> bool:
    collection_markers = (
        "os projetos",
        "projetos do meu setor",
        "todos os projetos",
        "meus projetos",
        "projetos configurados",
    )
    return any(marker in normalized for marker in collection_markers)


def _project_id_from_advisor_text(text: str) -> str | None:
    patterns = [
        r"\bprojeto\s+([\w\-.]+)",
        r"\bproject\s+([\w\-.]+)",
        r"\bredmine\s+([\w\-.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,")
            if value.lower() not in {"no", "na", "do", "da", "de", "redmine"}:
                return value[:120]
    return None


def _days_stale_from_text(text: str) -> int:
    match = re.search(r"(\d+)\s+dias?\s+sem\s+atualiza", text, flags=re.IGNORECASE)
    if match:
        return max(1, min(int(match.group(1)), 90))
    return 7



