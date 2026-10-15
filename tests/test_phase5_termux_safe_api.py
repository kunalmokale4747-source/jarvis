from __future__ import annotations

import subprocess
from types import SimpleNamespace

from integrations.termux import safe_api


def test_missing_command_is_reported(monkeypatch):
    monkeypatch.setattr(safe_api, "command_path", lambda name: None)
    result = safe_api.notify("Hello", "World")
    assert result["ok"] is False
    assert result["available"] is False
    assert "not installed" in result["error"]


def test_command_allowlist_rejects_unknown_command(monkeypatch):
    assert safe_api.command_path("python") is None
    monkeypatch.setattr(safe_api.shutil, "which", lambda name: "/usr/bin/python")
    assert safe_api.command_path("python") is None


def test_native_notification_success(monkeypatch):
    monkeypatch.setattr(safe_api, "command_path", lambda name: "/fake/termux-notification")
    monkeypatch.setattr(
        safe_api.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    result = safe_api.notify("Jarvis", "Reminder")
    assert result["ok"] is True
    assert result["available"] is True
    assert result["command"] == "termux-notification"


def test_native_notification_failure_is_reported(monkeypatch):
    monkeypatch.setattr(safe_api, "command_path", lambda name: "/fake/termux-notification")
    monkeypatch.setattr(
        safe_api.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="permission denied"),
    )
    result = safe_api.notify("Jarvis", "Reminder")
    assert result["ok"] is False
    assert "permission denied" in (result["error"] or "")


def test_invalid_parameters_are_rejected():
    assert safe_api.notify("", "body")["ok"] is False
    assert safe_api.speak("x", "fr-FR")["ok"] is False
    assert safe_api.open_url("file:///etc/passwd")["ok"] is False
    assert safe_api.open_url("https://example.com;rm -rf /")["ok"] is False


def test_battery_status_parses_json(monkeypatch):
    monkeypatch.setattr(safe_api, "command_path", lambda name: "/fake/termux-battery-status")
    monkeypatch.setattr(
        safe_api.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='{"percentage": 80}', stderr=""),
    )
    result = safe_api.battery_status()
    assert result["ok"] is True
    assert result["data"]["percentage"] == 80


def test_command_timeout_is_reported(monkeypatch):
    monkeypatch.setattr(safe_api, "command_path", lambda name: "/fake/termux-notification")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(safe_api.subprocess, "run", raise_timeout)
    result = safe_api.notify("Jarvis", "Reminder")
    assert result["ok"] is False
    assert "timed out" in (result["error"] or "")
