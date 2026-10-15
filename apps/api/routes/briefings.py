from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from core.auth import Identity
from core.briefings.service import BriefingService
from core.reminders.service import ReminderService

router = APIRouter(tags=["briefings"])


@router.get("/settings")
def get_settings(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    from core.db.repositories import BriefingSettingRepository

    setting = BriefingSettingRepository(db).get_or_create(identity.user_id)
    return {
        "morning_enabled": setting.morning_enabled,
        "morning_time": setting.morning_time,
        "evening_enabled": setting.evening_enabled,
        "evening_time": setting.evening_time,
        "timezone": setting.timezone,
        "morning_last_run_on": setting.morning_last_run_on,
        "evening_last_run_on": setting.evening_last_run_on,
    }


@router.put("/settings")
def update_settings(
    body: dict,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    if "timezone" in body and body.get("timezone") is not None:
        ReminderService.validate_timezone(body["timezone"])
    allowed = {
        "morning_enabled", "morning_time", "evening_enabled", "evening_time", "timezone"
    }
    payload = {k: v for k, v in (body or {}).items() if k in allowed}
    from core.db.repositories import BriefingSettingRepository

    setting = BriefingSettingRepository(db).update(identity.user_id, payload)
    return {
        "morning_enabled": setting.morning_enabled,
        "morning_time": setting.morning_time,
        "evening_enabled": setting.evening_enabled,
        "evening_time": setting.evening_time,
        "timezone": setting.timezone,
    }


@router.post("/run")
def run_briefing(
    body: dict,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    kind = str(body.get("kind", "morning")).lower()
    if kind not in {"morning", "evening"}:
        from core.errors import AppError

        raise AppError("INVALID_BRIEFING", "Invalid briefing kind.", what_failed="Briefing", what_happened="kind must be morning or evening", what_next="Send morning or evening.")
    service = BriefingService(db)
    return service.run_now(identity.user_id, kind)


@router.get("/morning")
def morning(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    # Regenerate without storing? Keep store semantics consistent.
    return BriefingService(db).run_now(identity.user_id, "morning")


@router.get("/evening")
def evening(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    return BriefingService(db).run_now(identity.user_id, "evening")


@router.get("/runs")
def runs(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    from core.db.repositories import BriefingRunRepository
    from sqlalchemy import select
    from core.db.models import BriefingRun

    rows = db.scalars(
        select(BriefingRun).where(BriefingRun.user_id == identity.user_id).order_by(BriefingRun.generated_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "run_for_date": r.run_for_date,
            "status": r.status,
            "title": r.title,
            "content": r.content,
            "generated_at": r.generated_at.isoformat(),
            "error": r.error,
        }
        for r in rows
    ]
