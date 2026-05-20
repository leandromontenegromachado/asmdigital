from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy.orm import Session

from app.models import AssistantAction, AssistantConversation, AssistantMessage, Employee, User
from app.services.ai_model_service import generate_ai_text, resolve_ai_model
from app.services.assistant_calendar_service import calendar_provider


CONFIRM_WORDS = {"confirmo", "confirma", "confirmar", "sim", "ok", "pode confirmar"}
CANCEL_WORDS = {"cancela", "cancelar", "nao", "desiste"}


class AssistantService:
    def __init__(self, db: Session):
        self.db = db

    def bind_telegram(self, user: User, chat_id: str, username: str | None = None) -> User:
        user.telegram_chat_id = str(chat_id)
        user.telegram_username = username
        self.db.commit()
        self.db.refresh(user)
        return user

    def handle_message(
        self,
        *,
        text: str,
        channel: str,
        user: User | None = None,
        external_chat_id: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> tuple[AssistantConversation, str, AssistantAction | None]:
        conversation = self._conversation(channel=channel, user=user, external_chat_id=external_chat_id)
        self._add_message(conversation, "in", text, raw_payload or {}, "text")

        pending = self._pending_action(conversation)
        normalized = _normalize(text)
        if pending:
            pending = self._apply_message_to_pending_action(pending, text)
        if pending and any(word in normalized for word in CONFIRM_WORDS):
            result = self.confirm_action(pending)
            reply = self._confirmation_reply(result)
            self._add_message(conversation, "out", reply, {"action_id": pending.id}, "text")
            return conversation, reply, pending
        if pending and any(word in normalized for word in CANCEL_WORDS):
            pending.status = "cancelled"
            pending.result_json = {"status": "cancelled"}
            self.db.commit()
            reply = "Cancelei a acao pendente."
            self._add_message(conversation, "out", reply, {"action_id": pending.id}, "text")
            return conversation, reply, pending
        if pending and pending.status == "needs_input":
            reply = self._proposal_reply(pending)
            self._add_message(conversation, "out", reply, {"action_id": pending.id}, "text")
            return conversation, reply, pending

        parsed = self._parse_intent(text, conversation=conversation)
        if parsed.get("intent") != "schedule_meeting":
            reply = (
                "Ainda estou preparado para agendar reunioes. "
                "Exemplo: agenda uma reuniao na proxima quarta de manha com Alessandra e Anderson sobre demandas atrasadas."
            )
            self._add_message(conversation, "out", reply, {}, "text")
            return conversation, reply, None

        payload = self._meeting_payload(parsed)
        payload["participants"] = self._resolve_people(payload.get("participant_names") or [])
        payload["suggested_slots"] = calendar_provider().suggest_slots(payload)
        payload["missing_fields"] = self._missing_fields(payload)
        action = AssistantAction(
            conversation_id=conversation.id,
            user_id=user.id if user else None,
            action_type="schedule_meeting",
            status="needs_confirmation" if not payload["missing_fields"] else "needs_input",
            payload_json=payload,
            result_json={},
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        reply = self._proposal_reply(action)
        self._add_message(conversation, "out", reply, {"action_id": action.id}, "text")
        return conversation, reply, action

    def confirm_action(self, action: AssistantAction) -> AssistantAction:
        if action.status not in {"needs_confirmation", "needs_input"}:
            return action
        payload = action.payload_json or {}
        if payload.get("missing_fields"):
            action.status = "needs_input"
            action.result_json = {"status": "needs_input", "missing_fields": payload.get("missing_fields")}
            self.db.commit()
            self.db.refresh(action)
            return action
        selected_slot = payload.get("selected_slot") or (payload.get("suggested_slots") or [{}])[0]
        payload["selected_slot"] = selected_slot
        result = calendar_provider().create_meeting(payload)
        action.status = "completed" if result.get("status") in {"created", "simulated"} else "error"
        action.result_json = result
        action.confirmed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(action)
        return action

    def cancel_action(self, action: AssistantAction) -> AssistantAction:
        action.status = "cancelled"
        action.result_json = {"status": "cancelled"}
        self.db.commit()
        self.db.refresh(action)
        return action

    def _conversation(self, *, channel: str, user: User | None, external_chat_id: str | None) -> AssistantConversation:
        query = self.db.query(AssistantConversation).filter(AssistantConversation.channel == channel)
        if external_chat_id:
            conversation = query.filter(AssistantConversation.external_chat_id == str(external_chat_id)).first()
        elif user:
            conversation = query.filter(AssistantConversation.user_id == user.id).first()
        else:
            conversation = None
        if conversation:
            if user and not conversation.user_id:
                conversation.user_id = user.id
                self.db.commit()
                self.db.refresh(conversation)
            return conversation
        conversation = AssistantConversation(
            channel=channel,
            external_chat_id=external_chat_id,
            user_id=user.id if user else None,
            state_json={},
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def _add_message(self, conversation: AssistantConversation, direction: str, text: str, raw: dict[str, Any], message_type: str) -> None:
        self.db.add(
            AssistantMessage(
                conversation_id=conversation.id,
                direction=direction,
                text=text,
                raw_payload=raw,
                message_type=message_type,
            )
        )
        self.db.commit()

    def _pending_action(self, conversation: AssistantConversation) -> AssistantAction | None:
        return (
            self.db.query(AssistantAction)
            .filter(AssistantAction.conversation_id == conversation.id, AssistantAction.status.in_(["needs_confirmation", "needs_input"]))
            .order_by(AssistantAction.id.desc())
            .first()
        )

    def _parse_intent(self, text: str, conversation: AssistantConversation | None = None) -> dict[str, Any]:
        normalized = _normalize(text)
        has_meeting_signal = "reuniao" in normalized or "agenda" in normalized or "marcar" in normalized
        employee_mentions = self._employee_mentions(text)
        if not has_meeting_signal and not employee_mentions:
            return {"intent": "unknown"}
        deterministic = _deterministic_meeting_parse(text)
        deterministic["participant_names"] = _merge_participant_names(
            deterministic.get("participant_names") or [],
            employee_mentions,
        )
        try:
            today = date.today()
            model = resolve_ai_model(self.db, "assistant")
            prompt_payload = {
                "mensagem_atual": text,
                "historico_recente": self._recent_context(conversation) if conversation else [],
                "funcionarios_ativos": self._employee_references(),
            }
            raw = generate_ai_text(
                model,
                system_instruction=(
                    "Voce extrai pedidos de agendamento de reuniao em portugues e responde apenas JSON valido. "
                    f"Data de hoje: {today.isoformat()}. "
                    "Interprete datas relativas como hoje, amanha, depois de amanha, proxima semana, "
                    "semana que vem e dias da semana. Campos obrigatorios do JSON: "
                    "intent, title, date_text, date, preferred_period, duration_minutes, participant_names, description. "
                    "Use intent schedule_meeting ou unknown. date deve ser ISO YYYY-MM-DD quando for possivel inferir, "
                    "caso contrario null. preferred_period deve ser manha, tarde, noite ou null. "
                    "participant_names deve ser uma lista de nomes citados ou nomes correspondentes no cadastro. "
                    "Use historico_recente para completar dados faltantes, mas nao confirme nem crie reuniao. "
                    "Use funcionarios_ativos apenas como referencia para corrigir nomes parecidos."
                ),
                prompt=json.dumps(prompt_payload, ensure_ascii=False),
                json_response=True,
                max_tokens=800,
            )
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return _merge_meeting_parse(parsed, deterministic)
        except Exception:
            pass
        return deterministic

    def _meeting_payload(self, parsed: dict[str, Any]) -> dict[str, Any]:
        meeting_date = _date_from_text(str(parsed.get("date") or parsed.get("date_text") or ""))
        title = _normalize_title(parsed.get("title"))
        return {
            "title": title,
            "description": parsed.get("description") or title or "",
            "date": meeting_date.isoformat() if meeting_date else None,
            "preferred_period": _period_from_text(str(parsed.get("preferred_period") or parsed.get("description") or "")),
            "duration_minutes": _duration_from_value(parsed.get("duration_minutes"), parsed.get("description") or ""),
            "participant_names": parsed.get("participant_names") or [],
        }

    def _resolve_people(self, names: list[str]) -> list[dict[str, Any]]:
        employees = self.db.query(Employee).filter(Employee.active.is_(True)).all()
        resolved = []
        seen_resolved: set[str] = set()
        for name in names:
            normalized = _normalize(_clean_person_name(name))
            best = None
            best_score = 0.0
            scored: list[tuple[Employee, float]] = []
            for employee in employees:
                candidate = _normalize(employee.name)
                score = max(_token_overlap(normalized, candidate), _similarity(normalized, candidate))
                if normalized and (normalized in candidate or candidate in normalized):
                    score = max(score, 1.0)
                if score >= 0.34:
                    scored.append((employee, score))
                if score > best_score:
                    best = employee
                    best_score = score
            scored.sort(key=lambda item: item[1], reverse=True)
            close_candidates = [
                {"id": employee.id, "name": employee.name, "email": employee.email, "score": round(score, 3)}
                for employee, score in scored[:3]
                if score >= max(0.34, best_score - 0.08)
            ]
            if best and best_score >= 0.5 and len(close_candidates) <= 1:
                key = f"id:{best.id}"
                if key not in seen_resolved:
                    seen_resolved.add(key)
                    resolved.append({"id": best.id, "name": best.name, "email": best.email})
            elif best and best_score >= 0.72:
                key = f"id:{best.id}"
                if key not in seen_resolved:
                    seen_resolved.add(key)
                    resolved.append({"id": best.id, "name": best.name, "email": best.email})
            else:
                key = f"name:{normalized}"
                if key not in seen_resolved:
                    seen_resolved.add(key)
                    resolved.append({"name": name, "email": None, "unresolved": True, "candidates": close_candidates})
        return resolved

    def _apply_message_to_pending_action(self, action: AssistantAction, text: str) -> AssistantAction:
        payload = action.payload_json or {}
        parsed = self._parse_intent(text, conversation=action.conversation)
        new_payload = self._meeting_payload(parsed) if parsed.get("intent") == "schedule_meeting" else {}
        if parsed.get("intent") == "unknown":
            direct_mentions = self._employee_mentions(text)
            direct_date = _date_from_text(text)
            direct_period = _period_from_text(text)
            if direct_mentions:
                new_payload = {"participant_names": direct_mentions}
            if direct_date:
                new_payload["date"] = direct_date.isoformat()
            if direct_period:
                new_payload["preferred_period"] = direct_period

        if not payload.get("date") and new_payload.get("date"):
            payload["date"] = new_payload["date"]
        if not payload.get("preferred_period") and new_payload.get("preferred_period"):
            payload["preferred_period"] = new_payload["preferred_period"]
        if (payload.get("duration_minutes") in (None, 30)) and new_payload.get("duration_minutes"):
            payload["duration_minutes"] = new_payload["duration_minutes"]
        if not payload.get("title") and new_payload.get("title"):
            payload["title"] = new_payload["title"]
        if not payload.get("description") and new_payload.get("description"):
            payload["description"] = new_payload["description"]

        participant_names = new_payload.get("participant_names") or []
        if participant_names:
            payload["participant_names"] = participant_names
            payload["participants"] = self._resolve_people(participant_names)

        if not payload.get("title"):
            title_complement = _title_complement_from_text(text)
            has_structured_value = bool(new_payload.get("date") or new_payload.get("preferred_period") or participant_names)
            if title_complement and not has_structured_value:
                payload["title"] = title_complement
                payload["description"] = title_complement

        payload["suggested_slots"] = calendar_provider().suggest_slots(payload)
        payload["missing_fields"] = self._missing_fields(payload)
        action.payload_json = payload
        action.status = "needs_confirmation" if not payload["missing_fields"] else "needs_input"
        self.db.commit()
        self.db.refresh(action)
        return action

    def _employee_references(self) -> list[dict[str, Any]]:
        employees = (
            self.db.query(Employee)
            .filter(Employee.active.is_(True))
            .order_by(Employee.name.asc())
            .limit(120)
            .all()
        )
        return [
            {
                "id": employee.id,
                "name": employee.name,
                "email": employee.email,
                "setor": employee.setor or employee.department,
            }
            for employee in employees
        ]

    def _recent_context(self, conversation: AssistantConversation | None, limit: int = 8) -> list[dict[str, str]]:
        if not conversation:
            return []
        messages = (
            self.db.query(AssistantMessage)
            .filter(AssistantMessage.conversation_id == conversation.id)
            .order_by(AssistantMessage.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {"direction": message.direction, "text": message.text or ""}
            for message in reversed(messages)
            if message.text
        ]

    def _employee_mentions(self, text: str) -> list[str]:
        normalized_text = _normalize(text)
        if not normalized_text:
            return []
        employees = self.db.query(Employee).filter(Employee.active.is_(True)).all()
        mentions: list[str] = []
        seen: set[str] = set()
        for employee in employees:
            normalized_name = _normalize(employee.name)
            tokens = [token for token in normalized_name.split() if len(token) >= 4]
            if normalized_name and normalized_name in normalized_text:
                key = _normalize(employee.name)
            elif any(re.search(rf"\b{re.escape(token)}\b", normalized_text) for token in tokens):
                key = _normalize(employee.name)
            else:
                continue
            if key not in seen:
                seen.add(key)
                mentions.append(employee.name)
        return mentions

    def _missing_fields(self, payload: dict[str, Any]) -> list[str]:
        missing = []
        if not payload.get("title"):
            missing.append("titulo")
        if not payload.get("date"):
            missing.append("data")
        if not payload.get("participants") or any(item.get("unresolved") for item in payload.get("participants", [])):
            missing.append("participantes")
        return missing

    def _proposal_reply(self, action: AssistantAction) -> str:
        payload = action.payload_json or {}
        participants = payload.get("participants") or []
        slots = payload.get("suggested_slots") or []
        lines = [
            "Confirme os dados da reuniao antes de eu criar o agendamento:",
            f"Titulo: {payload.get('title') or 'nao informado'}",
            f"Data: {payload.get('date') or 'nao informada'}",
            f"Periodo: {payload.get('preferred_period') or 'sem preferencia'}",
            f"Duracao: {payload.get('duration_minutes') or 30} minutos",
        ]
        if participants:
            lines.append("Participantes:")
            lines.extend(f"- {item.get('name')} ({item.get('email') or 'nao encontrado'})" for item in participants)
            unresolved = [item for item in participants if item.get("unresolved") and item.get("candidates")]
            for item in unresolved:
                options = ", ".join(candidate["name"] for candidate in item.get("candidates", [])[:3])
                if options:
                    lines.append(f"Para '{item.get('name')}', voce quis dizer: {options}?")
        if payload.get("missing_fields"):
            lines.append(f"Antes de confirmar, faltam: {', '.join(payload['missing_fields'])}.")
            return "\n".join(lines)
        lines.append("Horarios sugeridos:")
        lines.extend(f"- {slot.get('start')} ate {slot.get('end')}" for slot in slots[:3])
        lines.append("Responda 'confirmo' para criar a reuniao no primeiro horario sugerido ou 'cancelar'.")
        return "\n".join(lines)

    def _confirmation_reply(self, action: AssistantAction) -> str:
        result = action.result_json or {}
        if action.status == "needs_input":
            return f"Ainda faltam informacoes: {', '.join(result.get('missing_fields') or [])}."
        if action.status == "completed":
            if result.get("status") == "simulated":
                return "Reuniao validada, mas o Microsoft Graph nao esta configurado. Registrei a simulacao da agenda."
            return f"Reuniao criada. Link: {result.get('meeting_url') or '-'}"
        return f"Nao consegui criar a reuniao: {result.get('error') or result}"


def _deterministic_meeting_parse(text: str) -> dict[str, Any]:
    normalized = _normalize(text)
    participant_names: list[str] = []
    for match in re.finditer(r"\bcom\s+(.+?)(?:\s+para\s+|\s+sobre\s+|$)", text, flags=re.IGNORECASE):
        raw_names = re.split(r",|\se\s", match.group(1))
        participant_names.extend(_clean_person_name(name) for name in raw_names if len(_clean_person_name(name)) >= 3)
    return {
        "intent": "schedule_meeting" if "agenda" in normalized or "reuniao" in normalized or "marcar" in normalized else "unknown",
        "title": _title_from_text(text),
        "date_text": _date_text_from_text(normalized),
        "preferred_period": _period_from_text(text),
        "duration_minutes": _duration_from_value(None, text),
        "participant_names": participant_names,
        "description": text,
    }


def _merge_meeting_parse(ai_parsed: dict[str, Any], deterministic: dict[str, Any]) -> dict[str, Any]:
    merged = dict(deterministic)
    for key, value in ai_parsed.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    merged["participant_names"] = _merge_participant_names(
        ai_parsed.get("participant_names") or [],
        deterministic.get("participant_names") or [],
    )
    if not merged.get("date_text") and deterministic.get("date_text"):
        merged["date_text"] = deterministic["date_text"]
    if not merged.get("preferred_period") and deterministic.get("preferred_period"):
        merged["preferred_period"] = deterministic["preferred_period"]
    return merged


def _merge_participant_names(ai_names: list[Any], deterministic_names: list[Any]) -> list[str]:
    ignored = {"eu", "mim", "me", "meu", "minha", "nos", "gente", "assistente"}
    merged: list[str] = []
    seen: set[str] = set()
    for raw_name in [*deterministic_names, *ai_names]:
        name = _clean_person_name(str(raw_name))
        normalized = _normalize(name)
        if not normalized or normalized in ignored:
            continue
        if normalized not in seen:
            seen.add(normalized)
            merged.append(name)
    return merged


def _title_from_text(text: str) -> str:
    match = re.search(r"\bsobre\s+(.+)$", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"\bfalar\s+(?:sobre|de)\s+(.+)$", text, flags=re.IGNORECASE)
    if not match:
        return "Reuniao ASM Digital"
    title = re.sub(r"\s+com\s+.+$", "", match.group(1), flags=re.IGNORECASE)
    return title.strip(" .") or "Reuniao ASM Digital"


def _normalize_title(value: Any) -> str | None:
    title = str(value or "").strip(" .")
    if not title or _normalize(title) == _normalize("Reuniao ASM Digital"):
        return None
    return title


def _title_complement_from_text(text: str) -> str | None:
    normalized = _normalize(text)
    if not normalized:
        return None
    if normalized in CONFIRM_WORDS or normalized in CANCEL_WORDS:
        return None
    if _date_from_text(text) or _period_from_text(text):
        return None
    extracted = _normalize_title(_title_from_text(text))
    if extracted:
        return extracted
    cleaned = re.sub(r"^(?:titulo|assunto|sobre|tema)\s*[:\-]?\s*", "", text or "", flags=re.IGNORECASE).strip(" .")
    if len(cleaned) < 3:
        return None
    return cleaned


def _clean_person_name(value: str) -> str:
    cleaned = re.sub(r"^\s*(?:com|a|o|as|os|para|pra)\s+", "", value or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:para|pra|sobre|falar)\s+.*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" .,;:\"'")


def _date_text_from_text(normalized: str) -> str:
    if "depois de amanha" in normalized:
        return "depois de amanha"
    if "proxima semana" in normalized or "semana que vem" in normalized:
        for weekday in ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]:
            if weekday in normalized:
                return f"{weekday} proxima semana"
        return "proxima semana"
    for weekday in ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]:
        if weekday in normalized:
            return weekday
    if "amanha" in normalized:
        return "amanha"
    if "hoje" in normalized:
        return "hoje"
    return ""


def _date_from_text(text: str) -> date | None:
    normalized = _normalize(text)
    today = date.today()
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", normalized)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group(1))
        except ValueError:
            pass
    br_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", normalized)
    if br_match:
        day = int(br_match.group(1))
        month = int(br_match.group(2))
        year = int(br_match.group(3)) if br_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            parsed = date(year, month, day)
            if not br_match.group(3) and parsed < today:
                parsed = date(year + 1, month, day)
            return parsed
        except ValueError:
            pass
    day_match = re.search(r"\bdia\s+(\d{1,2})\b", normalized)
    if day_match:
        day = int(day_match.group(1))
        try:
            parsed = date(today.year, today.month, day)
            if parsed < today:
                next_month = today.month + 1
                year = today.year + (1 if next_month > 12 else 0)
                month = 1 if next_month > 12 else next_month
                parsed = date(year, month, day)
            return parsed
        except ValueError:
            pass
    if "hoje" in normalized:
        return today
    if "depois de amanha" in normalized:
        return today + timedelta(days=2)
    if "amanha" in normalized:
        return today + timedelta(days=1)
    weekdays = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
    next_week = "proxima semana" in normalized or "semana que vem" in normalized
    for label, weekday in weekdays.items():
        if label in normalized:
            if next_week:
                start_next_week = today + timedelta(days=(7 - today.weekday()))
                return start_next_week + timedelta(days=weekday)
            days = (weekday - today.weekday()) % 7 or 7
            return today + timedelta(days=days)
    if next_week:
        return today + timedelta(days=(7 - today.weekday()))
    return None


def _period_from_text(text: str) -> str | None:
    normalized = _normalize(text)
    if "manha" in normalized:
        return "manha"
    if "tarde" in normalized:
        return "tarde"
    if "noite" in normalized:
        return "noite"
    return None


def _duration_from_value(value: Any, text: str) -> int:
    try:
        if value:
            minutes = int(value)
            if 5 <= minutes <= 480:
                return minutes
    except (TypeError, ValueError):
        pass
    normalized = _normalize(text)
    match = re.search(r"\b(\d{1,2})\s*(?:min|minutos)\b", normalized)
    if match:
        return max(5, min(480, int(match.group(1))))
    match = re.search(r"\b(\d{1,2})\s*(?:h|hora|horas)\b", normalized)
    if match:
        return max(5, min(480, int(match.group(1)) * 60))
    if "meia hora" in normalized:
        return 30
    if "uma hora" in normalized or "1 hora" in normalized:
        return 60
    return 30


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents.casefold()).strip()


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    ratios = [SequenceMatcher(None, left, right).ratio()]
    left_tokens = [token for token in left.split() if len(token) >= 3]
    right_tokens = [token for token in right.split() if len(token) >= 3]
    for left_token in left_tokens:
        ratios.extend(SequenceMatcher(None, left_token, right_token).ratio() for right_token in right_tokens)
    return max(ratios) if ratios else 0.0
