from __future__ import annotations

import unicodedata
from enum import StrEnum


class AssistantIntent(StrEnum):
    HELP = "HELP"
    LIST_LATE_PROJECTS = "LIST_LATE_PROJECTS"
    NOTIFY_RESPONSIBLES = "NOTIFY_RESPONSIBLES"
    CREATE_MEETING = "CREATE_MEETING"
    UNKNOWN = "UNKNOWN"


def detect_intent(text: str) -> AssistantIntent:
    normalized = _normalize(text)
    if not normalized:
        return AssistantIntent.UNKNOWN
    if normalized in {"ajuda", "help", "/help"} or "o que voce pode fazer" in normalized:
        return AssistantIntent.HELP
    if any(word in normalized for word in ("reuniao", "agenda", "marcar")):
        return AssistantIntent.CREATE_MEETING
    if any(word in normalized for word in ("notificar", "avisar", "enviar mensagem")) and any(
        word in normalized for word in ("responsavel", "responsaveis", "atrasad")
    ):
        return AssistantIntent.NOTIFY_RESPONSIBLES
    if any(word in normalized for word in ("listar", "quais", "mostrar", "trazer")) and any(
        word in normalized for word in ("atrasado", "atrasados", "atrasada", "atrasadas")
    ):
        return AssistantIntent.LIST_LATE_PROJECTS
    if "projetos em atraso" in normalized or "demandas em atraso" in normalized:
        return AssistantIntent.LIST_LATE_PROJECTS
    return AssistantIntent.UNKNOWN


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().strip().split())
