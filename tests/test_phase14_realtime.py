from __future__ import annotations

import os
import tempfile

import pytest


def _setup(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings()
    reset_engine()
    Base.metadata.create_all(get_engine())
    return reset_settings, reset_engine


def test_realtime_disabled_and_unauthorized():
    reset_settings, reset_engine = _setup(pytest.MonkeyPatch())
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "dev")
    from apps.api.main import create_app
    from fastapi.testclient import TestClient
    client = TestClient(create_app())
    # unauthorized
    r = client.post("/api/v1/voice/realtime/session")
    assert r.status_code == 401
    # disabled
    login = client.post("/api/v1/auth/login", json={"email": "a@b.com"}).json()["token"]
    r2 = client.post("/api/v1/voice/realtime/session", headers={"Authorization": f"Bearer {login}"})
    assert r2.status_code == 503
    assert r2.json()["detail"] == "Real-time voice is not configured."
    reset_settings()
    reset_engine()


def test_realtime_session_mocked_success_and_redacts_secret(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
    from core.config import reset_settings, get_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings()
    reset_engine()
    Base.metadata.create_all(get_engine())

    import apps.api.routes.voice as voice_route
    monkeypatch.setattr("core.config.settings_is_enabled", lambda: True, raising=False)
    monkeypatch.setenv("OPENAI_REALTIME_ENABLED", "true")
    monkeypatch.setenv("OPENAI_REALTIME_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_REALTIME_MODEL", "gpt-realtime")
    monkeypatch.setenv("OPENAI_REALTIME_VOICE", "alloy")
    monkeypatch.setenv("OPENAI_REALTIME_EXPIRES_IN_SECONDS", "60")
    reset_settings()
    monkeypatch.setattr(voice_route, "_openai_client_secret", lambda settings, user_email: {"value": "ek-test", "expires_at": 999999})

    from apps.api.main import create_app
    from fastapi.testclient import TestClient
    client = TestClient(create_app())
    token = client.post("/api/v1/auth/login", json={"email": "a@b.com"}).json()["token"]
    r = client.post("/api/v1/voice/realtime/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["ephemeral_key"] == "ek-test"
    assert body["provider"] == "openai-realtime"
    assert "secret" not in str(body)
    assert "OPENAI_REALTIME_API_KEY" not in str(body)

    # status
    sr = client.get("/api/v1/voice/realtime/status", headers={"Authorization": f"Bearer {token}"})
    assert sr.status_code == 200
    assert sr.json()["enabled"] is True
    assert "secret" not in str(sr.json())

    reset_settings()
    reset_engine()


def test_realtime_session_error_handling_without_secret_leak(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
    import urllib.error
    from core.config import reset_settings, get_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings()
    reset_engine()
    Base.metadata.create_all(get_engine())

    import apps.api.routes.voice as voice_route

    monkeypatch.setenv("OPENAI_REALTIME_ENABLED", "true")
    monkeypatch.setattr("apps.api.routes.voice.get_settings", lambda: type("S", (), {"openai_realtime_enabled": True, "openai_realtime_api_key": "secret-value", "openai_realtime_model": "gpt-realtime", "openai_realtime_voice": "alloy", "openai_realtime_expires_in_seconds": 60, "openai_realtime_base_url": "https://api.openai.com/v1"})())
    monkeypatch.setattr(voice_route, "_openai_client_secret", lambda settings, user_email: (_ for _ in ()).throw(urllib.error.HTTPError("https://example.com", 401, "x", {}, None)))

    from apps.api.main import create_app
    from fastapi.testclient import TestClient
    client = TestClient(create_app())
    token = client.post("/api/v1/auth/login", json={"email": "a@b.com"}).json()["token"]
    r = client.post("/api/v1/voice/realtime/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert "authentication" in detail.lower()
    assert "secret-value" not in detail
    reset_settings()
    reset_engine()
