"""phase 2 brain: memories, goals, tasks, chat sessions/messages

Revision ID: 0002_phase2
Revises: 0001_initial
Create Date: 2026-10-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0002_phase2"
down_revision: str | None = "0001_initial"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "PROFILE", "GOAL", "PROJECT", "TASK", "PREFERENCE", "CONTACT",
                "OPPORTUNITY", "DECISION", "LESSON", "CONVERSATION", "FACT",
                name="memory_type", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_ref", sa.JSON(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("agent", "tool", "user", "import", name="memory_source", native_enum=False),
            nullable=False,
        ),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_memories"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_memories_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_user_type", "memories", ["user_id", "type"])

    op.create_table(
        "goals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column(
            "kind",
            sa.Enum("MISSION", "OBJECTIVE", "PROJECT", name="goal_kind", native_enum=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metric", sa.String(length=120), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "PAUSED", "DONE", "CANCELLED", name="goal_status", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("P0", "P1", "P2", "P3", name="goal_priority", native_enum=False),
            nullable=False,
        ),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_goals"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_goals_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["goals.id"], name="fk_goals_parent_id_goals", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    op.create_index("ix_goals_parent_id", "goals", ["parent_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority",
            sa.Enum("P0", "P1", "P2", "P3", name="task_priority", native_enum=False),
            nullable=False,
        ),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "TODO", "IN_PROGRESS", "BLOCKED", "WAITING_APPROVAL", "DONE", "CANCELLED",
                name="task_status", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("goal_id", sa.String(length=36), nullable=True),
        sa.Column("parent_task_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_tasks_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["goals.id"], name="fk_tasks_goal_id_goals", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"], ["tasks.id"], name="fk_tasks_parent_task_id_tasks", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_user_status", "tasks", ["user_id", "status"])
    op.create_index("ix_tasks_goal_id", "tasks", ["goal_id"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_chat_sessions_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", "system", name="chat_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("OK", "ERROR", "OFFLINE", name="chat_message_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"],
            name="fk_chat_messages_session_id_chat_sessions", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_chat_messages_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("tasks")
    op.drop_table("goals")
    op.drop_table("memories")
