from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, select, text

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from core.auth import Identity
from core.config import get_settings
from core.llm import ai_status, probe_provider
from core.scheduler import SchedulerRuntime
from core.scheduler.runtime import scheduler_running
from integrations.termux.safe_api import capabilities as termux_capabilities

router = APIRouter(prefix="/api/v1", tags=["diagnostics"])


@router.get("/diagnostics")
def diagnostics(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
):
    settings = get_settings()
    db_ok = False
    db_detail = None
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        db_detail = type(exc).__name__

    sched = SchedulerRuntime.shared().status()

    ai = ai_status(settings)

    from core.db.models import (
        AuditLog,
        BriefingRun,
        Notification,
        Reminder,
        Task,
    )

    def count(model, *filters):
        stmt = select(func.count()).select_from(model)
        for flt in filters:
            stmt = stmt.where(flt)
        return int(db.scalar(stmt) or 0)

    try:
        reminders_pending = count(Reminder, Reminder.user_id == identity.user_id, Reminder.status.in_(["PENDING", "SCHEDULED"]))
        reminders_due = count(Reminder, Reminder.user_id == identity.user_id, Reminder.status.in_(["PENDING", "SCHEDULED"]), Reminder.scheduled_at <= datetime.now(timezone.utc))
        reminders_failed = count(Reminder, Reminder.user_id == identity.user_id, Reminder.status == "FAILED")
        notifications_queued = count(Notification, Notification.user_id == identity.user_id, Notification.status == "QUEUED")
        notifications_failed = count(Notification, Notification.user_id == identity.user_id, Notification.status == "FAILED")
        tasks_open = count(Task, Task.user_id == identity.user_id, Task.status.notin_(["DONE", "CANCELLED"]))
        briefing_runs = count(BriefingRun, BriefingRun.user_id == identity.user_id)
        briefing_failed = count(BriefingRun, BriefingRun.user_id == identity.user_id, BriefingRun.status == "FAILED")
    except Exception as exc:  # noqa: BLE001
        reminders_pending = reminders_due = reminders_failed = None
        notifications_queued = notifications_failed = None
        tasks_open = None
        briefing_runs = briefing_failed = None
        db_ok = False
        db_detail = type(exc).__name__

    termux_caps = termux_capabilities()
    dc = {
        "database": {"status": "online" if db_ok else "offline", "detail": db_detail},
        "scheduler": {
            "status": "online" if sched["running"] else "offline",
            "detail": sched["state"],
            "state": sched,
        },
        "ai": ai.as_dict(),
        "android": {
            "status": "online" if any(termux_caps.values()) else "offline",
            "detail": "optional Termux:API integration",
            "capabilities": termux_caps,
            "available_count": sum(1 for v in termux_caps.values() if v),
        },
    }

    overall = "ok" if db_ok else "degraded"
    return {
        "status": overall,
        "time": datetime.now(timezone.utc),
        "version": settings.app_version,
        "phase": settings.current_phase,
        "auth_mode": settings.auth_mode,
        "components": dc,
        "counts": {
            "reminders_pending_or_scheduled": reminders_pending,
            "reminders_due": reminders_due,
            "reminders_failed": reminders_failed,
            "notifications_queued": notifications_queued,
            "notifications_failed": notifications_failed,
            "tasks_open": tasks_open,
            "briefing_runs": briefing_runs,
            "briefing_runs_failed": briefing_failed,
            "audit_rows": count(AuditLog, AuditLog.user_id == identity.user_id),
        },
        "scheduler_policy": {
            "process": "single thread per API process",
            "missed_reminder_policy": "process due reminders up to catch-up window; very old one-time reminders are marked failed instead of replaying",
            "missed_briefing_policy": "generate current-day briefing only if its configured time has passed and no run exists",
            "cross_process_locking": "not coordinated; use one scheduler owner or database-level locking for multiple workers",
        },
    }

@router.get("/diagnostics/provider")
def provider_probe(
    live: bool = False,
    identity: Identity = Depends(get_identity),
):
    settings = get_settings()
    result = {
        "configured_status": ai_status(settings).as_dict(),
        "live_probe": "not_requested",
    }
    if not live:
        return result
    try:
        result["live_probe"] = probe_provider(settings, timeout_seconds=5.0)
    except Exception as exc:  # noqa: BLE001
        result["live_probe"] = {"live_status": "unexpected_error", "detail": type(exc).__name__}
    return result

