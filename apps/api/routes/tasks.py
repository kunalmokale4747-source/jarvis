from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import TaskCreate, TaskOut, TaskUpdate
from core.auth import Identity
from core.db.repositories import TaskRepository

router = APIRouter(tags=["tasks"])


@router.get("")
def list_tasks(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    goal_id: str | None = Query(default=None),
    overdue: bool = Query(default=False),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[TaskOut]:
    repo = TaskRepository(db)
    rows = repo.list_for_user(
        identity.user_id, status=status, priority=priority, goal_id=goal_id, overdue_only=overdue
    )
    return [TaskOut.model_validate(r) for r in rows]


@router.post("")
def create_task(
    body: TaskCreate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> TaskOut:
    repo = TaskRepository(db)
    row = repo.create(identity.user_id, body.model_dump(exclude_none=True))
    return TaskOut.model_validate(row)


@router.get("/{task_id}")
def get_task(
    task_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> TaskOut:
    repo = TaskRepository(db)
    row = repo.get(identity.user_id, task_id)
    if row is None:
        from core.errors import not_found

        raise not_found("task")
    return TaskOut.model_validate(row)


@router.put("/{task_id}")
def update_task(
    task_id: str,
    body: TaskUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> TaskOut:
    repo = TaskRepository(db)
    data = body.model_dump(exclude_unset=True)
    row = repo.update(identity.user_id, task_id, data)
    return TaskOut.model_validate(row)


@router.patch("/{task_id}")
def patch_task(
    task_id: str,
    body: TaskUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> TaskOut:
    return update_task(task_id, body, identity, db)


@router.post("/{task_id}/complete")
def complete_task(
    task_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> TaskOut:
    repo = TaskRepository(db)
    row = repo.update(identity.user_id, task_id, {"status": "DONE"})
    return TaskOut.model_validate(row)


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict:
    repo = TaskRepository(db)
    ok = repo.delete(identity.user_id, task_id)
    if not ok:
        from core.errors import not_found

        raise not_found("task")
    return {"deleted": True, "id": task_id}
