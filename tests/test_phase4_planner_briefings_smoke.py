from __future__ import annotations

from datetime import datetime, timezone, timedelta


def test_phase4_planner_and_briefings(client, login):
    token, user = login()
    h = {"Authorization": f"Bearer {token}"}

    # create task due today
    today = datetime.now(timezone.utc).date().isoformat()
    t = client.post("/api/v1/tasks", json={"title": "Plan me", "deadline": datetime.now(timezone.utc).isoformat()}, headers=h)
    assert t.status_code == 200

    plan = client.get("/api/v1/planner/today", headers=h)
    assert plan.status_code == 200
    body = plan.json()
    assert body["date"] == today
    assert "recommended" in body

    progress = client.get("/api/v1/projects/progress", headers=h)
    assert progress.status_code == 200

    settings = client.get("/api/v1/briefings/settings", headers=h)
    assert settings.status_code == 200
    assert settings.json()["morning_enabled"] is True

    run = client.post("/api/v1/briefings/run", json={"kind": "morning"}, headers=h)
    assert run.status_code == 200
    assert run.json()["kind"] == "morning"

    runs = client.get("/api/v1/briefings/runs", headers=h)
    assert runs.status_code == 200
    assert len(runs.json()) >= 1
