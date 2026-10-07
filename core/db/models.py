"""Phase 1 domain models.

Portability rules (docs/database.md): only portable column types;
no JSONB/ARRAY/UUID-native/tsvector. Enumerations use sa.Enum(native_enum=False)
=> VARCHAR + CHECK constraint on every engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
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
