from __future__ import annotations

import logging

import threading
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.error_handlers import register_error_handlers
from apps.api.routes import android, auth, briefings, chat, diagnostics, goals, health, memory, meta, planner, profile, projects, reminders, tasks, tools, voice
from core.config import get_settings
from core.scheduler import SchedulerRuntime, scheduler_running

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def _scheduler_worker(runtime: SchedulerRuntime) -> None:
    from core.briefings.service import BriefingService
    from core.db.base import get_session_factory
    from core.reminders.service import ReminderService

    runtime.state = "running"
    while not runtime.should_stop():
        db = None
        try:
            db = get_session_factory()()
            ReminderService(db).process_due()
            BriefingService(db).process_due()
        except Exception as exc:  # noqa: BLE001
            runtime.last_error = f"{type(exc).__name__}: {exc}"
        finally:
            if db is not None:
                db.close()
        runtime.sleep(30)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from core.briefings.service import BriefingService
    from core.db.base import get_session_factory
    from core.reminders.service import ReminderService

    # Safe catch-up before the scheduler starts; also retries on the regular loop.
    db = get_session_factory()()
    try:
        ReminderService(db).process_due(catch_up=True)
        BriefingService(db).process_due()
    except Exception:  # noqa: BLE001
        pass
    finally:
        db.close()

    runtime = SchedulerRuntime.shared()
    runtime.interval_seconds = 30
    started = runtime.start(_scheduler_worker)
    app.state.scheduler = runtime
    yield
    runtime.stop()



def create_app() -> FastAPI:
    settings = get_settings()

    if settings.is_production and not settings.is_dev_auth:
        # Phase 1: only the dev shim exists. Fail fast rather than pretend.
        raise RuntimeError(
            "AUTH_MODE=supabase is not implemented yet; production boot is blocked "
            "until a real auth provider ships (Phase 9)."
        )
    if settings.is_production and settings.is_dev_auth:
        raise RuntimeError("AUTH_MODE=dev must never run with ENV=production.")

    app = FastAPI(
        title="JARVIS API",
        version=settings.app_version,
        description="Personal AI operating system — Phase 3 voice + reminders milestone.",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(meta.router)
    app.include_router(diagnostics.router)
    app.include_router(auth.router)
    app.include_router(profile.router)

    for prefix in ("/api/v1/memory", "/api/v1/memories"):
        app.include_router(memory.router, prefix=prefix)
    for prefix in ("/api/v1/goals", "/api/v1/me/goals"):
        app.include_router(goals.router, prefix=prefix)
    for prefix in ("/api/v1/tasks", "/api/v1/me/tasks"):
        app.include_router(tasks.router, prefix=prefix)
    for prefix in ("/api/v1/chat", "/api/v1/chats"):
        app.include_router(chat.router, prefix=prefix)
    for prefix in ("/api/v1/reminders", "/api/v1/me/reminders"):
        app.include_router(reminders.router, prefix=prefix)
    for prefix in ("/api/v1/notifications", "/api/v1/me/notifications"):
        app.include_router(reminders.notifications_router, prefix=prefix)
    for prefix in ("/api/v1/planner", "/api/v1/daily-planner", "/api/v1/daily_plan"):
        app.include_router(planner.router, prefix=prefix)
    for prefix in ("/api/v1/briefings", "/api/v1/briefing"):
        app.include_router(briefings.router, prefix=prefix)
    for prefix in ("/api/v1/projects", "/api/v1/goals/progress"):
        app.include_router(projects.router, prefix=prefix)
    for prefix in ("/api/v1",):
        app.include_router(voice.router, prefix=prefix)
    for prefix in ("/api/v1/android", "/api/v1/termux"):
        app.include_router(android.router, prefix=prefix)
    for prefix in ("/api/v1",):
        app.include_router(tools.router, prefix=prefix)
    return app


app = create_app()
