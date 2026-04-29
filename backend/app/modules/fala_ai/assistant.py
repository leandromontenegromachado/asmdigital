from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.core.config import settings


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


def _ask_gemini(question: str, user_name: str | None = None) -> str:
    if not settings.fala_ai_gemini_api_key:
        return _fallback_answer(question)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.fala_ai_gemini_model}:generateContent"
    prompt = question.strip()
    if user_name:
        prompt = f"Usuario: {user_name}\nPergunta: {prompt}"

    payload: dict[str, Any] = {
        "system_instruction": {"parts": [{"text": _build_system_instruction()}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 300,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    response = httpx.post(
        url,
        params={"key": settings.fala_ai_gemini_api_key},
        json=payload,
        timeout=settings.fala_ai_gemini_timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates") or []
    if not candidates:
        return _fallback_answer(question)
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text_chunks = [str(part.get("text") or "").strip() for part in parts if isinstance(part, dict)]
    final = " ".join(chunk for chunk in text_chunks if chunk).strip()
    return final or _fallback_answer(question)


def build_assistant_answer(question: str, *, user_name: str | None = None) -> str:
    deterministic = _deterministic_time_answer(question)
    if deterministic:
        return deterministic
    if not settings.fala_ai_assistant_enabled:
        return _fallback_answer(question)
    try:
        return _ask_gemini(question, user_name=user_name)
    except Exception:
        return _fallback_answer(question)
