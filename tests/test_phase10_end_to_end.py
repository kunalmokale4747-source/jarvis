from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone, timedelta


def test_natural_reminder_is_persisted_and_verified(client, login):
    token, _ = login()
    h = {"Authorization": f"Bearer {token}"}

    before = client.get("/api/v1/reminders", headers=h).json()
    before_count = len(before)

    response = client.post(
        "/api/v1/chat",
        json={"message": "Remind me to call home tomorrow at 7 PM"},
        headers=h,
    )
    assert response.status_code == 200
    body = response.json()
    assert "Reminder set" in body["assistant_message"]["content"]
    reply = body["assistant_message"]["content"]

    after = client.get("/api/v1/reminders", headers=h).json()
    assert len(after) == before_count + 1
    created = after[-1]
    assert created["title"] == "call home"
    assert created["scheduled_at"] < (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()


def test_ambiguous_reminder_does_not_create_record(client, login):
    token, _ = login()
    h = {"Authorization": f"Bearer {token}"}

    before = client.get("/api/v1/reminders", headers=h).json()
    response = client.post(
        "/api/v1/chat",
        json={"message": "Remind me to call home tomorrow"},
        headers=h,
    )
    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] != ""
    after = client.get("/api/v1/reminders", headers=h).json()
    assert len(after) == len(before)


def test_provider_status_and_explicit_unreachable_probe(client, login, monkeypatch):
    token, _ = login()
    h = {"Authorization": f"Bearer {token}"}

    diag = client.get("/api/v1/diagnostics", headers=h)
    assert diag.status_code == 200
    assert "ai" in diag.json()["components"]
    assert diag.json()["components"]["ai"]["status"] in {"not_configured", "error", "online"}

    monkeypatch.setattr("apps.api.routes.diagnostics.probe_provider", lambda settings=None, timeout_seconds=5.0: {"live_status": "configured_but_untested"})
    probed = client.get("/api/v1/diagnostics/provider?live=true", headers=h)
    assert probed.status_code == 200
    assert probed.json()["live_probe"]["live_status"] == "configured_but_untested"

    unprobed = client.get("/api/v1/diagnostics/provider", headers=h)
    assert unprobed.json()["live_probe"] == "not_requested"


def test_chat_continues_when_provider_unavailable(client, login, monkeypatch):
    token, _ = login()
    h = {"Authorization": f"Bearer {token}"}

    import core.chat.service as chat_service

    class FailingProvider:
        name = "failing"
        model = "failing-model"
        timeout = 1

        def complete(self, request):
            from core.llm.types import ProviderUnavailableError
            raise ProviderUnavailableError("simulated unavailable")

    monkeypatch.setattr(chat_service, "get_provider_chain", lambda settings=None: [FailingProvider()])
    response = client.post("/api/v1/chat", json={"message": "Tell me something useful."}, headers=h)
    assert response.status_code == 200
    assert response.json()["offline"] is True
    assert response.json()["assistant_message"]["content"]

    # natural consequence should still continue via deterministic reminder path
    reminder = client.post("/api/v1/chat", json={"message": "Remind me to call home tomorrow at 7 PM"}, headers=h)
    assert reminder.status_code == 200


def test_missing_termux_commands_reported_honestly(client, login):
    token, _ = login()
    h = {"Authorization": f"Bearer {token}"}

    capabilities = client.get("/api/v1/android/capabilities", headers=h)
    assert capabilities.status_code == 200
    caps = capabilities.json()["termux_api"]
    assert "termux-notification" in caps
    assert "termux-tts-speak" in caps
    assert caps["termux-notification"] is False
    assert caps["termux-tts-speak"] is False


def test_wake_lock_is_explicit_and_not_automatic(client, login):
    token, _ = login()
    h = {"Authorization": f"Bearer {token}"}

    # It may succeed/fail depending on device; it must be an explicit call.
    response = client.post("/api/v1/android/wake-lock", headers=h)
    assert response.status_code == 200
    assert "warning" in response.json()
    unlock = client.post("/api/v1/android/wake-unlock", headers=h)
    assert unlock.status_code == 200
