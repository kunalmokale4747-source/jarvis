"""Repository layer. Every method requires a user_id (ownership is enforced here)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from core.db.models import User, UserProfile, UserSession, utcnow


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
