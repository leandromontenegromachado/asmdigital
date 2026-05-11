from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AuditLog, Automation, Notification, NotificationRule, NotificationTemplate, User
from app.schemas.notifications import (
    NotificationOut,
    NotificationRetryOut,
    NotificationRuleCreate,
    NotificationRuleOut,
    NotificationRuleUpdate,
    NotificationTemplateCreate,
    NotificationTemplateOut,
    NotificationTemplateUpdate,
)
from app.services.notification_service import approve_notification, cancel_notification, retry_notification

router = APIRouter(tags=["notifications"])


def _audit(db: Session, actor: User, action: str, entity_type: str, entity_id: int | None, old_value=None, new_value=None) -> None:
    db.add(
        AuditLog(
            user_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
        )
    )


def _template_out(template: NotificationTemplate) -> NotificationTemplateOut:
    return NotificationTemplateOut.model_validate(template)


def _rule_out(rule: NotificationRule) -> NotificationRuleOut:
    return NotificationRuleOut(
        id=rule.id,
        automation_id=rule.automation_id,
        automation_name=rule.automation.name if rule.automation else None,
        is_active=rule.is_active,
        send_condition=rule.send_condition,
        recipient_type=rule.recipient_type,
        preferred_channel=rule.preferred_channel,
        fallback_channel=rule.fallback_channel,
        template_id=rule.template_id,
        template_name=rule.template.name if rule.template else None,
        requires_approval=rule.requires_approval,
        notify_manager=rule.notify_manager,
        manager_condition=rule.manager_condition,
        params_json=rule.params_json or {},
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _notification_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        execution_id=notification.execution_id,
        automation_id=notification.automation_id,
        automation_name=notification.automation.name if notification.automation else None,
        employee_id=notification.employee_id,
        employee_name=notification.employee.name if notification.employee else None,
        channel=notification.channel,
        recipient=notification.recipient or notification.to_ref,
        subject=notification.subject,
        message=notification.message or notification.body,
        status=notification.status,
        data_envio=notification.data_envio,
        sent_at=notification.sent_at,
        error=notification.error,
        attempts=notification.attempts,
        simulation=notification.simulation,
        created_at=notification.created_at,
    )


@router.get("/notification-templates", response_model=list[NotificationTemplateOut])
def list_templates(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(NotificationTemplate).order_by(NotificationTemplate.name.asc()).all()


@router.post("/notification-templates", response_model=NotificationTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(payload: NotificationTemplateCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = NotificationTemplate(**payload.model_dump())
    db.add(template)
    db.flush()
    _audit(db, user, "CREATE_NOTIFICATION_TEMPLATE", "notification_templates", template.id, None, payload.model_dump())
    db.commit()
    db.refresh(template)
    return _template_out(template)


@router.put("/notification-templates/{template_id}", response_model=NotificationTemplateOut)
def update_template(template_id: int, payload: NotificationTemplateUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    data = payload.model_dump(exclude_unset=True)
    old = {key: getattr(template, key) for key in data}
    for key, value in data.items():
        setattr(template, key, value)
    _audit(db, user, "UPDATE_NOTIFICATION_TEMPLATE", "notification_templates", template.id, old, data)
    db.commit()
    db.refresh(template)
    return _template_out(template)


@router.delete("/notification-templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    _audit(db, user, "DELETE_NOTIFICATION_TEMPLATE", "notification_templates", template.id, {"name": template.name}, None)
    db.delete(template)
    db.commit()
    return None


@router.get("/notification-rules", response_model=list[NotificationRuleOut])
def list_rules(
    automation_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = db.query(NotificationRule)
    if automation_id:
        query = query.filter(NotificationRule.automation_id == automation_id)
    return [_rule_out(rule) for rule in query.order_by(NotificationRule.id.asc()).all()]


@router.post("/notification-rules", response_model=NotificationRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(payload: NotificationRuleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    automation = db.query(Automation).filter(Automation.id == payload.automation_id).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    rule = NotificationRule(**payload.model_dump())
    db.add(rule)
    db.flush()
    _audit(db, user, "CREATE_NOTIFICATION_RULE", "notification_rules", rule.id, None, payload.model_dump())
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@router.put("/notification-rules/{rule_id}", response_model=NotificationRuleOut)
def update_rule(rule_id: int, payload: NotificationRuleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = db.query(NotificationRule).filter(NotificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    data = payload.model_dump(exclude_unset=True)
    old = {key: getattr(rule, key) for key in data}
    for key, value in data.items():
        setattr(rule, key, value)
    _audit(db, user, "UPDATE_NOTIFICATION_RULE", "notification_rules", rule.id, old, data)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@router.delete("/notification-rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = db.query(NotificationRule).filter(NotificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    _audit(db, user, "DELETE_NOTIFICATION_RULE", "notification_rules", rule.id, {"automation_id": rule.automation_id}, None)
    db.delete(rule)
    db.commit()
    return None


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    execution_id: int | None = Query(default=None),
    automation_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = db.query(Notification)
    if execution_id:
        query = query.filter(Notification.execution_id == execution_id)
    if automation_id:
        query = query.filter(Notification.automation_id == automation_id)
    if status_filter:
        query = query.filter(Notification.status == status_filter)
    notifications = query.order_by(Notification.created_at.desc()).limit(200).all()
    return [_notification_out(notification) for notification in notifications]


@router.post("/notifications/{notification_id}/retry", response_model=NotificationRetryOut)
def retry_notification_endpoint(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    old = {"status": notification.status, "attempts": notification.attempts, "error": notification.error}
    notification = retry_notification(db, notification)
    _audit(db, user, "RETRY_NOTIFICATION", "notifications", notification.id, old, {"status": notification.status, "attempts": notification.attempts, "error": notification.error})
    db.commit()
    return NotificationRetryOut(id=notification.id, status=notification.status, error=notification.error, attempts=notification.attempts)


@router.post("/notifications/{notification_id}/approve", response_model=NotificationRetryOut)
def approve_notification_endpoint(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    old = {"status": notification.status, "attempts": notification.attempts, "error": notification.error}
    notification = approve_notification(db, notification)
    _audit(
        db,
        user,
        "APPROVE_NOTIFICATION",
        "notifications",
        notification.id,
        old,
        {"status": notification.status, "attempts": notification.attempts, "error": notification.error},
    )
    db.commit()
    return NotificationRetryOut(id=notification.id, status=notification.status, error=notification.error, attempts=notification.attempts)


@router.post("/notifications/{notification_id}/cancel", response_model=NotificationRetryOut)
def cancel_notification_endpoint(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    old = {"status": notification.status, "attempts": notification.attempts, "error": notification.error}
    notification = cancel_notification(db, notification)
    _audit(
        db,
        user,
        "CANCEL_NOTIFICATION",
        "notifications",
        notification.id,
        old,
        {"status": notification.status, "attempts": notification.attempts, "error": notification.error},
    )
    db.commit()
    return NotificationRetryOut(id=notification.id, status=notification.status, error=notification.error, attempts=notification.attempts)
