"""Morning/evening briefings generated from real stored data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session as OrmSession

from core.db.repositories import (
    BriefingRunRepository,
    BriefingSettingRepository,
    NotificationRepository,
    TaskRepository,
    UserRepository,
)
from core.planner.daily import DailyPlannerService
from core.scheduler import PROCESSING_LOCK


class BriefingService:
    def __init__(self, db: OrmSession, planner: DailyPlannerService | None = None) -> None:
        self.db = db
        self.settings_repo = BriefingSettingRepository(db)
        self.runs_repo = BriefingRunRepository(db)
        self.notifications = NotificationRepository(db)
        self.tasks = TaskRepository(db)
        self.users = UserRepository(db)
        self.planner = planner or DailyPlannerService(db)

    @staticmethod
    def _zone(name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name or "UTC")
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    @staticmethod
    def _time_minutes(value: str) -> int:
        try:
            hh, mm = value.split(":", 1)
            return int(hh) * 60 + int(mm)
        except (ValueError, AttributeError):
            return 0

    def generate_morning(self, user_id: str, timezone_name: str | None = None) -> dict:
        tz = self._zone(timezone_name or "UTC")
        setting = self.settings_repo.get_or_create(user_id)
        tz = self._zone(setting.timezone or timezone_name or "UTC")
        now_local = datetime.now(tz)
        plan = self.planner.build(user_id, for_date=now_local.date(), timezone_name=setting.timezone)
        recommended = plan.get("recommended", [])
        top = recommended[:5]
        title = "Good morning — here is your briefing"
        content = {
            "welcome": f"Good morning. Today is {now_local.strftime('%A, %d %B %Y')}.",
            "date": now_local.date().isoformat(),
            "timezone": setting.timezone,
            "top_priorities": top,
            "overdue": plan.get("overdue", [])[:10],
            "upcoming_deadlines": sorted(
                [t for t in plan.get("tasks_today", [])], key=lambda x: x.get("deadline") or ""
            )[:10],
            "upcoming_reminders": plan.get("upcoming_reminders", [])[:10],
            "suggested_next_action": (top[0]["title"] if top else "No open tasks are scheduled; review your goals."),
            "counts": plan.get("counts", {}),
        }
        return {"kind": "morning", "title": title, "content": content}

    def generate_evening(self, user_id: str, timezone_name: str | None = None) -> dict:
        tz_name = timezone_name or "UTC"
        setting = self.settings_repo.get_or_create(user_id)
        tz = self._zone(setting.timezone or tz_name)
        now_local = datetime.now(tz)
        plan = self.planner.build(user_id, for_date=now_local.date(), timezone_name=setting.timezone)
        open_tasks = [t for t in self.tasks.list_for_user(user_id) if t.status not in {"DONE", "CANCELLED"}]
        title = "Evening review"
        content = {
            "date": now_local.date().isoformat(),
            "timezone": setting.timezone,
            "completed_today": plan.get("completed_today", []),
            "pending": [self._task(t) for t in open_tasks[:15]],
            "overdue": plan.get("overdue", [])[:10],
            "goal_progress": plan.get("active_goals", []),
            "suggestions_for_tomorrow": [
                "Carry over the highest-priority open task first.",
                "Review any overdue items before adding new work.",
            ],
            "counts": plan.get("counts", {}),
        }
        return {"kind": "evening", "title": title, "content": content}

    def run_now(self, user_id: str, kind: str, timezone_name: str | None = None) -> dict:
        if kind == "morning":
            result = self.generate_morning(user_id, timezone_name)
        elif kind == "evening":
            result = self.generate_evening(user_id, timezone_name)
        else:
            raise ValueError("kind must be morning or evening")
        setting = self.settings_repo.get_or_create(user_id)
        run = self.runs_repo.create(
            {
                "user_id": user_id,
                "kind": kind,
                "run_for_date": result["content"].get("date", datetime.now(timezone.utc).date().isoformat()),
                "scheduled_time": (setting.morning_time if kind == "morning" else setting.evening_time),
                "status": "COMPLETED",
                "title": result["title"],
                "content": result["content"],
            }
        )
        self.db.flush()
        # Best-effort notification history entry; no claim of device delivery.
        self.notifications.create(
            {
                "user_id": user_id,
                "title": result["title"],
                "body": result["content"].get("suggested_next_action", "Open JARVIS to review your briefing."),
                "channel": "web",
                "status": "QUEUED",
            }
        )
        result["run_id"] = run.id
        return result

    def process_due(self) -> int:
        processed = 0
        with PROCESSING_LOCK:
            for user in self.users.list_all():
                try:
                    setting = self.settings_repo.get_or_create(user.id)
                    tz = self._zone(setting.timezone)
                    now_local = datetime.now(tz)
                    today = now_local.date().isoformat()
                    now_minutes = now_local.hour * 60 + now_local.minute
                    for kind, enabled, time_value, last_attr in (
                        ("morning", setting.morning_enabled, setting.morning_time, "morning_last_run_on"),
                        ("evening", setting.evening_enabled, setting.evening_time, "evening_last_run_on"),
                    ):
                        if not enabled:
                            continue
                        if getattr(setting, last_attr) == today:
                            continue
                        if now_minutes < self._time_minutes(time_value):
                            continue
                        existing = self.runs_repo.get_for_date(user.id, kind, today)
                        if existing is not None:
                            setattr(setting, last_attr, today)
                            self.db.add(setting)
                            self.db.flush()
                            self.db.commit()
                            continue
                        try:
                            self.run_now(user.id, kind, setting.timezone)
                            setting = self.settings_repo.get_or_create(user.id)
                            setattr(setting, last_attr, today)
                            self.db.add(setting)
                            self.db.flush()
                            self.db.commit()
                            processed += 1
                        except Exception:  # noqa: BLE001
                            self.runs_repo.create(
                                {
                                    "user_id": user.id,
                                    "kind": kind,
                                    "run_for_date": today,
                                    "scheduled_time": time_value,
                                    "status": "FAILED",
                                    "title": f"{kind.title()} briefing",
                                    "content": None,
                                    "error": "Briefing generation failed",
                                }
                            )
                            self.db.commit()
                            processed += 1
                except Exception:  # noqa: BLE001
                    # Do not let one user's processing abort the whole scheduler.
                    try:
                        self.db.rollback()
                    except Exception:  # noqa: BLE001
                        pass
        return processed

    @staticmethod
    def _task(task) -> dict:
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "deadline": task.deadline.isoformat() if getattr(task, "deadline", None) else None,
        }
