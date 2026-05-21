from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AiModel, AiModelAssignment


AI_MODEL_FEATURES: dict[str, str] = {
    "default": "Padrao do sistema",
    "reports": "Relatorios por IA",
    "evaluation": "Avaliacao e relatorios 360",
    "chefia": "ChefIA",
    "assistant": "Assistente de Gestao",
}

SUPPORTED_PROVIDERS: dict[str, str] = {
    "google_gemini": "Google Gemini",
    "openrouter": "OpenRouter",
}


@dataclass(frozen=True)
class ResolvedAiModel:
    feature_key: str
    name: str
    provider: str
    model_id: str
    api_key: str | None
    timeout_seconds: int

    @property
    def provider_supported(self) -> bool:
        return self.provider in SUPPORTED_PROVIDERS


def provider_label(provider: str) -> str:
    return SUPPORTED_PROVIDERS.get(provider, provider)


def _api_key_from_env(api_key_env: str | None, provider: str) -> str | None:
    env_name = api_key_env.strip() if isinstance(api_key_env, str) else ""
    if env_name:
        value = os.getenv(env_name)
        if value:
            return value
    if provider == "openrouter":
        return settings.openrouter_api_key
    return settings.fala_ai_gemini_api_key


def _fallback_config(feature_key: str) -> ResolvedAiModel:
    return ResolvedAiModel(
        feature_key=feature_key,
        name="Gemini 3 Flash Preview",
        provider="google_gemini",
        model_id=settings.fala_ai_gemini_model,
        api_key=settings.fala_ai_gemini_api_key,
        timeout_seconds=settings.fala_ai_gemini_timeout_seconds,
    )


def resolve_ai_model(db: Session | None, feature_key: str) -> ResolvedAiModel:
    key = (feature_key or "default").strip().lower()
    if db is None:
        return _fallback_config(key)

    model: AiModel | None = None
    assignment = (
        db.query(AiModelAssignment)
        .join(AiModel)
        .filter(AiModelAssignment.feature_key == key, AiModel.is_active.is_(True))
        .first()
    )
    if not assignment and key != "default":
        assignment = (
            db.query(AiModelAssignment)
            .join(AiModel)
            .filter(AiModelAssignment.feature_key == "default", AiModel.is_active.is_(True))
            .first()
        )
    if assignment:
        model = assignment.model
    if not model:
        model = (
            db.query(AiModel)
            .filter(AiModel.is_active.is_(True), AiModel.is_default.is_(True))
            .order_by(AiModel.id.asc())
            .first()
        )
    if not model:
        return _fallback_config(key)

    return ResolvedAiModel(
        feature_key=key,
        name=model.name,
        provider=model.provider,
        model_id=model.model_id,
        api_key=_api_key_from_env(model.api_key_env, model.provider),
        timeout_seconds=settings.fala_ai_gemini_timeout_seconds,
    )


def _extract_gemini_text(data: dict[str, Any]) -> str:
    return (
        (data.get("candidates") or [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )


def _extract_openrouter_text(data: dict[str, Any]) -> str:
    message = (data.get("choices") or [{}])[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict):
                chunks.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(chunk for chunk in chunks if chunk)
    return str(content)


def _openrouter_requires_reasoning_enabled(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        message = str((response.json().get("error") or {}).get("message") or "").lower()
    except ValueError:
        message = response.text.lower()
    return "reasoning is mandatory" in message or "cannot be disabled" in message


def generate_ai_text(
    model: ResolvedAiModel,
    *,
    system_instruction: str,
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2500,
    json_response: bool = False,
) -> str:
    if not model.api_key:
        raise RuntimeError("AI model API key is not configured")

    if model.provider == "google_gemini":
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if json_response:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model.model_id}:generateContent",
            headers={"x-goog-api-key": model.api_key},
            json=payload,
            timeout=model.timeout_seconds,
            verify=settings.ai_http_verify_ssl,
        )
        response.raise_for_status()
        return _extract_gemini_text(response.json())

    if model.provider == "openrouter":
        effective_system_instruction = system_instruction
        if json_response:
            effective_system_instruction = (
                f"{system_instruction}\n\n"
                "Responda com um unico objeto JSON valido. "
                "Nao use markdown, crases ou comentarios. "
                "Nao adicione texto antes ou depois do JSON."
            )
        headers = {
            "Authorization": f"Bearer {model.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.openrouter_site_url or settings.app_public_url,
            "X-Title": settings.openrouter_app_name or settings.app_name,
        }
        payload = {
            "model": model.model_id,
            "messages": [
                {"role": "system", "content": effective_system_instruction},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_response:
            payload["reasoning"] = {"effort": "none", "exclude": True}
        response = httpx.post(
            f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=model.timeout_seconds,
            verify=settings.ai_http_verify_ssl,
        )
        if _openrouter_requires_reasoning_enabled(response):
            payload.pop("reasoning", None)
            response = httpx.post(
                f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=model.timeout_seconds,
                verify=settings.ai_http_verify_ssl,
            )
        response.raise_for_status()
        return _extract_openrouter_text(response.json())

    raise RuntimeError(f"AI provider not supported: {model.provider}")
