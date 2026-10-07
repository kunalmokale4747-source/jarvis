from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.error_handlers import register_error_handlers
from apps.api.routes import auth, health, meta, profile
from core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


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
        description="Personal AI operating system — Phase 1 foundation API.",
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
    app.include_router(auth.router)
    app.include_router(profile.router)
    return app


app = create_app()
