from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
import unicodedata

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User
from app.modules.fala_ai.models import FalaAiCheckin, FalaAiLog, FalaAiReminder
from app.modules.fala_ai.schemas import FalaAiCheckinCreate, FalaAiDailyReportOut, FalaAiDailyUserStatus
from app.modules.fala_ai.teams_integration import extract_teams_identity


BOT_OPENERS = [
    "Fala ai! Bora fazer esse check-in?",
    "Partiu garantir o basico do dia?",
    "Fala ai... status rapido e vida que segue.",
]

CHECKIN_CONFIRM_WORDS = {
    "sim",
    "s",
    "ok",
    "okay",
    "bati",
    "batido",
    "feito",
    "concluido",
    "done",
    "pronto",
    "checkin",
    "check-in",
}

CHECKIN_CONFIRM_REACTIONS = {
    "like",
    "thumbsup",
    "thumbs_up",
    "heart",
}

ACTIVE_DISPATCH_WINDOW_HOURS = 16


def build_engagement_snapshot(db: Session, target_date: date) -> dict[str, Any]:
    """Placeholder para evolucao futura (gamificacao, ranking e indicadores PPR)."""
    report = build_daily_report(db, target_date=target_date)
    return {
        "date": str(target_date),
        "checked_in_total": len(report.checked_in_users),
        "missing_total": len(report.missing_users),
        "ranking": [],
        "ppr_indicators": {},
    }


def register_log(db: Session, evento: str, payload: dict[str, Any]) -> FalaAiLog:
    log = FalaAiLog(evento=evento, payload=payload)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def resolve_user(
    db: Session,
    *,
    user_id: int | None = None,
    email: str | None = None,
    name: str | None = None,
) -> User | None:
    if user_id is not None:
        return db.query(User).filter(User.id == user_id).first()
    if email:
        return db.query(User).filter(User.email == email).first()
    if name:
        matched = db.query(User).filter(User.name.ilike(name)).all()
        if len(matched) == 1:
            return matched[0]
    return None


def create_checkin(
    db: Session,
    payload: FalaAiCheckinCreate,
    *,
    actor: User | None,
    allow_impersonation: bool,
) -> FalaAiCheckin:
    target_user_id = payload.user_id or (actor.id if actor else None)
    if target_user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")

    if actor and not allow_impersonation and target_user_id != actor.id:
        raise HTTPException(status_code=403, detail="Cannot create checkin for another user")

    target_user = resolve_user(db, user_id=target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    created_at = payload.timestamp or datetime.now(timezone.utc)
    checkin = FalaAiCheckin(
        user_id=target_user.id,
        tipo=(payload.tipo or "manual").strip() or "manual",
        origem=(payload.origem or "web").strip() or "web",
        created_at=created_at,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


def list_checkins(db: Session, *, limit: int = 100) -> list[FalaAiCheckin]:
    return (
        db.query(FalaAiCheckin)
        .order_by(FalaAiCheckin.created_at.desc())
        .limit(limit)
        .all()
    )


def list_reminders(db: Session) -> list[FalaAiReminder]:
    return db.query(FalaAiReminder).order_by(FalaAiReminder.horario.asc(), FalaAiReminder.id.asc()).all()


def create_reminder(db: Session, *, mensagem: str, horario, ativo: bool) -> FalaAiReminder:
    reminder = FalaAiReminder(mensagem=mensagem.strip(), horario=horario, ativo=ativo)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def update_reminder(db: Session, reminder: FalaAiReminder, changes: dict[str, Any]) -> FalaAiReminder:
    for key, value in changes.items():
        setattr(reminder, key, value)
    db.commit()
    db.refresh(reminder)
    return reminder


def delete_reminder(db: Session, reminder: FalaAiReminder) -> None:
    db.delete(reminder)
    db.commit()


def build_bot_reply(mensagem: str) -> str:
    text = (mensagem or "").lower()
    if "bom dia" in text:
        return "Bom dia! Ja mandou seu check-in? Vale ponto de honra."
    if "status" in text:
        return "Resumo do dia: foco no essencial e check-in em dia."
    if "help" in text or "ajuda" in text:
        return "Posso registrar check-in, lembrar horarios e gerar relatorio diario."
    return BOT_OPENERS[hash(text) % len(BOT_OPENERS)]


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip().lower()


def _is_checkin_confirmation(identity: dict[str, Any]) -> tuple[bool, str]:
    activity_type = str(identity.get("activity_type") or "").strip().lower()
    message = _normalize_text(str(identity.get("normalized_message") or identity.get("message") or ""))
    reaction_types = {
        _normalize_text(str(item))
        for item in (identity.get("reaction_types") or [])
        if str(item).strip()
    }

    if activity_type == "messagereaction":
        if reaction_types.intersection(CHECKIN_CONFIRM_REACTIONS):
            return True, "reaction"
        return False, "reaction"

    if activity_type == "message":
        tokens = [token for token in message.replace(".", " ").replace(",", " ").split() if token]
        if any(token in CHECKIN_CONFIRM_WORDS for token in tokens):
            return True, "message_confirmation"
        return False, "message"

    return False, activity_type or "unknown"


def _existing_checkin_today(db: Session, user_id: int) -> FalaAiCheckin | None:
    now = datetime.now(timezone.utc)
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return (
        db.query(FalaAiCheckin)
        .filter(
            FalaAiCheckin.user_id == user_id,
            FalaAiCheckin.created_at >= day_start,
            FalaAiCheckin.created_at <= day_end,
        )
        .order_by(FalaAiCheckin.created_at.desc())
        .first()
    )


def _find_dispatch_by_id(db: Session, dispatch_id: str) -> dict[str, Any] | None:
    if not dispatch_id:
        return None
    logs = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "reminder_sent")
        .order_by(FalaAiLog.created_at.desc())
        .limit(500)
        .all()
    )
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        if str(payload.get("dispatch_id") or "") == dispatch_id:
            return payload
    return None


def _resolve_active_dispatch(identity: dict[str, Any], db: Session) -> dict[str, Any] | None:
    conversation_id = str(identity.get("conversation_id") or "").strip()
    channel_id = str(identity.get("channel_id") or "").strip()
    if not conversation_id:
        return None

    logs = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "reminder_sent")
        .order_by(FalaAiLog.created_at.desc())
        .limit(200)
        .all()
    )
    now = datetime.now(timezone.utc)

    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        if str(payload.get("conversation_id") or "") != conversation_id:
            continue
        if channel_id and str(payload.get("channel_id") or "") and str(payload.get("channel_id") or "") != channel_id:
            continue
        age_hours = (now - log.created_at).total_seconds() / 3600 if log.created_at else 999
        if age_hours > ACTIVE_DISPATCH_WINDOW_HOURS:
            continue
        return payload

    return None


def _checkin_already_recorded_for_dispatch(db: Session, *, user_id: int, dispatch_id: str) -> bool:
    logs = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "teams_checkin_registered")
        .order_by(FalaAiLog.created_at.desc())
        .limit(500)
        .all()
    )
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        if int(payload.get("user_id") or -1) == user_id and str(payload.get("dispatch_id") or "") == dispatch_id:
            return True
    return False


def build_dispatch_report(db: Session, dispatch_id: str) -> dict[str, Any]:
    dispatch = _find_dispatch_by_id(db, dispatch_id)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch not found")

    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).all()

    logs = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "teams_checkin_registered")
        .order_by(FalaAiLog.created_at.desc())
        .limit(1000)
        .all()
    )
    by_user: dict[int, dict[str, Any]] = {}
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        if str(payload.get("dispatch_id") or "") != dispatch_id:
            continue
        user_id = int(payload.get("user_id") or -1)
        if user_id <= 0 or user_id in by_user:
            continue
        by_user[user_id] = {
            "user_id": user_id,
            "checkin_id": payload.get("checkin_id"),
            "reason": payload.get("reason"),
            "at": log.created_at.isoformat() if log.created_at else None,
        }

    checked_in = []
    missing = []
    for user in users:
        status = {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "confirmation": by_user.get(user.id),
        }
        if user.id in by_user:
            checked_in.append(status)
        else:
            missing.append(status)

    return {
        "dispatch_id": dispatch_id,
        "reminder_id": dispatch.get("reminder_id"),
        "message": dispatch.get("message"),
        "sent_at": dispatch.get("sent_at"),
        "channel_id": dispatch.get("channel_id"),
        "conversation_id": dispatch.get("conversation_id"),
        "checked_in_users": checked_in,
        "missing_users": missing,
    }


def build_poll_history(
    db: Session,
    *,
    limit: int = 20,
    target_date: date | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))
    users_total = db.query(User).filter(User.is_active.is_(True)).count()

    reminder_logs = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "reminder_sent")
        .order_by(FalaAiLog.created_at.desc())
        .limit(1000)
        .all()
    )

    confirmation_logs = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "teams_checkin_registered")
        .order_by(FalaAiLog.created_at.desc())
        .limit(5000)
        .all()
    )

    confirmations_by_dispatch: dict[str, set[int]] = {}
    for log in confirmation_logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        dispatch_id = str(payload.get("dispatch_id") or "").strip()
        user_id = int(payload.get("user_id") or -1)
        if not dispatch_id or user_id <= 0:
            continue
        if dispatch_id not in confirmations_by_dispatch:
            confirmations_by_dispatch[dispatch_id] = set()
        confirmations_by_dispatch[dispatch_id].add(user_id)

    history: list[dict[str, Any]] = []
    seen_dispatches: set[str] = set()
    for log in reminder_logs:
        if target_date and log.created_at and log.created_at.date() != target_date:
            continue
        payload = log.payload if isinstance(log.payload, dict) else {}
        dispatch_id = str(payload.get("dispatch_id") or "").strip()
        if not dispatch_id or dispatch_id in seen_dispatches:
            continue
        seen_dispatches.add(dispatch_id)

        checked_in_total = len(confirmations_by_dispatch.get(dispatch_id, set()))
        missing_total = max(users_total - checked_in_total, 0)
        history.append(
            {
                "dispatch_id": dispatch_id,
                "reminder_id": payload.get("reminder_id"),
                "message": payload.get("message"),
                "sent_at": payload.get("sent_at") or (log.created_at.isoformat() if log.created_at else None),
                "checked_in_total": checked_in_total,
                "missing_total": missing_total,
            }
        )
        if len(history) >= safe_limit:
            break

    return history


def build_latest_dispatch_report(db: Session) -> dict[str, Any]:
    latest = (
        db.query(FalaAiLog)
        .filter(FalaAiLog.evento == "reminder_sent")
        .order_by(FalaAiLog.created_at.desc())
        .first()
    )
    if not latest or not isinstance(latest.payload, dict):
        raise HTTPException(status_code=404, detail="No dispatch found")
    dispatch_id = str(latest.payload.get("dispatch_id") or "")
    if not dispatch_id:
        raise HTTPException(status_code=404, detail="No dispatch found")
    return build_dispatch_report(db, dispatch_id)


def build_daily_report(db: Session, target_date: date) -> FalaAiDailyReportOut:
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)

    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).all()
    checkins = (
        db.query(FalaAiCheckin)
        .filter(FalaAiCheckin.created_at >= day_start, FalaAiCheckin.created_at <= day_end)
        .order_by(FalaAiCheckin.created_at.desc())
        .all()
    )

    latest_by_user: dict[int, FalaAiCheckin] = {}
    for item in checkins:
        if item.user_id not in latest_by_user:
            latest_by_user[item.user_id] = item

    checked_in_users: list[FalaAiDailyUserStatus] = []
    missing_users: list[FalaAiDailyUserStatus] = []

    for user in users:
        latest = latest_by_user.get(user.id)
        status = FalaAiDailyUserStatus(
            user_id=user.id,
            name=user.name,
            email=user.email,
            last_checkin_at=latest.created_at if latest else None,
        )
        if latest:
            checked_in_users.append(status)
        else:
            missing_users.append(status)

    return FalaAiDailyReportOut(
        date=target_date,
        checked_in_users=checked_in_users,
        missing_users=missing_users,
    )


def process_teams_webhook_payload(db: Session, payload: dict[str, Any]) -> tuple[FalaAiCheckin | None, str]:
    identity = extract_teams_identity(payload)
    activity_type = str(identity.get("activity_type") or "").strip().lower()
    has_text = bool(str(identity.get("message") or "").strip())
    has_reactions = bool(identity.get("reaction_types"))

    # Avoid loops with automatic channel events (conversationUpdate, typing, ping, etc.).
    if activity_type not in {"message", "messagereaction"}:
        register_log(
            db,
            "teams_event_ignored",
            {"activity_type": activity_type, "has_text": has_text, "has_reactions": has_reactions},
        )
        return None, ""

    if activity_type == "message" and not has_text:
        register_log(
            db,
            "teams_empty_message_ignored",
            {"activity_type": activity_type},
        )
        return None, ""

    if activity_type == "messagereaction" and not has_reactions:
        register_log(
            db,
            "teams_empty_reaction_ignored",
            {"activity_type": activity_type},
        )
        return None, ""

    active_dispatch = _resolve_active_dispatch(identity, db)

    should_checkin, reason = _is_checkin_confirmation(identity)
    user = resolve_user(
        db,
        user_id=identity["user_id"],
        email=identity["email"],
        name=identity["name"],
    )
    fallback_user_id = int(settings.fala_ai_teams_fallback_user_id) if str(settings.fala_ai_teams_fallback_user_id or "").isdigit() else None
    if not user and fallback_user_id:
        user = resolve_user(db, user_id=fallback_user_id)
    if not user and settings.fala_ai_teams_fallback_user_email:
        user = resolve_user(db, email=settings.fala_ai_teams_fallback_user_email.strip().lower())

    if not user:
        register_log(
            db,
            "teams_user_not_found",
            {"identity": identity, "payload_keys": sorted(payload.keys())},
        )
        return None, "Recebi sua mensagem, mas ainda nao consegui vincular seu usuario no sistema."

    if not should_checkin:
        register_log(
            db,
            "teams_message_without_checkin_confirmation",
            {"user_id": user.id, "message": identity.get("message"), "reason": reason},
        )
        return None, "Se voce ja bateu o ponto, responde com 'sim' ou reage com like nesta mensagem."

    if not active_dispatch:
        register_log(
            db,
            "teams_confirmation_without_active_dispatch",
            {"user_id": user.id, "message": identity.get("message"), "reason": reason},
        )
        return None, "Ainda nao ha enquete ativa para este chat."

    dispatch_id = str(active_dispatch.get("dispatch_id") or "")
    if dispatch_id and _checkin_already_recorded_for_dispatch(db, user_id=user.id, dispatch_id=dispatch_id):
        register_log(
            db,
            "teams_checkin_already_registered_for_dispatch",
            {"user_id": user.id, "dispatch_id": dispatch_id, "reason": reason},
        )
        return None, "Sua confirmacao dessa enquete ja foi registrada. Valeu!"

    checkin = create_checkin(
        db,
        FalaAiCheckinCreate(
            user_id=user.id,
            tipo="teams" if reason == "message_confirmation" else "teams_reaction",
            origem="teams",
            timestamp=datetime.now(timezone.utc),
        ),
        actor=user,
        allow_impersonation=True,
    )

    reply = "Show! Check-in confirmado com sucesso."
    register_log(
        db,
        "teams_checkin_registered",
        {
            "user_id": user.id,
            "message": identity["message"],
            "checkin_id": checkin.id,
            "reason": reason,
            "dispatch_id": dispatch_id,
            "conversation_id": active_dispatch.get("conversation_id"),
        },
    )
    return checkin, reply
