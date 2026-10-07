"""initial schema: users, user_profiles, sessions, audit_logs, approvals

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("role", sa.Enum("user", "admin", name="user_role", native_enum=False), nullable=False),
        sa.Column(
            "auth_provider",
            sa.Enum("dev", "supabase", name="user_auth_provider", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("experience", sa.JSON(), nullable=True),
        sa.Column("projects", sa.JSON(), nullable=True),
        sa.Column("career_goals", sa.JSON(), nullable=True),
        sa.Column("business_goals", sa.JSON(), nullable=True),
        sa.Column("financial_goals", sa.JSON(), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("availability", sa.JSON(), nullable=True),
        sa.Column("resume", sa.JSON(), nullable=True),
        sa.Column("portfolio", sa.JSON(), nullable=True),
        sa.Column("social_profiles", sa.JSON(), nullable=True),
        sa.Column("professional_profiles", sa.JSON(), nullable=True),
        sa.Column("current_priorities", sa.JSON(), nullable=True),
        sa.Column("is_complete", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_profiles"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_profiles_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_sessions_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent", sa.String(length=60), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("tool", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("input_summary", sa.JSON(), nullable=True),
        sa.Column("output_summary", sa.JSON(), nullable=True),
        sa.Column("permission_level", sa.Integer(), nullable=False),
        sa.Column("approval_id", sa.String(length=36), nullable=True),
        sa.Column(
            "result",
            sa.Enum("OK", "FAILED", "BLOCKED", "DENIED", "EXPIRED", name="audit_result", native_enum=False),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_audit_logs_user_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_ts", "audit_logs", ["ts"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tool", sa.String(length=120), nullable=False),
        sa.Column("agent", sa.String(length=60), nullable=True),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "risk_level",
            sa.Enum("low", "medium", "high", "critical", name="approval_risk", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "DENIED", "EXPIRED", name="approval_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_approvals"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_approvals_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_approvals_user_id", "approvals", ["user_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("audit_logs")
    op.drop_table("sessions")
    op.drop_table("user_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
