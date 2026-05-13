from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.services.ai_model_service import ResolvedAiModel, generate_ai_text

logger = logging.getLogger(__name__)


def _now_local() -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.scheduler_timezone))
    except (ZoneInfoNotFoundError, ValueError):
        return datetime.now()


def _deterministic_time_answer(question: str) -> str | None:
    text = (question or "").strip().lower()
    now = _now_local()
    if "que dia" in text and "hoje" in text:
        return f"Hoje e {now.strftime('%d/%m/%Y')}."
    if "que horas" in text or "hora agora" in text:
        return f"Agora sao {now.strftime('%H:%M')}."
    return None


def _fallback_answer(question: str) -> str:
    deterministic = _deterministic_time_answer(question)
    if deterministic:
        return deterministic
    text = (question or "").strip().lower()
    if "bom dia" in text:
        return "Bom dia! Se for resposta da enquete, responde com 'sim' ou reage com like."
    if "ajuda" in text or "help" in text:
        return "Posso ajudar com respostas, lembretes e duvidas gerais."
    return "Entendi sua pergunta. No momento estou em modo basico, mas posso te orientar no que precisar."


def _build_system_instruction() -> str:
    domain = (settings.fala_ai_assistant_domain or "geral").strip().lower()
    if domain == "procergs":
        return (
            "Voce e o assistente interno ChefIA da PROCERGS. "
            "Responda apenas sobre assuntos de trabalho da PROCERGS, de forma objetiva e amigavel. "
            "Se a pergunta fugir desse escopo, diga que no momento voce esta limitado a duvidas da PROCERGS."
        )
    return (
        "Voce e o assistente interno ChefIA de uma equipe corporativa. "
        "Nao fale sobre culinaria ou receitas. "
        "Responda duvidas dos funcionarios sobre trabalho, processos internos, uso do sistema e rotina. "
        "Responda de forma amigavel, direta e curta em portugues do Brasil."
    )


def _ask_gemini(question: str, user_name: str | None = None, model: ResolvedAiModel | None = None) -> str:
    if model:
        if not model.api_key or not model.provider_supported:
            return _fallback_answer(question)
    elif not settings.fala_ai_gemini_api_key:
        return _fallback_answer(question)

    prompt = question.strip()
    if user_name:
        prompt = f"Usuario: {user_name}\nPergunta: {prompt}"

    resolved = model or ResolvedAiModel(
        feature_key="chefia",
        name="Gemini",
        provider="google_gemini",
        model_id=settings.fala_ai_gemini_model,
        api_key=settings.fala_ai_gemini_api_key,
        timeout_seconds=settings.fala_ai_gemini_timeout_seconds,
    )
    final = generate_ai_text(
        resolved,
        system_instruction=_build_system_instruction(),
        prompt=prompt,
        temperature=0.4,
        max_tokens=300,
        json_response=False,
    ).strip()
    return final or _fallback_answer(question)


def build_assistant_answer(
    question: str,
    *,
    user_name: str | None = None,
    model: ResolvedAiModel | None = None,
) -> str:
    deterministic = _deterministic_time_answer(question)
    if deterministic:
        return deterministic
    if not settings.fala_ai_assistant_enabled:
        return _fallback_answer(question)
    try:
        return _ask_gemini(question, user_name=user_name, model=model)
    except Exception as exc:  # noqa: BLE001
        logger.warning("chefia_assistant_external_ai_failed", extra={"error": str(exc), "model": getattr(model, "model_id", None)})
        return _fallback_answer(question)
