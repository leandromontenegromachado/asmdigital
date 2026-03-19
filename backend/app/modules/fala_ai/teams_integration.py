from __future__ import annotations

import hmac
import hashlib
from collections.abc import Mapping
from typing import Any
import unicodedata

import httpx


def validate_teams_request(raw_body: bytes, headers: Mapping[str, str], secret: str | None) -> bool:
    if not secret:
        return True

    signature = (
        headers.get("x-fala-ai-signature")
        or headers.get("X-Fala-AI-Signature")
        or headers.get("x-teams-signature")
        or headers.get("X-Teams-Signature")
    )
    if not signature:
        return False

    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(signature.strip(), expected)


def extract_teams_identity(payload: dict[str, Any]) -> dict[str, Any]:
    from_block = payload.get("from") if isinstance(payload.get("from"), dict) else {}
    user_block = from_block.get("user") if isinstance(from_block.get("user"), dict) else {}
    channel_data = payload.get("channelData") if isinstance(payload.get("channelData"), dict) else {}
    from_channel = channel_data.get("from") if isinstance(channel_data.get("from"), dict) else {}
    conversation = payload.get("conversation") if isinstance(payload.get("conversation"), dict) else {}

    def _pick(*values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    user_id_raw = _pick(
        payload.get("user_id"),
        user_block.get("id"),
        from_block.get("id"),
    )
    email = _pick(
        payload.get("user_email"),
        user_block.get("email"),
        from_block.get("email"),
        from_channel.get("email"),
        channel_data.get("email"),
        channel_data.get("userPrincipalName"),
    )
    name = _pick(
        payload.get("user_name"),
        user_block.get("displayName"),
        from_block.get("name"),
        from_channel.get("name"),
    )

    message = (
        payload.get("message")
        or payload.get("text")
        or payload.get("value")
        or ""
    )

    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFD", value or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return text.strip().lower()

    activity_type = str(payload.get("type") or "").strip().lower()
    reactions_added = payload.get("reactionsAdded") if isinstance(payload.get("reactionsAdded"), list) else []
    reaction_types = []
    for reaction in reactions_added:
        if isinstance(reaction, dict):
            reaction_type = str(reaction.get("type") or "").strip().lower()
            if reaction_type:
                reaction_types.append(reaction_type)

    normalized_message = _normalize(str(message))

    return {
        "user_id": int(user_id_raw) if str(user_id_raw).isdigit() else None,
        "email": str(email).strip().lower() if email else None,
        "name": str(name).strip() if name else None,
        "external_id": _pick(from_block.get("id"), from_channel.get("id")),
        "message": str(message).strip(),
        "normalized_message": normalized_message,
        "activity_type": activity_type,
        "reaction_types": reaction_types,
        "conversation_id": _pick(conversation.get("id")),
        "channel_id": _pick(payload.get("channelId")),
    }


def extract_bot_context(payload: dict[str, Any]) -> dict[str, str | None]:
    conversation = payload.get("conversation") if isinstance(payload.get("conversation"), dict) else {}
    recipient = payload.get("recipient") if isinstance(payload.get("recipient"), dict) else {}
    service_url = payload.get("serviceUrl")
    return {
        "service_url": str(service_url).strip() if service_url else None,
        "conversation_id": str(conversation.get("id")).strip() if conversation.get("id") else None,
        "bot_id": str(recipient.get("id")).strip() if recipient.get("id") else None,
    }


def _send_webhook_message(webhook_url: str, message: str) -> None:
    payload = {"text": message}
    response = httpx.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()


def _get_botframework_token(app_id: str, app_secret: str, tenant_id: str) -> str:
    response = httpx.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": app_secret,
            "scope": "https://api.botframework.com/.default",
        },
        timeout=20,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Bot Framework token not returned")
    return token


def _send_botframework_message(
    *,
    message: str,
    app_id: str,
    app_secret: str,
    tenant_id: str,
    service_url: str,
    conversation_id: str,
    bot_id: str | None = None,
) -> None:
    token = _get_botframework_token(app_id, app_secret, tenant_id)
    base_url = service_url.rstrip("/")
    url = f"{base_url}/v3/conversations/{conversation_id}/activities"
    payload = {
        "type": "message",
        "text": message,
        "from": {"id": bot_id or app_id},
    }
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()


def send_teams_message(
    *,
    message: str,
    webhook_url: str | None = None,
    bot_app_id: str | None = None,
    bot_app_secret: str | None = None,
    bot_tenant_id: str | None = None,
    service_url: str | None = None,
    conversation_id: str | None = None,
    bot_id: str | None = None,
) -> str:
    if webhook_url:
        _send_webhook_message(webhook_url, message)
        return "webhook"

    if bot_app_id and bot_app_secret and service_url and conversation_id:
        _send_botframework_message(
            message=message,
            app_id=bot_app_id,
            app_secret=bot_app_secret,
            tenant_id=bot_tenant_id or "botframework.com",
            service_url=service_url,
            conversation_id=conversation_id,
            bot_id=bot_id,
        )
        return "botframework"

    raise RuntimeError("No Teams delivery channel configured")
