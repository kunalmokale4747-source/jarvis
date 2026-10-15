"""Authenticated, server-mediated OpenAI Realtime session setup."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from core.auth import Identity
from core.config import get_settings

router = APIRouter(tags=["voice"])

_recent_sessions: dict[str, float] = {}


def _openai_client_secret(settings, user_email: str) -> dict[str, Any]:
    body = {
        "session": {
            "type": "realtime",
            "model": settings.openai_realtime_model,
            "audio": {"output": {"voice": settings.openai_realtime_voice}},
        },
        "expires_after": {"anchor": "created_at", "seconds": settings.openai_realtime_expires_in_seconds},
    }
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.openai_realtime_base_url.removesuffix('/')}/realtime/client_secrets",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.openai_realtime_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


@router.get("/voice/realtime/status")
def realtime_status(identity: Identity = Depends(get_identity)) -> dict[str, Any]:
    settings = get_settings()
    return {
        "enabled": settings.openai_realtime_enabled,
        "configured": bool(settings.openai_realtime_enabled and settings.openai_realtime_api_key),
        "provider": "openai-realtime" if settings.openai_realtime_enabled else None,
        "model": settings.openai_realtime_model if settings.openai_realtime_enabled else None,
        "voice": settings.openai_realtime_voice if settings.openai_realtime_enabled else None,
        "expires_in_seconds": settings.openai_realtime_expires_in_seconds,
        "sdp_endpoint": "https://api.openai.com/v1/realtime/calls" if settings.openai_realtime_enabled else None,
    }


@router.post("/voice/realtime/session")
def realtime_session(identity: Identity = Depends(get_identity), db: OrmSession = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings()
    ok = settings.openai_realtime_enabled and bool(settings.openai_realtime_api_key)
    if not ok:
        raise HTTPException(status_code=503, detail="Real-time voice is not configured.")

    now = time.time()
    last = _recent_sessions.get(identity.user_id, 0.0)
    if now - last < 10.0:
        raise HTTPException(status_code=429, detail="Please wait before starting another voice session.")
    _recent_sessions[identity.user_id] = now

    try:
        data = _openai_client_secret(settings, identity.user_id)
    except urllib.error.HTTPError as exc:
        status = exc.code
        if status == 401:
            raise HTTPException(status_code=502, detail="Real-time voice provider authentication failed.")
        if status == 429:
            raise HTTPException(status_code=502, detail="Real-time voice provider rate limit exceeded.")
        raise HTTPException(status_code=502, detail=f"Real-time voice provider returned HTTP {status}.")
    except urllib.error.URLError:
        raise HTTPException(status_code=503, detail="Real-time voice provider is unavailable.")
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Real-time voice setup timed out.")
    except Exception:
        raise HTTPException(status_code=502, detail="Real-time voice setup failed.")

    key = data.get("value") or data.get("client_secret", {}).get("value")
    if not key:
        raise HTTPException(status_code=502, detail="Real-time voice provider returned an invalid session.")

    expires_at = data.get("expires_at")
    if expires_at is None:
        expires_at = time.time() + settings.openai_realtime_expires_in_seconds

    # Keep the response minimal; never expose permanent credentials.
    return {
        "provider": "openai-realtime",
        "model": settings.openai_realtime_model,
        "voice": settings.openai_realtime_voice,
        "ephemeral_key": key,
        "expires_at": expires_at,
        "sdp_endpoint": f"{settings.openai_realtime_base_url.removesuffix('/')}/v1/realtime/calls",
        "instructions": "Ephemeral client credential only; create a short-lived audio-only WebRTC session.",
    }
