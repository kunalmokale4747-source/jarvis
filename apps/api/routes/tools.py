"""Safe, allowlisted tool execution endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from core.auth import Identity
from core.tools.registry import ToolContext, build_default_registry

router = APIRouter(tags=["tools"])


class ToolExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.get("/tools")
@router.get("/tools/list")
def list_tools(identity: Identity = Depends(get_identity)) -> dict[str, Any]:
    return {"tools": build_default_registry().list()}


@router.post("/tools")
@router.post("/tools/execute")
def execute_tool(
    body: ToolExecuteRequest,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict[str, Any]:
    ctx = ToolContext(user_id=identity.user_id, db=db)
    result = build_default_registry().execute(ctx, body.tool, body.arguments)
    return result.as_dict()
