from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import User
from app.modules.fala_ai.models import FalaAiLog, FalaAiReminder
from app.modules.fala_ai.schemas import (
    FalaAiBotReplyIn,
    FalaAiBotReplyOut,
    FalaAiCheckinCreate,
    FalaAiCheckinOut,
    FalaAiDailyReportOut,
    FalaAiDispatchReportOut,
    FalaAiLogOut,
    FalaAiPollHistoryItemOut,
    FalaAiReminderCreate,
    FalaAiReminderOut,
    FalaAiReminderUpdate,
    FalaAiWebhookResponse,
)
from app.modules.fala_ai.scheduler import send_reminder_now, sync_fala_ai_jobs
from app.modules.fala_ai.service import (
    build_bot_reply,
    build_daily_report,
    build_dispatch_report,
    build_latest_dispatch_report,
    build_poll_history,
    create_checkin,
    create_reminder,
    delete_reminder,
    list_checkins,
    list_reminders,
    process_teams_webhook_payload,
    register_log,
    update_reminder,
)
from app.modules.fala_ai.teams_integration import (
    extract_bot_context,
    send_teams_message,
    validate_teams_request,
)
from app.core.config import settings
from app.scheduler import scheduler

router = APIRouter(prefix="/fala-ai", tags=["fala-ai"])


@router.post("/checkin", response_model=FalaAiCheckinOut, status_code=status.HTTP_201_CREATED)
def create_checkin_endpoint(
    payload: FalaAiCheckinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_checkin(
        db,
        payload,
        actor=current_user,
        allow_impersonation=current_user.role == "admin",
    )


@router.get("/checkins", response_model=list[FalaAiCheckinOut])
def list_checkins_endpoint(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return list_checkins(db)


@router.get("/reminders", response_model=list[FalaAiReminderOut])
def list_reminders_endpoint(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return list_reminders(db)


@router.post("/reminders", response_model=FalaAiReminderOut, status_code=status.HTTP_201_CREATED)
def create_reminder_endpoint(
    payload: FalaAiReminderCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    reminder = create_reminder(db, mensagem=payload.mensagem, horario=payload.horario, ativo=payload.ativo)
    sync_fala_ai_jobs(db, scheduler)
    return reminder


@router.put("/reminders/{reminder_id}", response_model=FalaAiReminderOut)
def update_reminder_endpoint(
    reminder_id: int,
    payload: FalaAiReminderUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    reminder = db.query(FalaAiReminder).filter(FalaAiReminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    updated = update_reminder(db, reminder, payload.model_dump(exclude_unset=True))
    sync_fala_ai_jobs(db, scheduler)
    return updated


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder_endpoint(
    reminder_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    reminder = db.query(FalaAiReminder).filter(FalaAiReminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    delete_reminder(db, reminder)
    sync_fala_ai_jobs(db, scheduler)
    return None


@router.post("/reminders/{reminder_id}/send", status_code=status.HTTP_202_ACCEPTED)
def send_reminder_now_endpoint(
    reminder_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    reminder = db.query(FalaAiReminder).filter(FalaAiReminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    send_reminder_now(reminder_id)
    return {"status": "queued"}


@router.get("/report/daily", response_model=FalaAiDailyReportOut)
def daily_report_endpoint(
    date_ref: datetime | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    target_date = (date_ref or datetime.now(timezone.utc)).date()
    return build_daily_report(db, target_date=target_date)


@router.get("/report/poll/latest", response_model=FalaAiDispatchReportOut)
def latest_poll_report_endpoint(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return build_latest_dispatch_report(db)


@router.get("/report/poll/history", response_model=list[FalaAiPollHistoryItemOut])
def poll_history_endpoint(
    limit: int = 20,
    date_ref: date | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return build_poll_history(db, limit=limit, target_date=date_ref)


@router.get("/report/poll/{dispatch_id}", response_model=FalaAiDispatchReportOut)
def poll_report_endpoint(
    dispatch_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return build_dispatch_report(db, dispatch_id)


@router.get("/logs", response_model=list[FalaAiLogOut])
def list_logs_endpoint(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return db.query(FalaAiLog).order_by(FalaAiLog.created_at.desc()).limit(100).all()


@router.post("/webhook/teams", response_model=FalaAiWebhookResponse)
async def teams_webhook_endpoint(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    headers = {k: v for (k, v) in request.headers.items()}

    if not validate_teams_request(raw_body, headers, settings.fala_ai_teams_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid Teams signature")

    payload = await request.json()
    checkin, reply = process_teams_webhook_payload(db, payload)
    bot_context = extract_bot_context(payload)
    register_log(
        db,
        "teams_bot_context_received",
        {
            "service_url": bot_context.get("service_url"),
            "conversation_id": bot_context.get("conversation_id"),
            "bot_id": bot_context.get("bot_id"),
            "channel_id": payload.get("channelId"),
        },
    )

    if reply.strip():
        try:
            send_teams_message(
                message=reply,
                webhook_url=settings.fala_ai_teams_outgoing_webhook,
                bot_app_id=settings.fala_ai_teams_bot_app_id,
                bot_app_secret=settings.fala_ai_teams_bot_app_secret,
                bot_tenant_id=settings.fala_ai_teams_bot_tenant_id,
                service_url=bot_context.get("service_url") or settings.fala_ai_teams_default_service_url,
                conversation_id=bot_context.get("conversation_id") or settings.fala_ai_teams_default_conversation_id,
                bot_id=bot_context.get("bot_id") or settings.fala_ai_teams_default_bot_id,
            )
        except RuntimeError:
            register_log(
                db,
                "teams_delivery_not_configured",
                {
                    "has_webhook": bool(settings.fala_ai_teams_outgoing_webhook),
                    "has_bot_id": bool(settings.fala_ai_teams_bot_app_id),
                    "has_bot_secret": bool(settings.fala_ai_teams_bot_app_secret),
                    "has_service_url": bool(bot_context.get("service_url") or settings.fala_ai_teams_default_service_url),
                    "has_conversation_id": bool(bot_context.get("conversation_id") or settings.fala_ai_teams_default_conversation_id),
                },
            )
        except Exception as exc:  # noqa: BLE001
            register_log(
                db,
                "teams_delivery_failed",
                {"error": str(exc)},
            )

    if not checkin:
        return FalaAiWebhookResponse(status="ignored", detail=reply)

    return FalaAiWebhookResponse(
        status="ok",
        detail="Check-in registrado",
        checkin_id=checkin.id,
        reply_message=reply,
    )


@router.post("/reply", response_model=FalaAiBotReplyOut)
def bot_reply_endpoint(payload: FalaAiBotReplyIn, _user: User = Depends(get_current_user)):
    return FalaAiBotReplyOut(resposta=build_bot_reply(payload.mensagem))
