"""Application error type carrying the JARVIS failure-reporting contract.

Every failure surfaced to a client answers:
  what failed -> why -> what already happened -> what needs to happen next.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        what_failed: str,
        what_happened: str,
        what_next: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.what_failed = what_failed
        self.what_happened = what_happened
        self.what_next = what_next
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "what_failed": self.what_failed,
            "what_happened": self.what_happened,
            "what_next": self.what_next,
        }
        if self.details:
            payload["details"] = self.details
        return payload


def unauthorized(message: str = "Authentication required.") -> AppError:
    return AppError(
        "UNAUTHORIZED",
        message,
        what_failed="Authentication",
        what_happened="No valid session token was supplied.",
        what_next="Log in again to obtain a session token.",
        status_code=401,
    )


def not_found(resource: str) -> AppError:
    return AppError(
        "NOT_FOUND",
        f"{resource} not found.",
        what_failed=f"Fetching {resource}",
        what_happened="The requested resource does not exist.",
        what_next="Check the identifier and try again.",
        status_code=404,
    )


def conflict(message: str, *, what_next: str = "Refresh and try again.") -> AppError:
    return AppError(
        "CONFLICT",
        message,
        what_failed="The requested change",
        what_happened=message,
        what_next=what_next,
        status_code=409,
    )


def unavailable(component: str, *, what_next: str) -> AppError:
    return AppError(
        "UNAVAILABLE",
        f"{component} is not available.",
        what_failed=component,
        what_happened=f"{component} is not configured or not implemented yet.",
        what_next=what_next,
        status_code=503,
    )
