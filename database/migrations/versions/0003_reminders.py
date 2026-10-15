"""phase 3: reminders + notification history"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0003_reminders"
down_revision: str | None = "0002_phase2"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "SCHEDULED", "FIRED", "CANCELLED", "FAILED", name="reminder_status", native_enum=False), nullable=False),
        sa.Column("recurrence", sa.Enum("none", "daily", "weekly", "monthly", "yearly", name="reminder_recurrence", native_enum=False), nullable=False),
        sa.Column("recurrence_interval", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("channel", sa.Enum("web", "termux", "email", name="reminder_channel", native_enum=False), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_reminders"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_reminders_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name="fk_reminders_task_id_tasks", ondelete="SET NULL"),
        sa.UniqueConstraint("idempotency_key", name="uq_reminders_idempotency_key"),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_user_scheduled", "reminders", ["user_id", "status", "scheduled_at"])
    op.create_index("ix_reminders_scheduled_at", "reminders", ["scheduled_at"])
    op.create_index("ix_reminders_task_id", "reminders", ["task_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("reminder_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("status", sa.Enum("QUEUED", "SENT", "FAILED", "READ", name="notification_status", native_enum=False), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reminder_id"], ["reminders.id"], name="fk_notifications_reminder_id_reminders", ondelete="SET NULL"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_reminder_id", "notifications", ["reminder_id"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "read_at", "created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("reminders")
