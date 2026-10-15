from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import AndroidNotifyRequest, AndroidOpenUrlRequest, AndroidSpeakRequest
from core.auth import Identity
from core.audit import record
from integrations.termux.safe_api import (
    battery_status,
    capabilities,
    device_capabilities,
    notify,
    open_url,
    speak,
    toast,
    wake_lock,
    wake_unlock,
)

router = APIRouter(tags=["android"])


def _audit(db, user_id, action, tool, result, output):
    record(
        db,
        user_id=user_id,
        agent="android",
        action=action,
        tool=tool,
        result=result,
        output_summary={"output": output} if output is not None else None,
    )
    db.commit()


@router.get("/capabilities")
def get_capabilities(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    return {
        "termux_api": capabilities(),
        "device": device_capabilities(),
        "available_commands": [name for name, ok in capabilities().items() if ok],
    }


@router.post("/notify")
def native_notify(
    body: AndroidNotifyRequest,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    from core.db.repositories import NotificationRepository

    result = notify(body.title, body.body, body.notification_id)
    row = NotificationRepository(db).create(
        {
            "user_id": identity.user_id,
            "title": body.title,
            "body": body.body,
            "channel": "termux",
            "status": "SENT" if result["ok"] else "FAILED",
            "error": result.get("error"),
        }
    )
    row.sent_at = None
    if result["ok"]:
        from core.db.models import utcnow

        row.sent_at = utcnow()
        row.status = "SENT"
    else:
        row.status = "FAILED"
    db.add(row)
    db.flush()
    db.commit()
    _audit(db, identity.user_id, "android.notify", "termux-notification", "OK" if result["ok"] else "FAILED", result)
    return {"notification_id": row.id, "delivery": result}


@router.post("/speak")
def native_speak(
    body: AndroidSpeakRequest,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    result = speak(body.text, body.language)
    _audit(db, identity.user_id, "android.speak", "termux-tts-speak", "OK" if result["ok"] else "FAILED", result)
    return {"delivery": result}


@router.post("/wake-lock")
def android_wake_lock(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    result = wake_lock()
    _audit(db, identity.user_id, "android.wake_lock", "termux-wake-lock", "OK" if result.get("ok") else "FAILED", result)
    return {"delivery": result, "warning": "Wake locks consume battery and Android may still stop the process."}


@router.post("/wake-unlock")
def android_wake_unlock(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    result = wake_unlock()
    _audit(db, identity.user_id, "android.wake_unlock", "termux-wake-unlock", "OK" if result.get("ok") else "FAILED", result)
    return {"delivery": result}


@router.post("/open-url")
def native_open_url(
    body: AndroidOpenUrlRequest,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    if not body.confirm:
        from core.errors import AppError

        raise AppError(
            "CONFIRMATION_REQUIRED",
            "URL opening requires explicit confirmation.",
            what_failed="Android URL action",
            what_happened="confirm was false.",
            what_next="Set confirm=true after reviewing the URL.",
            status_code=400,
        )
    result = open_url(body.url)
    _audit(db, identity.user_id, "android.open_url", "termux-open-url", "OK" if result["ok"] else "FAILED", result)
    return {"delivery": result}


@router.get("/device")
def device_status(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    battery = battery_status()
    _audit(db, identity.user_id, "android.device", "termux-battery-status", "OK", battery)
    return {"battery": battery, "capabilities": device_capabilities()}


@router.post("/toast")
def native_toast(
    body: dict,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    result = toast(str(body.get("message", "")), bool(body.get("short", True)))
    _audit(db, identity.user_id, "android.toast", "termux-toast", "OK" if result["ok"] else "FAILED", result)
    return {"delivery": result}
