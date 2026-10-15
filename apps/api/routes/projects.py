from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from core.auth import Identity
from core.db.repositories import GoalRepository, TaskRepository

router = APIRouter(tags=["projects"])


@router.get("/progress")
def project_progress(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    goals = GoalRepository(db).list_for_user(identity.user_id)
    active = [g for g in goals if g.status == "ACTIVE"]
    projects = []
    for goal in active:
        tasks = TaskRepository(db).list_for_user(identity.user_id, goal_id=goal.id)
        open_tasks = [t for t in tasks if t.status not in {"DONE", "CANCELLED"}]
        # overdue date check
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        overdue = [t for t in tasks if t.deadline is not None and (t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=timezone.utc)) < now and t.status not in {"DONE", "CANCELLED"}]
        done = len([t for t in tasks if t.status == "DONE"])
        projects.append(
            {
                "goal_id": goal.id,
                "name": goal.title,
                "description": goal.description,
                "status": goal.status,
                "priority": goal.priority,
                "deadline": goal.deadline.isoformat() if goal.deadline else None,
                "task_total": len(tasks),
                "task_done": done,
                "completion_pct": round((done / len(tasks)) * 100.0, 1) if tasks else 0.0,
                "open_tasks": len(open_tasks),
                "overdue_tasks": len(overdue),
                "upcoming_milestones": [t.id for t in sorted(tasks, key=lambda x: x.deadline or datetime.max.replace(tzinfo=timezone.utc))[:3] if t.deadline],
            }
        )
    return {"projects": projects, "total_active_projects": len(projects)}


@router.get("/goals")
def goal_progress_alias(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    # convenience alias: active goals with task progress
    return project_progress(identity, db)


@router.get("")
def list_projects(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    goals = GoalRepository(db).list_for_user(identity.user_id)
    return [{"id": g.id, "name": g.title, "status": g.status, "priority": g.priority, "deadline": g.deadline.isoformat() if g.deadline else None} for g in goals]
