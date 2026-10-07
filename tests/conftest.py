from __future__ import annotations

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh app + fresh SQLite database per test."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")

    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401  (registers tables on Base.metadata)

    reset_settings()
    reset_engine()
    Base.metadata.create_all(get_engine())

    from fastapi.testclient import TestClient

    from apps.api.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    reset_engine()
    reset_settings()


@pytest.fixture()
def login(client):
    """Helper: POST /api/v1/auth/login and return (token, user_dict)."""

    def _login(email: str = "kunalmokale4747@gmail.com", name: str | None = "Kunal"):
        resp = client.post(
            "/api/v1/auth/login", json={"email": email, "display_name": name}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        return data["token"], data["user"]

    return _login
