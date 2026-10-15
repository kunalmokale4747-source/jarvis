from __future__ import annotations

from datetime import datetime, timezone, timedelta


def test_phase3_reminder_create_and_due_processing(client, login):
    token, user = login()
    h = {"Authorization": f"Bearer {token}"}
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    r = client.post("/api/v1/reminders", json={"title": "Ring", "scheduled_at": due, "timezone": "UTC"}, headers=h)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    fired = client.post("/api/v1/reminders/process-due", headers=h)
    assert fired.status_code == 200
    assert fired.json()["fired"] >= 1
    rr = client.get(f"/api/v1/reminders/{rid}", headers=h).json()
    assert rr["status"] == "FIRED"
    notifs = client.get("/api/v1/notifications", headers=h).json()
    assert len(notifs) >= 1
