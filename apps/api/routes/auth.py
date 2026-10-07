from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import IdentityOut, LoginRequest, LoginResponse, UserOut
from core.audit import record
from core.auth import DevAuthProvider, Identity, build_auth_provider
from core.config import get_settings
from core.db.repositories import UserRepository
from core.errors import AppError, unauthorized

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _supabase_unavailable() -> AppError:
    return AppError(
        "AUTH_NOT_IMPLEMENTED",
        "Supabase Auth is not implemented yet.",
        what_failed="Authentication provider",
        what_happened="AUTH_MODE is set to a provider that has not been implemented.",
        what_next="Phase 1 supports AUTH_MODE=dev only; configure Supabase in a later phase.",
        status_code=503,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: OrmSession = Depends(get_db),
) -> LoginResponse:
    """Dev-only login: provision the user and issue a session token."""
    settings = get_settings()
    if not settings.is_dev_auth:
        raise _supabase_unavailable()

    provider = build_auth_provider(db)
    if not isinstance(provider, DevAuthProvider):
        raise _supabase_unavailable()

    user, created = UserRepository(db).get_or_create_by_email(
        body.email, display_name=body.display_name
    )
    token, expires_at = provider.issue(
        user_id=user.id, user_agent=request.headers.get("user-agent")
    )
    record(
        db,
        user_id=user.id,
        agent="system",
        action="auth.login",
        result="OK",
        input_summary={"email": user.email, "created": created},
        output_summary={"session": "issued"},
        correlation_id=request.headers.get("x-request-id"),
    )
    return LoginResponse(token=token, expires_at=expires_at, user=UserOut.model_validate(user))


@router.get("/me", response_model=IdentityOut)
def me(identity: Identity = Depends(get_identity), db: OrmSession = Depends(get_db)) -> IdentityOut:
    user = UserRepository(db).get(identity.user_id)
    if user is None:
        raise unauthorized("Session owner no longer exists.")
    return IdentityOut(
        user_id=identity.user_id,
        email=identity.email,
        mode=identity.mode,
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
def logout(
    request: Request,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict[str, str]:
    header = request.headers.get("authorization", "")
    token = header.split(" ", 1)[1].strip() if " " in header else ""
    provider = build_auth_provider(db)
    provider.revoke(token)
    record(
        db,
        user_id=identity.user_id,
        agent="system",
        action="auth.logout",
        result="OK",
    )
    return {"status": "logged_out"}
