from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import GoalCreate, GoalOut, GoalUpdate
from core.auth import Identity
from core.db.repositories import GoalRepository

router = APIRouter(tags=["goals"])


@router.get("")
def list_goals(
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[GoalOut]:
    repo = GoalRepository(db)
    rows = repo.list_for_user(identity.user_id, status=status, kind=kind)
    return [GoalOut.model_validate(r) for r in rows]


@router.post("")
def create_goal(
    body: GoalCreate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> GoalOut:
    repo = GoalRepository(db)
    row = repo.create(identity.user_id, body.model_dump(exclude_none=True))
    return GoalOut.model_validate(row)


@router.get("/{goal_id}")
def get_goal(
    goal_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> GoalOut:
    repo = GoalRepository(db)
    row = repo.get(identity.user_id, goal_id)
    if row is None:
        from core.errors import not_found

        raise not_found("goal")
    return GoalOut.model_validate(row)


@router.put("/{goal_id}")
def update_goal(
    goal_id: str,
    body: GoalUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> GoalOut:
    repo = GoalRepository(db)
    data = body.model_dump(exclude_unset=True)
    row = repo.update(identity.user_id, goal_id, data)
    return GoalOut.model_validate(row)


@router.patch("/{goal_id}")
def patch_goal(
    goal_id: str,
    body: GoalUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> GoalOut:
    return update_goal(goal_id, body, identity, db)


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict:
    repo = GoalRepository(db)
    ok = repo.delete(identity.user_id, goal_id)
    if not ok:
        from core.errors import not_found

        raise not_found("goal")
    return {"deleted": True, "id": goal_id}
