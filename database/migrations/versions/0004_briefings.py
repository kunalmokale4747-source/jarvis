"""phase 4: briefing settings and runs"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0004_briefings"
down_revision: str | None = "0003_reminders"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    op.create_table(
        "briefing_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("morning_enabled", sa.Boolean(), nullable=False),
        sa.Column("morning_time", sa.String(length=8), nullable=False),
        sa.Column("evening_enabled", sa.Boolean(), nullable=False),
        sa.Column("evening_time", sa.String(length=8), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("morning_last_run_on", sa.String(length=10), nullable=True),
        sa.Column("evening_last_run_on", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_briefing_settings"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_briefing_settings_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_briefing_settings_user_id"),
    )
    op.create_index("ix_briefing_settings_user_id", "briefing_settings", ["user_id"])

    op.create_table(
        "briefing_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.Enum("morning", "evening", name="briefing_kind", native_enum=False), nullable=False),
        sa.Column("run_for_date", sa.String(length=10), nullable=False),
        sa.Column("scheduled_time", sa.String(length=8), nullable=False),
        sa.Column("status", sa.Enum("RUNNING", "COMPLETED", "FAILED", "SKIPPED", name="briefing_run_status", native_enum=False), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_briefing_runs"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_briefing_runs_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_briefing_runs_user_id", "briefing_runs", ["user_id"])
    op.create_index("ix_briefing_runs_user_kind_date", "briefing_runs", ["user_id", "kind", "run_for_date"])


def downgrade() -> None:
    op.drop_table("briefing_runs")
    op.drop_table("briefing_settings")
