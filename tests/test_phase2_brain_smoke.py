from __future__ import annotations

import pytest


def test_phase2_goal_task_memory_chat_offline(client, login):
    from fastapi.testclient import TestClient  # noqa: F401
    token, user = login()
    h = {"Authorization": f"Bearer {token}"}

    g = client.post("/api/v1/goals", json={"title": "Learn Python"}, headers=h)
    assert g.status_code == 200
    gid = g.json()["id"]

    t = client.post("/api/v1/tasks", json={"title": "Study Python", "goal_id": gid}, headers=h)
    assert t.status_code == 200
    tid = t.json()["id"]

    assert client.get("/api/v1/tasks", headers=h).json()[0]["id"] == tid

    mem = client.post("/api/v1/memory", json={"content": "prefers concise Hinglish replies"}, headers=h)
    assert mem.status_code == 200
    assert mem.json()["accepted"] is True

    hits = client.get("/api/v1/memory/search?q=concise", headers=h).json()
    assert hits and "concise" in hits[0]["memory"]["content"]

    chat = client.post("/api/v1/chat", json={"message": "hey"}, headers=h)
    assert chat.status_code == 200
    assert chat.json()["offline"] is True
