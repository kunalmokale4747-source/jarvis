"""Authentication provider interface.

Production will use Supabase Auth behind the same protocol.
Phase 1 ships the dev shim only; choosing AUTH_MODE=supabase fails fast
until that provider is actually implemented (never silently faked).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from core.config import get_settings
from core.db.models import utcnow
from core.db.repositories import SessionRepository, UserRepository
from sqlalchemy.orm import Session as OrmSession


@dataclass(frozen=True)
class Identity:
    user_id: str
    email: str
    mode: str
    session_id: str | None = None


class AuthProvider(Protocol):
    mode: str

    def verify(self, token: str) -> Identity: ...

    def revoke(self, token: str) -> None: ...


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class DevAuthProvider:
    """Local single-user shim: DB-backed sessions, random bearer tokens.

    Only usable when AUTH_MODE=dev. Never enabled in production.
    """

    mode = "dev"

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def issue(self, user_id: str, user_agent: str | None = None) -> tuple[str, "object"]:
        settings = get_settings()
        token = secrets.token_urlsafe(32)
        expires_at = utcnow() + timedelta(hours=settings.session_ttl_hours)
        row = SessionRepository(self.db).create(
            user_id=user_id,
            token_hash=_hash_token(token),
            expires_at=expires_at,
            user_agent=user_agent,
        )
        return token, expires_at

    def verify(self, token: str) -> Identity:
        from core.errors import unauthorized

        if not token:
            raise unauthorized()
        row = SessionRepository(self.db).get_by_token_hash(_hash_token(token))
        if row is None or row.revoked_at is not None:
            raise unauthorized("Session is invalid or has been revoked.")
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=utcnow().tzinfo)
        if expires <= utcnow():
            raise unauthorized("Session has expired.")
        user = UserRepository(self.db).get(row.user_id)
        if user is None:
            raise unauthorized("Session owner no longer exists.")
        return Identity(user_id=user.id, email=user.email, mode=self.mode, session_id=row.id)

    def revoke(self, token: str) -> None:
        SessionRepository(self.db).revoke(_hash_token(token))


class SupabaseAuthProvider:
    """Not implemented yet. Present so the interface is real; fails fast."""

    mode = "supabase"

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def verify(self, token: str) -> Identity:
        raise NotImplementedError(
            "Supabase Auth is not implemented yet (planned). Set AUTH_MODE=dev."
        )

    def revoke(self, token: str) -> None:
        raise NotImplementedError(
            "Supabase Auth is not implemented yet (planned). Set AUTH_MODE=dev."
        )


def build_auth_provider(db: OrmSession) -> AuthProvider:
    settings = get_settings()
    if settings.is_dev_auth:
        return DevAuthProvider(db)
    if settings.auth_mode == "supabase":
        raise NotImplementedError(
            "AUTH_MODE=supabase is not implemented yet. "
            "The Supabase Auth provider lands with cloud deployment (Phase 9); "
            "use AUTH_MODE=dev until then."
        )
    raise ValueError(f"Unknown AUTH_MODE: {settings.auth_mode!r}")
