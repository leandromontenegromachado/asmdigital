import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

_ASSISTANT_ROUTER_PATH = Path(__file__).resolve().parents[1] / "app" / "api" / "routers" / "assistant.py"
_ASSISTANT_SPEC = importlib.util.spec_from_file_location("assistant_router_under_test", _ASSISTANT_ROUTER_PATH)
assistant = importlib.util.module_from_spec(_ASSISTANT_SPEC)
assert _ASSISTANT_SPEC and _ASSISTANT_SPEC.loader
_ASSISTANT_SPEC.loader.exec_module(assistant)


class _FakeRequest:
    async def json(self):
        return {"message": {"chat": {"id": "123"}, "text": "ola"}}


def test_telegram_webhook_rejects_when_secret_is_not_configured(monkeypatch):
    monkeypatch.setattr(assistant.settings, "telegram_webhook_secret", None)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            assistant.telegram_webhook(
                _FakeRequest(),
                x_telegram_bot_api_secret_token=None,
                db=MagicMock(),
            )
        )

    assert exc_info.value.status_code == 503


def test_telegram_webhook_rejects_invalid_secret(monkeypatch):
    monkeypatch.setattr(assistant.settings, "telegram_webhook_secret", "expected-secret")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            assistant.telegram_webhook(
                _FakeRequest(),
                x_telegram_bot_api_secret_token="wrong-secret",
                db=MagicMock(),
            )
        )

    assert exc_info.value.status_code == 403


def test_telegram_webhook_processes_valid_secret(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(assistant.settings, "telegram_webhook_secret", "expected-secret")
    process_mock = MagicMock(return_value={"ok": True})
    monkeypatch.setattr(assistant, "process_telegram_update", process_mock)

    result = asyncio.run(
        assistant.telegram_webhook(
            _FakeRequest(),
            x_telegram_bot_api_secret_token="expected-secret",
            db=db,
        )
    )

    assert result == {"ok": True}
    process_mock.assert_called_once_with({"message": {"chat": {"id": "123"}, "text": "ola"}}, db)
