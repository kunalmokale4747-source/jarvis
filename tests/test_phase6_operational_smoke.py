from __future__ import annotations

from datetime import datetime, timezone, timedelta


def test_phase6_diagnostics_and_idempotency(client, login):
    token, user = login()
    h = {"Authorization": f"Bearer {token}"}
    diag = client.get("/api/v1/diagnostics", headers=h)
    assert diag.status_code == 200
    body = diag.json()
    assert body["components"]["database"]["status"] == "online"
    assert "scheduler" in body["components"]
    assert "android" in body["components"]
    assert "counts" in body

    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    created = client.post(
        "/api/v1/reminders", json={"title": "Idempotent", "scheduled_at": due, "timezone": "UTC"}, headers=h
    )
    assert created.status_code == 200
    first = client.post("/api/v1/reminders/process-due", headers=h).json()["fired"]
    second = client.post("/api/v1/reminders/process-due", headers=h).json()["fired"]
    assert first >= 1
    assert second == 0


def test_phase6_recurring_reminder_advances(client, login):
    token, user = login()
    h = {"Authorization": f"Bearer {token}"}
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    created = client.post(
        "/api/v1/reminders",
        json={"title": "Daily", "scheduled_at": due, "timezone": "UTC", "recurrence": "daily", "recurrence_interval": 1},
        headers=h,
    )
    assert created.status_code == 200
    assert created.json()["recurrence"] == "daily"
    fired = client.post("/api/v1/reminders/process-due", headers=h).json()["fired"]
    assert fired >= 1
    remaining = client.get("/api/v1/reminders", headers=h).json()
    daily = [r for r in remaining if r["title"] == "Daily"][0]
    assert daily["status"] == "SCHEDULED"
    assert daily["scheduled_at"] > due


def test_phase6_health_reports_scheduler(client, login):
    token, user = login()
    h = {"Authorization": f"Bearer {token}"}
    health = client.get("/health", headers=h)
    assert health.status_code == 200
    body = health.json()
    assert "scheduler" in body["components"]
    assert body["phase"] == 9
