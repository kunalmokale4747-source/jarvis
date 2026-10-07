from __future__ import annotations


def test_login_issues_token_and_me_returns_identity(client, login):
    token, user = login()
    assert token
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user["email"]
    assert body["mode"] == "dev"
    assert body["user"]["id"] == user["id"]


def test_missing_token_returns_failure_contract(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "UNAUTHORIZED"
    for key in ("message", "what_failed", "what_happened", "what_next"):
        assert body[key], f"missing {key}"


def test_invalid_token_rejected(client, login):
    token, _ = login()
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_logout_revokes_session(client, login):
    token, _ = login()
    out = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert out.status_code == 200
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_profile_round_trip(client, login):
    token, _ = login()
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/v1/me/profile", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["is_complete"] is False

    payload = {
        "name": "Kunal Mokale",
        "location": "India",
        "languages": ["English", "Marathi", "Hindi"],
        "skills": [{"name": "Python"}, {"name": "TypeScript"}],
        "career_goals": {"summary": "Land a remote engineering role"},
        "business_goals": {"summary": "Build a product studio"},
        "financial_goals": {"summary": "Earn 50000 INR/month"},
        "current_priorities": ["Fix portfolio", "Apply to 5 roles"],
    }
    updated = client.put("/api/v1/me/profile", json=payload, headers=headers)
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Kunal Mokale"
    assert body["is_complete"] is True
    assert body["skills"] == [{"name": "Python"}, {"name": "TypeScript"}]

    again = client.get("/api/v1/me/profile", headers=headers)
    assert again.json()["career_goals"]["summary"] == "Land a remote engineering role"


def test_profile_rejects_unknown_fields(client, login):
    token, _ = login()
    resp = client.put(
        "/api/v1/me/profile",
        json={"name": "X", "not_a_field": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_profile_is_isolated_between_users(client, login):
    token_a, _ = login("a@example.com", "User A")
    token_b, _ = login("b@example.com", "User B")

    resp_a = client.put(
        "/api/v1/me/profile",
        json={"name": "Secret A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a.status_code == 200

    resp_b = client.get(
        "/api/v1/me/profile", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["name"] is None, "user B must not see user A's profile"


def test_login_and_profile_writes_are_audited(client, login):
    token, user = login()
    client.put(
        "/api/v1/me/profile",
        json={"name": "Audited"},
        headers={"Authorization": f"Bearer {token}"},
    )

    from core.db.base import get_session_factory
    from core.db.models import AuditLog
    from sqlalchemy import select

    db = get_session_factory()()
    try:
        actions = [
            row.action
            for row in db.scalars(select(AuditLog).where(AuditLog.user_id == user["id"]))
        ]
    finally:
        db.close()
    assert "auth.login" in actions
    assert "profile.update" in actions
