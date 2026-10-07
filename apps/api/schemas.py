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
