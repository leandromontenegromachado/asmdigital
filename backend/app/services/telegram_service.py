from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


def send_telegram_message(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        return
    httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=20,
    ).raise_for_status()


def delete_telegram_webhook(drop_pending_updates: bool = False) -> None:
    if not settings.telegram_bot_token:
        return
    httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/deleteWebhook",
        json={"drop_pending_updates": drop_pending_updates},
        timeout=20,
        verify=settings.ai_http_verify_ssl,
    ).raise_for_status()


def get_telegram_updates(offset: int | None = None, timeout_seconds: int = 25) -> list[dict[str, Any]]:
    if not settings.telegram_bot_token:
        return []
    params: dict[str, Any] = {
        "timeout": timeout_seconds,
        "allowed_updates": ["message"],
    }
    if offset is not None:
        params["offset"] = offset
    response = httpx.get(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates",
        params=params,
        timeout=timeout_seconds + 10,
        verify=settings.ai_http_verify_ssl,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram getUpdates failed: {data}")
    return list(data.get("result") or [])


def download_telegram_file(file_id: str) -> tuple[bytes, str]:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    file_response = httpx.get(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/getFile",
        params={"file_id": file_id},
        timeout=20,
    )
    file_response.raise_for_status()
    file_path = file_response.json()["result"]["file_path"]
    download_response = httpx.get(
        f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}",
        timeout=30,
    )
    download_response.raise_for_status()
    return download_response.content, file_path


def transcribe_voice(file_bytes: bytes, filename: str, prompt: str | None = None) -> str:
    provider = (settings.assistant_speech_provider or "local").strip().lower()
    if provider == "local":
        response = httpx.post(
            settings.assistant_local_speech_url,
            files={"file": (filename or "voice.ogg", file_bytes, "audio/ogg")},
            data={"language": "pt", "prompt": prompt or ""},
            timeout=180,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return str(data.get("text") or "").strip()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured for voice transcription")
    response = httpx.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        files={"file": (filename or "voice.ogg", file_bytes, "audio/ogg")},
        data={"model": settings.assistant_speech_model, "language": "pt", "prompt": prompt or ""},
        timeout=60,
        verify=settings.ai_http_verify_ssl,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return str(data.get("text") or "").strip()
