"""Daily planning calculations based only on stored records."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session as OrmSession

from core.db.models import utcnow
from core.db.repositories import GoalRepository, ReminderRepository, TaskRepository


class DailyPlannerService:
    def __init__(self, db: OrmSession) -> None:
        self.db = db
        self.tasks = TaskRepository(db)
        self.goals = GoalRepository(db)
        self.reminders = ReminderRepository(db)

    def _parse_date(self, value: str | date | None) -> date:
        if value is None:
            return datetime.now(timezone.utc).date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def _is_today(self, dt: datetime | None, target: date) -> bool:
        if dt is None:
            return False
        work = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return work.astimezone(timezone.utc).date() == target

    def _is_overdue(self, task, now: datetime) -> bool:
        if task.status in {"DONE", "CANCELLED"} or task.deadline is None:
            return False
        deadline = task.deadline if task.deadline.tzinfo else task.deadline.replace(tzinfo=timezone.utc)
        return deadline < now

    def _priority_rank(self, value: str | None) -> int:
        return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(str(value or "P2"), 9)

    def build(self, user_id: str, for_date: str | date | None = None, timezone_name: str = "UTC") -> dict:
        target = self._parse_date(for_date)
        now = datetime.now(timezone.utc)
        all_tasks = self.tasks.list_for_user(user_id)
        today_tasks = [t for t in all_tasks if self._is_today(t.deadline, target) or t.status in {"TODO", "IN_PROGRESS", "BLOCKED"}]
        # Avoid duplicating done tasks in "today" unless due today.
        today_tasks = [t for t in all_tasks if self._is_today(t.deadline, target)]
        in_progress = [t for t in all_tasks if t.status == "IN_PROGRESS"]
        overdue = [t for t in all_tasks if self._is_overdue(t, now)]
        upcoming_tasks = [t for t in all_tasks if t.deadline is not None and not self._is_overdue(t, now) and t.status not in {"DONE", "CANCELLED"}]
        upcoming_tasks.sort(key=lambda t: t.deadline)
        recommended = sorted([t for t in today_tasks if t.status not in {"DONE", "CANCELLED"}], key=lambda t: (self._priority_rank(t.priority), t.deadline or datetime.max.replace(tzinfo=timezone.utc)))
        # Fall back to open tasks if none due today.
        if not recommended:
            recommended = sorted([t for t in all_tasks if t.status not in {"DONE", "CANCELLED"}], key=lambda t: (self._priority_rank(t.priority), t.deadline or datetime.max.replace(tzinfo=timezone.utc)))[:10]
        reminders = self.reminders.list_for_user(user_id, status="SCHEDULED")
        upcoming_reminders = []
        for r in reminders:
            at = r.scheduled_at if r.scheduled_at.tzinfo else r.scheduled_at.replace(tzinfo=timezone.utc)
            if now <= at <= now + timedelta(hours=48):
                upcoming_reminders.append(r)
        upcoming_reminders.sort(key=lambda r: r.scheduled_at)
        active_goals = self.goals.list_for_user(user_id, status="ACTIVE")
        goal_progress = []
        for goal in active_goals:
            linked = self.tasks.list_for_user(user_id, goal_id=goal.id)
            total = len(linked)
            done = len([t for t in linked if t.status == "DONE"])
            goal_progress.append(
                {
                    "goal_id": goal.id,
                    "title": goal.title,
                    "priority": goal.priority,
                    "status": goal.status,
                    "task_total": total,
                    "task_done": done,
                    "completion_pct": round((done / total) * 100.0, 1) if total else 0.0,
                    "deadline": goal.deadline,
                }
            )
        completed_today = [t for t in all_tasks if t.completed_at is not None and self._is_today(t.completed_at, target)]
        return {
            "date": target.isoformat(),
            "timezone": timezone_name,
            "tasks_today": [self._task_out(t) for t in today_tasks],
            "in_progress": [self._task_out(t) for t in in_progress],
            "overdue": [self._task_out(t) for t in overdue],
            "recommended": [self._task_out(t) for t in recommended],
            "completed_today": [self._task_out(t) for t in completed_today],
            "upcoming_tasks": [self._task_out(t) for t in upcoming_tasks[:15]],
            "upcoming_reminders": [self._reminder_out(r) for r in upcoming_reminders[:15]],
            "active_goals": goal_progress,
            "progress_summary": self._progress_summary(all_tasks, active_goals),
            "counts": {
                "tasks_total": len(all_tasks),
                "tasks_open": len([t for t in all_tasks if t.status not in {"DONE", "CANCELLED"}]),
                "tasks_completed_today": len(completed_today),
                "overdue": len(overdue),
                "reminders_upcoming": len(upcoming_reminders),
            },
        }

    def _progress_summary(self, tasks: Iterable, goals: Iterable) -> dict:
        tasks = list(tasks)
        total = len(tasks)
        done = len([t for t in tasks if t.status == "DONE"])
        open_tasks = len([t for t in tasks if t.status not in {"DONE", "CANCELLED"}])
        total_goals = len(list(goals))
        active_goals = len([g for g in goals if getattr(g, "status", "") == "ACTIVE"])
        return {
            "tasks_total": total,
            "tasks_done": done,
            "tasks_open": open_tasks,
            "task_completion_pct": round((done / total) * 100.0, 1) if total else 0.0,
            "goals_total": total_goals,
            "goals_active": active_goals,
        }

    def _task_out(self, task) -> dict:
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "goal_id": task.goal_id,
            "category": task.category,
            "estimated_minutes": task.estimated_minutes,
        }

    def _reminder_out(self, reminder) -> dict:
        return {
            "id": reminder.id,
            "title": reminder.title,
            "scheduled_at": reminder.scheduled_at.isoformat() if reminder.scheduled_at else None,
            "timezone": reminder.timezone,
            "status": reminder.status,
            "recurrence": reminder.recurrence,
        }
