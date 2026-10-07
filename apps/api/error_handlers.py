from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.errors import AppError

logger = logging.getLogger("jarvis.api")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "what_failed": "Input validation",
                "what_happened": "The request body or parameters did not match the expected schema.",
                "what_next": "Correct the highlighted fields and retry.",
                "details": {"errors": exc.errors()[:20]},
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Unexpected server error.",
                "what_failed": f"{request.method} {request.url.path}",
                "what_happened": "An unexpected error occurred inside the API; it has been logged.",
                "what_next": "Retry once; if it persists, check API logs for the stack trace.",
            },
        )
