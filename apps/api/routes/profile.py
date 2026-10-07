from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import ProfileOut, ProfileUpdate
from core.audit import record
from core.auth import Identity
from core.db.repositories import ProfileRepository

router = APIRouter(prefix="/api/v1/me/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ProfileOut:
    profile = ProfileRepository(db).get_or_create(identity.user_id)
    return ProfileOut.model_validate(profile)


@router.put("", response_model=ProfileOut)
def update_profile(
    body: ProfileUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ProfileOut:
    data = body.model_dump(exclude_unset=True)
    profile = ProfileRepository(db).update(identity.user_id, data)
    record(
        db,
        user_id=identity.user_id,
        agent="user",
        action="profile.update",
        result="OK",
        input_summary={"fields": sorted(data.keys())},
        output_summary={"is_complete": profile.is_complete},
    )
    db.commit()
    return ProfileOut.model_validate(profile)
