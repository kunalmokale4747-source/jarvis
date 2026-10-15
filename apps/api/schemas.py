"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=120)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None
    auth_provider: str
    created_at: datetime


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


class IdentityOut(BaseModel):
    user_id: str
    email: str
    mode: str
    user: UserOut


class HealthComponent(BaseModel):
    status: Literal["online", "offline"]
    detail: str | None = None


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    phase: int
    time: datetime
    components: dict[str, HealthComponent]


class MetaOut(BaseModel):
    name: str
    version: str
    phase: int
    auth_mode: str
    integrations: dict[str, dict[str, Any]]
    ai: dict[str, Any] | None = None


class ProfileUpdate(BaseModel):
    """Partial update; only supplied fields change."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=120)
    languages: list[str] | None = None
    skills: list[dict[str, Any]] | None = None
    career_goals: dict[str, Any] | None = None
    business_goals: dict[str, Any] | None = None
    financial_goals: dict[str, Any] | None = None
    current_priorities: list[str] | None = None
    education: list[Any] | dict[str, Any] | None = None
    experience: list[Any] | dict[str, Any] | None = None
    projects: list[Any] | dict[str, Any] | None = None
    preferences: dict[str, Any] | None = None
    availability: dict[str, Any] | None = None
    resume: dict[str, Any] | None = None
    portfolio: list[Any] | dict[str, Any] | None = None
    social_profiles: dict[str, Any] | None = None
    professional_profiles: dict[str, Any] | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str | None
    location: str | None
    languages: list[str] | None
    skills: list[dict[str, Any]] | None
    career_goals: dict[str, Any] | None
    business_goals: dict[str, Any] | None
    financial_goals: dict[str, Any] | None
    current_priorities: list[str] | None
    education: Any | None
    experience: Any | None
    projects: Any | None
    preferences: dict[str, Any] | None
    availability: dict[str, Any] | None
    resume: dict[str, Any] | None
    portfolio: Any | None
    social_profiles: dict[str, Any] | None
    professional_profiles: dict[str, Any] | None
    is_complete: bool
    updated_at: datetime


# ── Phase 2: memory, goals, tasks, chat ──────────────────────────────
from typing import Any


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1)
    type: Literal["PROFILE","GOAL","PROJECT","TASK","PREFERENCE","CONTACT","OPPORTUNITY","DECISION","LESSON","CONVERSATION","FACT"] = "FACT"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source: Literal["agent","tool","user","import"] = "user"
    structured_ref: dict[str, Any] | None = None


class MemoryUpdate(BaseModel):
    content: str | None = None
    type: Literal["PROFILE","GOAL","PROJECT","TASK","PREFERENCE","CONTACT","OPPORTUNITY","DECISION","LESSON","CONVERSATION","FACT"] | None = None
    importance: float | None = None
    confidence: float | None = None


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    type: str
    content: str
    structured_ref: dict[str, Any] | None = None
    importance: float
    confidence: float
    source: str
    created_at: datetime
    updated_at: datetime


class MemoryHitOut(BaseModel):
    memory: MemoryOut
    score: float


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["MISSION","OBJECTIVE","PROJECT"] = "OBJECTIVE"
    description: str | None = None
    metric: str | None = None
    target_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    status: Literal["ACTIVE","PAUSED","DONE","CANCELLED"] = "ACTIVE"
    priority: Literal["P0","P1","P2","P3"] = "P2"
    deadline: datetime | None = None
    parent_id: str | None = None


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    kind: Literal["MISSION","OBJECTIVE","PROJECT"] | None = None
    description: str | None = None
    metric: str | None = None
    target_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    status: Literal["ACTIVE","PAUSED","DONE","CANCELLED"] | None = None
    priority: Literal["P0","P1","P2","P3"] | None = None
    deadline: datetime | None = None
    parent_id: str | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    parent_id: str | None
    kind: str
    title: str
    description: str | None
    metric: str | None
    target_value: float | None
    current_value: float | None
    unit: str | None
    status: str
    priority: str
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    priority: Literal["P0","P1","P2","P3"] = "P2"
    deadline: datetime | None = None
    status: Literal["TODO","IN_PROGRESS","BLOCKED","WAITING_APPROVAL","DONE","CANCELLED"] = "TODO"
    estimated_minutes: int | None = None
    category: str | None = None
    goal_id: str | None = None
    parent_task_id: str | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    priority: Literal["P0","P1","P2","P3"] | None = None
    deadline: datetime | None = None
    status: Literal["TODO","IN_PROGRESS","BLOCKED","WAITING_APPROVAL","DONE","CANCELLED"] | None = None
    estimated_minutes: int | None = None
    category: str | None = None
    goal_id: str | None = None
    parent_task_id: str | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: str | None
    priority: str
    deadline: datetime | None
    status: str
    estimated_minutes: int | None
    category: str | None
    goal_id: str | None
    parent_task_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    user_id: str
    role: str
    content: str
    provider: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    status: str
    created_at: datetime


class ChatSendRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    title: str | None = None


class ChatSendResponse(BaseModel):
    session_id: str
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    offline: bool


# ── Phase 3: reminders and notifications ─────────────────────────────
class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    message: str | None = None
    scheduled_at: datetime
    timezone: str = "UTC"
    recurrence: Literal["none", "daily", "weekly", "monthly", "yearly"] = "none"
    recurrence_interval: int = Field(default=1, ge=1)
    task_id: str | None = None
    idempotency_key: str | None = None
    channel: Literal["web", "termux", "email"] = "web"


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=300)
    message: str | None = None
    scheduled_at: datetime | None = None
    timezone: str | None = None
    recurrence: Literal["none", "daily", "weekly", "monthly", "yearly"] | None = None
    recurrence_interval: int | None = Field(default=None, ge=1)
    task_id: str | None = None
    status: Literal["PENDING", "SCHEDULED", "FIRED", "CANCELLED", "FAILED"] | None = None
    channel: Literal["web", "termux", "email"] | None = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    message: str | None
    scheduled_at: datetime
    timezone: str
    status: str
    recurrence: str
    recurrence_interval: int
    task_id: str | None
    channel: str
    last_fired_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str | None = None
    channel: str = "web"
    reminder_id: str | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    reminder_id: str | None
    title: str
    body: str | None
    channel: str
    status: str
    error: str | None
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime


# ── Phase 5: Android / Termux integration ────────────────────────────
class AndroidNotifyRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = ""
    notification_id: str | None = None


class AndroidSpeakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=8000)
    language: Literal["en-US", "hi-IN", "en-IN", "en-GB"] = "en-US"


class AndroidOpenUrlRequest(BaseModel):
    url: str
    confirm: bool = False
