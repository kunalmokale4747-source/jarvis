from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session as OrmSession

from core.auth import Identity, build_auth_provider
from core.db.base import get_session_factory
from core.errors import unauthorized


def get_db() -> Generator[OrmSession, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_identity(request: Request, db: OrmSession = Depends(get_db)) -> Identity:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise unauthorized()
    token = header.split(" ", 1)[1].strip()
    provider = build_auth_provider(db)
    return provider.verify(token)
