from __future__ import annotations

import integrations as integrations_pkg
from apps.api.schemas import MetaOut
from core.config import get_settings

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/meta", response_model=MetaOut)
def meta() -> MetaOut:
    settings = get_settings()
    return MetaOut(
        name="JARVIS",
        version=settings.app_version,
        phase=settings.current_phase,
        auth_mode=settings.auth_mode,
        integrations=integrations_pkg.status(),
    )
