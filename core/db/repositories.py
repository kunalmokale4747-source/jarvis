"""Repository layer. Every method requires a user_id (ownership is enforced here)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from core.db.models import (
    User, UserProfile, UserSession, Memory, Goal, Task, ChatSession, ChatMessage, utcnow,
)


class UserRepository:
    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def get(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower().strip()))

    def create(self, email: str, display_name: str | None = None, auth_provider: str = "dev") -> User:
        user = User(email=email.lower().strip(), display_name=display_name, auth_provider=auth_provider)
        self.db.add(user)
        self.db.flush()
        return user

    def get_or_create_by_email(self, email: str, display_name: str | None = None) -> tuple[User, bool]:
        existing = self.get_by_email(email)
        if existing:
            return existing, False
        return self.create(email, display_name=display_name), True

    def list_all(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.created_at)))


class ProfileRepository:
    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def get(self, user_id: str) -> UserProfile | None:
        return self.db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))

    def get_or_create(self, user_id: str) -> UserProfile:
        profile = self.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.db.add(profile)
            self.db.flush()
        return profile

    def update(self, user_id: str, data: dict) -> UserProfile:
        profile = self.get_or_create(user_id)
        for key, value in data.items():
            if not hasattr(profile, key) or key in {"id", "user_id", "created_at", "updated_at"}:
                continue
            setattr(profile, key, value)
        profile.is_complete = bool(profile.name and profile.name.strip())
        profile.updated_at = utcnow()
        self.db.add(profile)
        self.db.flush()
        return profile


class SessionRepository:
    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def create(self, user_id: str, token_hash: str, expires_at: datetime, user_agent: str | None = None) -> UserSession:
        row = UserSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at, user_agent=user_agent)
        self.db.add(row)
        self.db.flush()
        return row

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        return self.db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))

    def revoke(self, token_hash: str) -> None:
        row = self.get_by_token_hash(token_hash)
        if row and row.revoked_at is None:
            row.revoked_at = utcnow()
            self.db.add(row)
            self.db.flush()


class MemoryRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def get(self, user_id: str, memory_id: str) -> "Memory | None":
        from core.db.models import Memory

        row = self.db.get(Memory, memory_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    def list_for_user(self, user_id: str, types: list[str] | None = None, limit: int = 200) -> list["Memory"]:
        from sqlalchemy import select

        from core.db.models import Memory

        stmt = select(Memory).where(Memory.user_id == user_id).order_by(Memory.updated_at.desc())
        if types:
            stmt = stmt.where(Memory.type.in_(types))
        stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))


class GoalRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def get(self, user_id: str, goal_id: str) -> "Goal | None":
        from core.db.models import Goal

        row = self.db.get(Goal, goal_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    def list_for_user(
        self, user_id: str, *, status: str | None = None, parent_id: str | None = None, kind: str | None = None
    ) -> list["Goal"]:
        from sqlalchemy import select

        from core.db.models import Goal

        stmt = select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at.desc())
        if status is not None:
            stmt = stmt.where(Goal.status == status)
        if parent_id is not None:
            stmt = stmt.where(Goal.parent_id == parent_id)
        if kind is not None:
            stmt = stmt.where(Goal.kind == kind)
        return list(self.db.scalars(stmt))

    def create(self, user_id: str, data: dict) -> "Goal":
        from core.db.models import Goal

        row = Goal(user_id=user_id, **_clean(data, {"id", "user_id"}))
        self.db.add(row)
        self.db.flush()
        return row

    def update(self, user_id: str, goal_id: str, data: dict) -> "Goal":
        from core.errors import not_found

        row = self.get(user_id, goal_id)
        if row is None:
            raise not_found("goal")
        for key, value in data.items():
            if key in {"id", "user_id", "created_at", "updated_at"}:
                continue
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return row

    def delete(self, user_id: str, goal_id: str) -> bool:
        row = self.get(user_id, goal_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True


class TaskRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def get(self, user_id: str, task_id: str) -> "Task | None":
        from core.db.models import Task

        row = self.db.get(Task, task_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    def list_for_user(
        self,
        user_id: str,
        *,
        status: str | None = None,
        priority: str | None = None,
        goal_id: str | None = None,
        overdue_only: bool = False,
    ) -> list["Task"]:
        from datetime import datetime, timezone

        from sqlalchemy import select

        from core.db.models import Task

        stmt = select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if goal_id is not None:
            stmt = stmt.where(Task.goal_id == goal_id)
        rows = list(self.db.scalars(stmt))
        if overdue_only:
            now = datetime.now(timezone.utc)
            rows = [
                r for r in rows
                if r.deadline is not None
                and (r.deadline if r.deadline.tzinfo else r.deadline.replace(tzinfo=timezone.utc)) < now
                and r.status not in {"DONE", "CANCELLED"}
            ]
        return rows

    def create(self, user_id: str, data: dict) -> "Task":
        from core.db.models import Task

        row = Task(user_id=user_id, **_clean(data, {"id", "user_id"}))
        self.db.add(row)
        self.db.flush()
        return row

    def update(self, user_id: str, task_id: str, data: dict) -> "Task":
        from core.errors import not_found

        row = self.get(user_id, task_id)
        if row is None:
            raise not_found("task")
        for key, value in data.items():
            if key in {"id", "user_id", "created_at", "updated_at"}:
                continue
            if hasattr(row, key):
                setattr(row, key, value)
        from core.db.models import utcnow

        row.updated_at = utcnow()
        if row.status == "DONE" and row.completed_at is None:
            row.completed_at = utcnow()
        if row.status == "IN_PROGRESS" and row.started_at is None:
            row.started_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return row

    def delete(self, user_id: str, task_id: str) -> bool:
        row = self.get(user_id, task_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True


class ChatRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def create_session(self, user_id: str, title: str | None = None) -> "ChatSession":
        from core.db.models import ChatSession

        row = ChatSession(user_id=user_id, title=title)
        self.db.add(row)
        self.db.flush()
        return row

    def get_session(self, user_id: str, session_id: str) -> "ChatSession | None":
        from core.db.models import ChatSession

        row = self.db.get(ChatSession, session_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    def list_sessions(self, user_id: str, limit: int = 50) -> list["ChatSession"]:
        from sqlalchemy import select

        from core.db.models import ChatSession

        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def add_message(
        self, session_id: str, user_id: str, role: str, content: str, **kwargs
    ) -> "ChatMessage":
        from core.db.models import ChatMessage, ChatSession

        row = ChatMessage(session_id=session_id, user_id=user_id, role=role, content=content, **kwargs)
        self.db.add(row)
        session = self.db.get(ChatSession, session_id)
        if session is not None:
            session.message_count = (session.message_count or 0) + 1
            session.updated_at = utcnow()
            self.db.add(session)
        self.db.flush()
        return row

    def list_messages(self, session_id: str, limit: int | None = None) -> list["ChatMessage"]:
        from sqlalchemy import select

        from core.db.models import ChatMessage

        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
        rows = list(self.db.scalars(stmt))
        if limit is not None and limit > 0:
            rows = rows[-limit:]
        return rows


def _clean(data: dict, forbidden: set[str]) -> dict:
    return {k: v for k, v in (data or {}).items() if k not in forbidden}


class ReminderRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def get(self, user_id: str, reminder_id: str) -> "Reminder | None":
        from core.db.models import Reminder

        row = self.db.get(Reminder, reminder_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    def list_for_user(self, user_id: str, *, status: str | None = None) -> list["Reminder"]:
        from sqlalchemy import select

        from core.db.models import Reminder

        stmt = select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.scheduled_at.asc())
        if status is not None:
            stmt = stmt.where(Reminder.status == status)
        return list(self.db.scalars(stmt))

    def due(self, now) -> list["Reminder"]:
        from sqlalchemy import select

        from core.db.models import Reminder

        stmt = select(Reminder).where(
            Reminder.status.in_(["PENDING", "SCHEDULED"]),
            Reminder.scheduled_at <= now,
        )
        return list(self.db.scalars(stmt))

    def create(self, user_id: str, data: dict) -> "Reminder":
        from core.db.models import Reminder

        row = Reminder(user_id=user_id, **_clean(data, {"id", "user_id"}))
        self.db.add(row)
        self.db.flush()
        return row

    def update(self, user_id: str, reminder_id: str, data: dict) -> "Reminder":
        from core.errors import not_found

        row = self.get(user_id, reminder_id)
        if row is None:
            raise not_found("reminder")
        for key, value in data.items():
            if key in {"id", "user_id", "created_at", "updated_at"}:
                continue
            if hasattr(row, key):
                setattr(row, key, value)
        from core.db.models import utcnow

        row.updated_at = utcnow()
        if row.status in {"FIRED", "CANCELLED"} and data.get("scheduled_at") is not None:
            row.status = "SCHEDULED"
            row.last_fired_at = None
        self.db.add(row)
        self.db.flush()
        return row

    def cancel(self, user_id: str, reminder_id: str) -> "Reminder":
        from core.db.models import utcnow

        row = self.get(user_id, reminder_id)
        if row is None:
            from core.errors import not_found

            raise not_found("reminder")
        row.status = "CANCELLED"
        row.updated_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return row

    def delete(self, user_id: str, reminder_id: str) -> bool:
        row = self.get(user_id, reminder_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True


class NotificationRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def get(self, user_id: str, notification_id: str) -> "Notification | None":
        from core.db.models import Notification

        row = self.db.get(Notification, notification_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    def list_for_user(self, user_id: str, *, unread_only: bool = False, limit: int = 100) -> list["Notification"]:
        from sqlalchemy import select

        from core.db.models import Notification

        stmt = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(limit)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        return list(self.db.scalars(stmt))

    def create(self, data: dict) -> "Notification":
        from core.db.models import Notification

        row = Notification(**_clean(data, {"id"}))
        self.db.add(row)
        self.db.flush()
        return row

    def mark_read(self, user_id: str, notification_id: str) -> "Notification":
        from core.db.models import utcnow
        from core.errors import not_found

        row = self.get(user_id, notification_id)
        if row is None:
            raise not_found("notification")
        row.read_at = utcnow()
        row.status = "READ"
        self.db.add(row)
        self.db.flush()
        return row


class BriefingSettingRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def get_or_create(self, user_id: str) -> "BriefingSetting":
        from core.db.models import BriefingSetting

        from sqlalchemy import select as _select

        row = self.db.scalar(_select(BriefingSetting).where(BriefingSetting.user_id == user_id))
        if row is None:
            row = BriefingSetting(user_id=user_id)
            self.db.add(row)
            self.db.flush()
        return row

    def update(self, user_id: str, data: dict) -> "BriefingSetting":
        from core.db.models import utcnow

        row = self.get_or_create(user_id)
        for key, value in (data or {}).items():
            if key in {"id", "user_id", "created_at", "updated_at"} or not hasattr(row, key):
                continue
            setattr(row, key, value)
        row.updated_at = utcnow()
        self.db.add(row)
        self.db.flush()
        return row


class BriefingRunRepository:
    def __init__(self, db: "OrmSession") -> None:
        self.db = db

    def get_for_date(self, user_id: str, kind: str, run_for_date: str) -> "BriefingRun | None":
        from sqlalchemy import select

        from core.db.models import BriefingRun

        return self.db.scalar(
            select(BriefingRun).where(
                BriefingRun.user_id == user_id,
                BriefingRun.kind == kind,
                BriefingRun.run_for_date == run_for_date,
            )
        )

    def create(self, data: dict) -> "BriefingRun":
        from core.db.models import BriefingRun

        from core.db.models import BriefingRun

        row = BriefingRun(**_clean(data, {"id"}))
        self.db.add(row)
        self.db.flush()
        return row
