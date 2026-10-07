"""Append-only audit trail. Every important action records one row."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as OrmSession

from core.db.models import AuditLog


def record(
    db: OrmSession,
    *,
    user_id: str | None,
    action: str,
    agent: str = "system",
    result: str = "OK",
    tool: str | None = None,
    reason: str | None = None,
    input_summary: dict[str, Any] | None = None,
    output_summary: dict[str, Any] | None = None,
    permission_level: int = 0,
    approval_id: str | None = None,
    error: str | None = None,
    correlation_id: str | None = None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        agent=agent,
        action=action,
        tool=tool,
        reason=reason,
        input_summary=input_summary,
        output_summary=output_summary,
        permission_level=permission_level,
        approval_id=approval_id,
        result=result,
        error=error,
        correlation_id=correlation_id,
    )
    db.add(row)
    db.flush()
    return row
