from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_TABLES = {"users", "user_profiles", "sessions", "audit_logs", "approvals"}


def _run_alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "AUTH_MODE": "dev",
        "ENV": "test",
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "database/alembic.ini", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _tables(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def _columns(db_path: Path, table: str) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def test_upgrade_then_downgrade_roundtrip(tmp_path):
    db = tmp_path / "migration.db"

    up = _run_alembic(["upgrade", "head"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    created = _tables(db)
    assert DOMAIN_TABLES <= created, f"missing tables: {DOMAIN_TABLES - created}"

    # Migration must match the ORM models exactly (no drift at Phase 1).
    from core.db.base import Base
    import core.db.models  # noqa: F401

    assert DOMAIN_TABLES == set(Base.metadata.tables)

    for table in DOMAIN_TABLES:
        model_cols = {c.name for c in Base.metadata.tables[table].columns}
        migrated_cols = _columns(db, table)
        assert migrated_cols == model_cols, (
            f"{table}: migration {sorted(migrated_cols)} != models {sorted(model_cols)}"
        )

    down = _run_alembic(["downgrade", "base"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    remaining = _tables(db) - {"alembic_version"}
    assert remaining == set(), f"tables survived downgrade: {remaining}"
