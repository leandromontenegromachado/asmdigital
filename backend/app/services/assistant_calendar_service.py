from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings


class CalendarProvider:
    def suggest_slots(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        raise NotImplementedError

    def create_meeting(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class SimulatedCalendarProvider(CalendarProvider):
    def suggest_slots(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        date_text = payload.get("date") or datetime.now().date().isoformat()
        duration = int(payload.get("duration_minutes") or 30)
        preferred = str(payload.get("preferred_period") or "").lower()
        starts = ["09:00", "10:30", "14:00"]
        if "tarde" in preferred:
            starts = ["14:00", "15:00", "16:00"]
        if "manha" in preferred or "manhã" in preferred:
            starts = ["09:00", "10:00", "11:00"]
        slots = []
        for start in starts:
            start_dt = datetime.fromisoformat(f"{date_text}T{start}:00")
            end_dt = start_dt + timedelta(minutes=duration)
            slots.append({"start": start_dt.isoformat(), "end": end_dt.isoformat()})
        return slots

    def create_meeting(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "simulated",
            "reason": "Microsoft Graph nao configurado.",
            "meeting_url": f"{settings.app_public_url.rstrip('/')}/assistant/actions",
            "payload": payload,
        }


class MicrosoftGraphCalendarProvider(CalendarProvider):
    def __init__(self) -> None:
        self.tenant_id = settings.graph_tenant_id
        self.client_id = settings.graph_client_id
        self.client_secret = settings.graph_client_secret

    @property
    def configured(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret)

    def _token(self) -> str:
        if not self.configured:
            raise RuntimeError("Microsoft Graph credentials not configured")
        response = httpx.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=20,
            verify=settings.ai_http_verify_ssl,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def suggest_slots(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        # Free/busy policies vary by tenant. Keep deterministic fallback until Graph permissions are configured.
        return SimulatedCalendarProvider().suggest_slots(payload)

    def create_meeting(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured or not settings.graph_default_organizer_email:
            return SimulatedCalendarProvider().create_meeting(payload)

        token = self._token()
        attendees = [
            {
                "emailAddress": {"address": item["email"], "name": item.get("name") or item["email"]},
                "type": "required",
            }
            for item in payload.get("participants", [])
            if item.get("email")
        ]
        start = payload.get("selected_slot", {}).get("start") or payload.get("start")
        end = payload.get("selected_slot", {}).get("end") or payload.get("end")
        event_payload = {
            "subject": payload.get("title") or "Reuniao ASM Digital",
            "body": {"contentType": "HTML", "content": payload.get("description") or "Reuniao criada pelo ASM Digital."},
            "start": {"dateTime": start, "timeZone": settings.scheduler_timezone},
            "end": {"dateTime": end, "timeZone": settings.scheduler_timezone},
            "attendees": attendees,
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
        }
        response = httpx.post(
            f"https://graph.microsoft.com/v1.0/users/{settings.graph_default_organizer_email}/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event_payload,
            timeout=30,
            verify=settings.ai_http_verify_ssl,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "status": "created",
            "event_id": data.get("id"),
            "meeting_url": (data.get("onlineMeeting") or {}).get("joinUrl") or data.get("webLink"),
            "raw": data,
        }


def calendar_provider() -> CalendarProvider:
    provider = MicrosoftGraphCalendarProvider()
    return provider if provider.configured else SimulatedCalendarProvider()
