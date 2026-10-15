from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace


def test_reminder_native_delivery_failure_is_recorded(client, login, monkeypatch):
    token, user = login()
    h = {"Authorization": f"Bearer {token}"}
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    created = client.post("/api/v1/reminders", json={"title": "Ring", "scheduled_at": due, "timezone": "UTC"}, headers=h)
    assert created.status_code == 200

    import core.reminders.service as reminder_service

    monkeypatch.setattr(
        reminder_service.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="native failed"),
    )

    from core.db.base import get_session_factory
    from core.reminders.service import ReminderService

    db = get_session_factory()()
    try:
        fired = ReminderService(db, terminal_notifier_path="/fake/termux-notification").process_due()
    finally:
        db.close()

    assert fired >= 1
    notifications = client.get("/api/v1/notifications", headers=h).json()
    assert any(n.get("status") == "FAILED" for n in notifications)
