"""Phase 1 domain models.

Portability rules (docs/database.md): only portable column types;
no JSONB/ARRAY/UUID-native/tsvector. Enumerations use sa.Enum(native_enum=False)
=> VARCHAR + CHECK constraint on every engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


def _enum(name: str, *values: str) -> Enum:
    return Enum(*values, name=name, native_enum=False, validate_strings=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(_enum("user_role", "user", "admin"), default="user", nullable=False)
    auth_provider: Mapped[str] = mapped_column(
        _enum("user_auth_provider", "dev", "supabase"), default="dev", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(200))
    education: Mapped[list | dict | None] = mapped_column(JSON)
    skills: Mapped[list | None] = mapped_column(JSON)
    experience: Mapped[list | dict | None] = mapped_column(JSON)
    projects: Mapped[list | dict | None] = mapped_column(JSON)
    career_goals: Mapped[dict | None] = mapped_column(JSON)
    business_goals: Mapped[dict | None] = mapped_column(JSON)
    financial_goals: Mapped[dict | None] = mapped_column(JSON)
    location: Mapped[str | None] = mapped_column(String(120))
    languages: Mapped[list | None] = mapped_column(JSON)
    preferences: Mapped[dict | None] = mapped_column(JSON)
    availability: Mapped[dict | None] = mapped_column(JSON)
    resume: Mapped[dict | None] = mapped_column(JSON)
    portfolio: Mapped[list | dict | None] = mapped_column(JSON)
    social_profiles: Mapped[dict | None] = mapped_column(JSON)
    professional_profiles: Mapped[dict | None] = mapped_column(JSON)
    current_priorities: Mapped[list | None] = mapped_column(JSON)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    agent: Mapped[str] = mapped_column(String(60), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(Text)
    input_summary: Mapped[dict | None] = mapped_column(JSON)
    output_summary: Mapped[dict | None] = mapped_column(JSON)
    permission_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approval_id: Mapped[str | None] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(
        _enum("audit_result", "OK", "FAILED", "BLOCKED", "DENIED", "EXPIRED"),
        nullable=False,
        default="OK",
    )
    error: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tool: Mapped[str] = mapped_column(String(120), nullable=False)
    agent: Mapped[str | None] = mapped_column(String(60))
    input: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(
        _enum("approval_risk", "low", "medium", "high", "critical"), default="medium", nullable=False
    )
    status: Mapped[str] = mapped_column(
        _enum("approval_status", "PENDING", "APPROVED", "DENIED", "EXPIRED"),
        default="PENDING",
        nullable=False,
        index=True,
    )
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── Phase 2: memory, goals, tasks, chat ──────────────────────────────


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_user_type", "user_id", "type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(
        _enum(
            "memory_type",
            "PROFILE", "GOAL", "PROJECT", "TASK", "PREFERENCE", "CONTACT",
            "OPPORTUNITY", "DECISION", "LESSON", "CONVERSATION", "FACT",
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_ref: Mapped[dict | None] = mapped_column(JSON)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    source: Mapped[str] = mapped_column(
        _enum("memory_source", "agent", "tool", "user", "import"), default="user", nullable=False
    )
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[str | None] = mapped_column(String(36))


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("goals.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(
        _enum("goal_kind", "MISSION", "OBJECTIVE", "PROJECT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metric: Mapped[str | None] = mapped_column(String(120))
    target_value: Mapped[float | None] = mapped_column(Float)
    current_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        _enum("goal_status", "ACTIVE", "PAUSED", "DONE", "CANCELLED"), default="ACTIVE", nullable=False
    )
    priority: Mapped[str] = mapped_column(
        _enum("goal_priority", "P0", "P1", "P2", "P3"), default="P2", nullable=False
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_user_status", "user_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(
        _enum("task_priority", "P0", "P1", "P2", "P3"), default="P2", nullable=False
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        _enum("task_status", "TODO", "IN_PROGRESS", "BLOCKED", "WAITING_APPROVAL", "DONE", "CANCELLED"),
        default="TODO",
        nullable=False,
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(80))
    goal_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("goals.id", ondelete="SET NULL"), index=True
    )
    parent_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(_enum("chat_role", "user", "assistant", "system"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        _enum("chat_message_status", "OK", "ERROR", "OFFLINE"), default="OK", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ── Phase 3: reminders and notification history ───────────────────────


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (Index("ix_reminders_user_scheduled", "user_id", "status", "scheduled_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC", nullable=False)
    status: Mapped[str] = mapped_column(
        _enum("reminder_status", "PENDING", "SCHEDULED", "FIRED", "CANCELLED", "FAILED"),
        default="SCHEDULED",
        nullable=False,
        index=True,
    )
    recurrence: Mapped[str] = mapped_column(
        _enum("reminder_recurrence", "none", "daily", "weekly", "monthly", "yearly"),
        default="none",
        nullable=False,
    )
    recurrence_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(
        _enum("reminder_channel", "web", "termux", "email"), default="web", nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reminder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reminders.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(40), default="web", nullable=False)
    status: Mapped[str] = mapped_column(
        _enum("notification_status", "QUEUED", "SENT", "FAILED", "READ"),
        default="QUEUED",
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ── Phase 4: briefings and proactive planning ─────────────────────────


class BriefingSetting(Base):
    __tablename__ = "briefing_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    morning_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    morning_time: Mapped[str] = mapped_column(String(8), default="07:30", nullable=False)
    evening_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evening_time: Mapped[str] = mapped_column(String(8), default="21:00", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC", nullable=False)
    morning_last_run_on: Mapped[str | None] = mapped_column(String(10))
    evening_last_run_on: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class BriefingRun(Base):
    __tablename__ = "briefing_runs"
    __table_args__ = (Index("ix_briefing_runs_user_kind_date", "user_id", "kind", "run_for_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(_enum("briefing_kind", "morning", "evening"), nullable=False)
    run_for_date: Mapped[str] = mapped_column(String(10), nullable=False)
    scheduled_time: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        _enum("briefing_run_status", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"),
        default="COMPLETED",
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
