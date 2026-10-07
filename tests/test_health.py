from __future__ import annotations


def test_health_reports_all_components_online(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["components"]["api"]["status"] == "online"
    assert body["components"]["database"]["status"] == "online"
    assert body["phase"] == 1


def test_meta_reports_honest_integration_status(client):
    resp = client.get("/api/v1/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "JARVIS"
    assert body["auth_mode"] == "dev"
    for name, info in body["integrations"].items():
        assert info["status"] in {"not_configured", "pending_oauth", "connected", "error"}
        # No integration is connected in Phase 1 — nothing may pretend otherwise.
        assert info["status"] != "connected", f"{name} claims connected without an implementation"
