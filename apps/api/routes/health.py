from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db
from apps.api.schemas import HealthComponent, HealthOut
from core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(db: OrmSession = Depends(get_db)) -> HealthOut:
    settings = get_settings()
    db_component = HealthComponent(status="online")
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - reported honestly, not swallowed
        db_component = HealthComponent(status="offline", detail=type(exc).__name__)

    overall = "ok" if db_component.status == "online" else "degraded"
    return HealthOut(
        status=overall,
        version=settings.app_version,
        phase=settings.current_phase,
        time=datetime.now(timezone.utc),
        components={"api": HealthComponent(status="online"), "database": db_component},
    )
