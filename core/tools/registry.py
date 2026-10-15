"""Allowlisted, schema-validated tools for JARVIS.

Tools are the only structured way the assistant acts on stored data. Every call is
validated, scoped to the authenticated user, and audited.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.audit import record as audit_record
from core.db.repositories import TaskRepository, ReminderRepository, GoalRepository, MemoryRepository
from core.errors import AppError, not_found
from core.memory.service import MemoryService
from core.planner.daily import DailyPlannerService
from core.reminders.service import ReminderService


@dataclass
class ToolContext:
    user_id: str
    db: Any


@dataclass
class ToolResult:
    ok: bool
    tool: str
    output: dict[str, Any] | list[Any] | None = None
    error: str | None = None
    requires_confirmation: bool = False
    proposed_action: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "output": self.output,
            "error": self.error,
            "requires_confirmation": self.requires_confirmation,
            "proposed_action": self.proposed_action,
        }


# ── input schemas ────────────────────────────────────────────────────
class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListTasksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["TODO", "IN_PROGRESS", "BLOCKED", "WAITING_APPROVAL", "DONE", "CANCELLED"] | None = None
    priority: Literal["P0", "P1", "P2", "P3"] | None = None
    overdue: bool = False
    limit: int = Field(default=50, ge=1, le=200)


class CreateTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    priority: Literal["P0", "P1", "P2", "P3"] = "P2"
    status: Literal["TODO", "IN_PROGRESS", "BLOCKED", "WAITING_APPROVAL", "DONE", "CANCELLED"] = "TODO"
    category: str | None = None
    goal_id: str | None = None
    deadline: datetime | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)


class UpdateTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    priority: Literal["P0", "P1", "P2", "P3"] | None = None
    status: Literal["TODO", "IN_PROGRESS", "BLOCKED", "WAITING_APPROVAL", "DONE", "CANCELLED"] | None = None
    category: str | None = None
    goal_id: str | None = None
    deadline: datetime | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    confirm: bool = False


class CompleteTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str


class DeleteTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    confirm: bool = False


class ListRemindersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PENDING", "SCHEDULED", "FIRED", "CANCELLED", "FAILED"] | None = None


class CreateReminderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    message: str | None = None
    scheduled_at: datetime
    timezone: str = "UTC"
    recurrence: Literal["none", "daily", "weekly", "monthly", "yearly"] = "none"
    recurrence_interval: int = Field(default=1, ge=1)


class CancelReminderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminder_id: str


class RetrieveMemoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = ""
    types: list[str] | None = None
    limit: int = Field(default=8, ge=1, le=50)


class SaveMemoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    type: str = "FACT"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class DeleteMemoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    confirm: bool = False


class DailyPlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str | None = None
    timezone: str = "UTC"


class ProjectProgressArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass


class ConversationSummaryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None


class AndroidOpenUrlArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    confirm: bool = False


# ── registry ─────────────────────────────────────────────────────────
@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel], ToolResult]
    permission_level: int = 0
    risk_level: str = "low"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "permission_level": spec.permission_level,
                "risk_level": spec.risk_level,
                "input_schema": spec.input_model.model_json_schema(),
            }
            for spec in sorted(self._tools.values(), key=lambda s: s.name)
        ]

    def execute(self, ctx: ToolContext, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        spec = self.get(name)
        if spec is None:
            return ToolResult(ok=False, tool=name, error=f"Unknown tool: {name}")
        try:
            args = spec.input_model.model_validate(arguments or {})
        except Exception as exc:  # noqa: BLE001
            return ToolResult(ok=False, tool=name, error=f"Invalid arguments: {exc}")
        try:
            result = spec.handler(ctx, args)
            audit_record(
                ctx.db,
                user_id=ctx.user_id,
                action=f"tool.execute.{name}",
                agent="tool",
                result="OK" if result.ok else "FAILED",
                tool=name,
                input_summary={"arguments": _redact(arguments or {})},
                output_summary={"ok": result.ok, "requires_confirmation": result.requires_confirmation},
                permission_level=spec.permission_level,
            )
            ctx.db.commit()
            return result
        except AppError as exc:
            audit_record(
                ctx.db,
                user_id=ctx.user_id,
                action=f"tool.execute.{name}",
                agent="tool",
                result="FAILED",
                tool=name,
                input_summary={"arguments": _redact(arguments or {})},
                error=exc.message,
                permission_level=spec.permission_level,
            )
            ctx.db.commit()
            return ToolResult(ok=False, tool=name, error=exc.message)
        except Exception as exc:  # noqa: BLE001
            ctx.db.rollback()
            audit_record(
                ctx.db,
                user_id=ctx.user_id,
                action=f"tool.execute.{name}",
                agent="tool",
                result="FAILED",
                tool=name,
                input_summary={"arguments": _redact(arguments or {})},
                error=str(exc),
                permission_level=spec.permission_level,
            )
            try:
                ctx.db.commit()
            except Exception:  # noqa: BLE001
                ctx.db.rollback()
            return ToolResult(ok=False, tool=name, error="Tool execution failed.")


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in payload.items():
        if any(secret in key.lower() for secret in ("key", "token", "secret", "password")):
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value
    return redacted


# ── handlers ─────────────────────────────────────────────────────────
def _list_tasks(ctx: ToolContext, args: ListTasksArgs) -> ToolResult:
    tasks = TaskRepository(ctx.db).list_for_user(
        ctx.user_id, status=args.status, priority=args.priority, overdue_only=args.overdue
    )
    return ToolResult(
        ok=True,
        tool="list_tasks",
        output={
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "deadline": t.deadline.isoformat() if t.deadline else None,
                }
                for t in tasks[: args.limit]
            ],
            "count": len(tasks),
        },
    )


def _create_task(ctx: ToolContext, args: CreateTaskArgs) -> ToolResult:
    row = TaskRepository(ctx.db).create(ctx.user_id, {
        "title": args.title,
        "description": args.description,
        "priority": args.priority,
        "status": args.status,
        "category": args.category,
        "goal_id": args.goal_id,
        "deadline": args.deadline,
        "estimated_minutes": args.estimated_minutes,
    })
    return ToolResult(ok=True, tool="create_task", output={"id": row.id, "title": row.title, "status": row.status})


def _update_task(ctx: ToolContext, args: UpdateTaskArgs) -> ToolResult:
    existing = TaskRepository(ctx.db).get(ctx.user_id, args.task_id)
    if existing is None:
        raise not_found("task")
    if args.status in {"DONE", "CANCELLED", "BLOCKED", "WAITING_APPROVAL"} or args.deadline is not None or args.priority is not None:
        if not args.confirm:
            return ToolResult(
                ok=False,
                tool="update_task",
                requires_confirmation=True,
                proposed_action={"task_id": args.task_id, "changes": args.model_dump(exclude={"task_id", "confirm"}, exclude_none=True)},
                error="Confirmation required before changing this task.",
            )
    changes = args.model_dump(exclude={"task_id", "confirm"}, exclude_none=True)
    row = TaskRepository(ctx.db).update(ctx.user_id, args.task_id, changes)
    return ToolResult(ok=True, tool="update_task", output={"id": row.id, "title": row.title, "status": row.status})


def _complete_task(ctx: ToolContext, args: CompleteTaskArgs) -> ToolResult:
    row = TaskRepository(ctx.db).get(ctx.user_id, args.task_id)
    if row is None:
        raise not_found("task")
    updated = TaskRepository(ctx.db).update(ctx.user_id, args.task_id, {"status": "DONE"})
    return ToolResult(ok=True, tool="complete_task", output={"id": updated.id, "title": updated.title, "status": updated.status})


def _delete_task(ctx: ToolContext, args: DeleteTaskArgs) -> ToolResult:
    existing = TaskRepository(ctx.db).get(ctx.user_id, args.task_id)
    if existing is None:
        raise not_found("task")
    if not args.confirm:
        return ToolResult(
            ok=False,
            tool="delete_task",
            requires_confirmation=True,
            proposed_action={"task_id": args.task_id, "title": existing.title},
            error="Confirmation required before deleting this task.",
        )
    deleted = TaskRepository(ctx.db).delete(ctx.user_id, args.task_id)
    return ToolResult(ok=True, tool="delete_task", output={"deleted": deleted, "id": args.task_id})


def _list_reminders(ctx: ToolContext, args: ListRemindersArgs) -> ToolResult:
    rows = ReminderRepository(ctx.db).list_for_user(ctx.user_id, status=args.status)
    return ToolResult(
        ok=True,
        tool="list_reminders",
        output={
            "reminders": [
                {"id": r.id, "title": r.title, "scheduled_at": r.scheduled_at.isoformat(), "status": r.status, "timezone": r.timezone}
                for r in rows
            ],
            "count": len(rows),
        },
    )


def _create_reminder(ctx: ToolContext, args: CreateReminderArgs) -> ToolResult:
    row = ReminderService(ctx.db).create(ctx.user_id, args.model_dump())
    return ToolResult(ok=True, tool="create_reminder", output={"id": row.id, "title": row.title, "scheduled_at": row.scheduled_at.isoformat(), "status": row.status})


def _cancel_reminder(ctx: ToolContext, args: CancelReminderArgs) -> ToolResult:
    row = ReminderRepository(ctx.db).get(ctx.user_id, args.reminder_id)
    if row is None:
        raise not_found("reminder")
    updated = ReminderService(ctx.db).cancel(ctx.user_id, args.reminder_id)
    return ToolResult(ok=True, tool="cancel_reminder", output={"id": updated.id, "status": updated.status})


def _retrieve_memory(ctx: ToolContext, args: RetrieveMemoryArgs) -> ToolResult:
    service = MemoryService(ctx.db)
    hits = service.search(user_id=ctx.user_id, query=args.query, types=args.types, limit=args.limit)
    return ToolResult(
        ok=True,
        tool="retrieve_memory",
        output={"memories": [{"id": h.memory.id, "type": h.memory.type, "content": h.memory.content, "score": h.score} for h in hits]},
    )


def _save_memory(ctx: ToolContext, args: SaveMemoryArgs) -> ToolResult:
    result = MemoryService(ctx.db).propose(
        user_id=ctx.user_id,
        content=args.content,
        type=args.type,
        importance=args.importance,
        confidence=args.confidence,
        source="user",
    )
    return ToolResult(ok=result.accepted, tool="save_memory", output={"accepted": result.accepted, "reason": result.reason, "memory_id": result.memory_id})


def _delete_memory(ctx: ToolContext, args: DeleteMemoryArgs) -> ToolResult:
    memory = MemoryRepository(ctx.db).get(ctx.user_id, args.memory_id)
    if memory is None:
        raise not_found("memory")
    if not args.confirm:
        return ToolResult(
            ok=False,
            tool="delete_memory",
            requires_confirmation=True,
            proposed_action={"memory_id": args.memory_id, "content": memory.content},
            error="Confirmation required before deleting this memory.",
        )
    deleted = MemoryService(ctx.db).delete(ctx.user_id, args.memory_id)
    return ToolResult(ok=deleted, tool="delete_memory", output={"deleted": deleted, "id": args.memory_id})


def _daily_plan(ctx: ToolContext, args: DailyPlanArgs) -> ToolResult:
    service = DailyPlannerService(ctx.db)
    plan = service.build(ctx.user_id, for_date=args.date, timezone_name=args.timezone)
    return ToolResult(ok=True, tool="daily_plan", output=plan)


def _project_progress(ctx: ToolContext, args: ProjectProgressArgs) -> ToolResult:
    # avoid apps import by inline goal calculation
    goals = GoalRepository(ctx.db).list_for_user(ctx.user_id, status="ACTIVE")
    projects = []
    for goal in goals:
        tasks = TaskRepository(ctx.db).list_for_user(ctx.user_id, goal_id=goal.id)
        done = len([t for t in tasks if t.status == "DONE"])
        projects.append(
            {
                "goal_id": goal.id,
                "title": goal.title,
                "status": goal.status,
                "task_total": len(tasks),
                "task_done": done,
                "completion_pct": round((done / len(tasks)) * 100.0, 1) if tasks else 0.0,
            }
        )
    return ToolResult(ok=True, tool="project_progress", output={"projects": projects})


def _android_capabilities(ctx: ToolContext, args: EmptyArgs) -> ToolResult:
    import importlib
    caps = importlib.import_module("integrations.termux.safe_api").capabilities

    return ToolResult(ok=True, tool="android_capabilities", output={"capabilities": caps()})


def _termux_notify(ctx: ToolContext, args: BaseModel) -> ToolResult:
    import importlib
    notify = importlib.import_module("integrations.termux.safe_api").notify

    # Args passed as dict through generic? Define ad hoc schema locally.
    result = native_notify(getattr(args, "title", ""), getattr(args, "body", ""), getattr(args, "notification_id", None))
    return ToolResult(ok=bool(result.get("ok")), tool="termux_notify", output=result)


def _termux_open_url(ctx: ToolContext, args: AndroidOpenUrlArgs) -> ToolResult:
    import importlib
    native_open = importlib.import_module("integrations.termux.safe_api").open_url

    if not args.confirm:
        return ToolResult(
            ok=False,
            tool="termux_open_url",
            requires_confirmation=True,
            proposed_action={"url": args.url},
            error="Confirmation required before opening this URL.",
        )
    result = native_open(args.url)
    return ToolResult(ok=bool(result.get("ok")), tool="termux_open_url", output=result)


def _save_memory_tool(ctx: ToolContext, args: SaveMemoryArgs) -> ToolResult:
    return _save_memory(ctx, args)


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec("list_tasks", "List tasks with optional filters.", ListTasksArgs, _list_tasks, 0, "low"))
    registry.register(ToolSpec("create_task", "Create a new task.", CreateTaskArgs, _create_task, 0, "low"))
    registry.register(ToolSpec("update_task", "Update a task; consequential changes require confirmation.", UpdateTaskArgs, _update_task, 1, "medium"))
    registry.register(ToolSpec("complete_task", "Mark a task completed.", CompleteTaskArgs, _complete_task, 0, "low"))
    registry.register(ToolSpec("delete_task", "Delete a task after confirmation.", DeleteTaskArgs, _delete_task, 2, "critical"))
    registry.register(ToolSpec("list_reminders", "List reminders.", ListRemindersArgs, _list_reminders, 0, "low"))
    registry.register(ToolSpec("create_reminder", "Create a reminder.", CreateReminderArgs, _create_reminder, 0, "low"))
    registry.register(ToolSpec("cancel_reminder", "Cancel a reminder.", CancelReminderArgs, _cancel_reminder, 0, "low"))
    registry.register(ToolSpec("retrieve_memory", "Retrieve relevant memories.", RetrieveMemoryArgs, _retrieve_memory, 0, "low"))
    registry.register(ToolSpec("save_memory", "Store a durable memory after value checks.", SaveMemoryArgs, _save_memory, 0, "low"))
    registry.register(ToolSpec("delete_memory", "Delete a memory after confirmation.", DeleteMemoryArgs, _delete_memory, 2, "critical"))
    registry.register(ToolSpec("daily_plan", "Generate the daily plan.", DailyPlanArgs, _daily_plan, 0, "low"))
    registry.register(ToolSpec("project_progress", "Calculate goal/project progress from tasks.", ProjectProgressArgs, _project_progress, 0, "low"))
    registry.register(ToolSpec("android_capabilities", "Report available Android/Termux integrations.", EmptyArgs, _android_capabilities, 0, "low"))
    registry.register(ToolSpec("android_open_url", "Open a URL through a validated Termux command after confirmation.", AndroidOpenUrlArgs, _termux_open_url, 1, "high"))

    # Compatibility aliases matching the architecture's dotted tool names.
    alias_map = {
        "memory.search": "retrieve_memory",
        "memory.store": "save_memory",
        "memory.delete": "delete_memory",
        "task.list": "list_tasks",
        "task.create": "create_task",
        "task.update": "update_task",
        "task.complete": "complete_task",
        "task.delete": "delete_task",
        "reminder.list": "list_reminders",
        "reminder.create": "create_reminder",
        "reminder.cancel": "cancel_reminder",
        "daily.plan": "daily_plan",
        "planner.daily": "daily_plan",
        "goal.progress": "project_progress",
        "project.progress": "project_progress",
        "android.capabilities": "android_capabilities",
        "android.open_url": "android_open_url",
    }
    for alias_name, canonical_name in alias_map.items():
        spec = registry.get(canonical_name)
        registry.register(
            ToolSpec(
                name=alias_name,
                description=spec.description,
                input_model=spec.input_model,
                handler=spec.handler,
                permission_level=spec.permission_level,
                risk_level=spec.risk_level,
            )
        )
    return registry


# For convenience/tests
default_registry = build_default_registry()
