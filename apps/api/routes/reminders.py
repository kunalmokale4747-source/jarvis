from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import NotificationOut, ReminderCreate, ReminderOut, ReminderUpdate
from core.auth import Identity
from core.db.repositories import NotificationRepository, ReminderRepository
from core.reminders.service import ReminderService

router = APIRouter(tags=["reminders"])
notifications_router = APIRouter(tags=["notifications"])


@router.get("")
def list_reminders(
    status: str | None = Query(default=None),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[ReminderOut]:
    rows = ReminderRepository(db).list_for_user(identity.user_id, status=status)
    return [ReminderOut.model_validate(r) for r in rows]


@router.post("")
def create_reminder(
    body: ReminderCreate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ReminderOut:
    service = ReminderService(db)
    row = service.create(identity.user_id, body.model_dump(exclude_none=False))
    return ReminderOut.model_validate(row)


@router.get("/{reminder_id}")
def get_reminder(
    reminder_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ReminderOut:
    row = ReminderRepository(db).get(identity.user_id, reminder_id)
    if row is None:
        from core.errors import not_found

        raise not_found("reminder")
    return ReminderOut.model_validate(row)


@router.put("/{reminder_id}")
def update_reminder(
    reminder_id: str,
    body: ReminderUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ReminderOut:
    service = ReminderService(db)
    data = body.model_dump(exclude_unset=True)
    row = service.update(identity.user_id, reminder_id, data)
    return ReminderOut.model_validate(row)


@router.patch("/{reminder_id}")
def patch_reminder(
    reminder_id: str,
    body: ReminderUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ReminderOut:
    return update_reminder(reminder_id, body, identity, db)


@router.post("/{reminder_id}/cancel")
def cancel_reminder(
    reminder_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ReminderOut:
    service = ReminderService(db)
    row = service.cancel(identity.user_id, reminder_id)
    return ReminderOut.model_validate(row)


@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict[str, Any]:
    service = ReminderService(db)
    ok = service.delete(identity.user_id, reminder_id)
    if not ok:
        from core.errors import not_found

        raise not_found("reminder")
    return {"deleted": True, "id": reminder_id}


@router.post("/process-due")
def process_due(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict[str, Any]:
    service = ReminderService(db)
    fired = service.process_due()
    return {"fired": fired}


@notifications_router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[NotificationOut]:
    rows = NotificationRepository(db).list_for_user(identity.user_id, unread_only=unread_only, limit=limit)
    return [NotificationOut.model_validate(r) for r in rows]


@notifications_router.post("")
def create_notification(
    body: dict[str, Any],
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> NotificationOut:
    # Minimal manual notification creation (no external provider).
    from apps.api.schemas import NotificationCreate

    parsed = NotificationCreate.model_validate(body)
    row = NotificationRepository(db).create(
        {
            "user_id": identity.user_id,
            "title": parsed.title,
            "body": parsed.body,
            "channel": parsed.channel,
            "reminder_id": parsed.reminder_id,
            "status": "QUEUED",
        }
    )
    return NotificationOut.model_validate(row)


@notifications_router.post("/{notification_id}/read")
def read_notification(
    notification_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> NotificationOut:
    row = NotificationRepository(db).mark_read(identity.user_id, notification_id)
    return NotificationOut.model_validate(row)
