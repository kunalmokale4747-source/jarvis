from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from core.auth import Identity
from core.db.repositories import ProfileRepository
from core.planner.daily import DailyPlannerService

router = APIRouter(tags=["planner"])


def _build(user_id, target_date, tz_name, db):
    profile = ProfileRepository(db).get_or_create(user_id)
    availability = {}
    if isinstance(profile.availability, dict):
        availability = profile.availability
    plan = DailyPlannerService(db).build(user_id, for_date=target_date, timezone_name=tz_name)
    # Attach only user-provided availability; never invent it.
    plan["availability"] = availability if availability else None
    plan["available_minutes"] = availability.get("available_minutes") if isinstance(availability, dict) else None
    return plan


@router.get("")
def daily_plan(
    date: str | None = Query(default=None),
    timezone: str = Query(default="UTC"),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    return _build(identity.user_id, date, timezone, db)


@router.get("/today")
def today_plan(
    timezone: str = Query(default="UTC"),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    return _build(identity.user_id, None, timezone, db)


@router.get("/daily")
def daily_plan_alias(
    date: str | None = Query(default=None),
    timezone: str = Query(default="UTC"),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    return _build(identity.user_id, date, timezone, db)
