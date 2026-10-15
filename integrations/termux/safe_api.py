"""Safe, allowlisted integration with Termux:API commands.

Rules enforced here:
- Only commands known to belong to Termux:API are allowed.
- Commands are executed with subprocess argument arrays, never a shell.
- All parameters are validated before execution.
- A missing command or nonzero exit code is reported honestly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from urllib.parse import urlparse

ALLOWED_COMMANDS = frozenset(
    {
        "termux-notification",
        "termux-open-url",
        "termux-tts-speak",
        "termux-battery-status",
        "termux-vibrate",
        "termux-toast",
        "termux-wake-lock",
        "termux-wake-unlock",
    }
)

LANGUAGES = frozenset({"en-US", "hi-IN", "en-IN", "en-GB"})
URL_SCHEMES = frozenset({"http", "https"})


def command_path(name: str) -> str | None:
    if name not in ALLOWED_COMMANDS:
        return None
    path = shutil.which(name)
    if path is None:
        return None
    return path


def is_available(name: str) -> bool:
    return command_path(name) is not None


def capabilities() -> dict[str, bool]:
    return {name: is_available(name) for name in sorted(ALLOWED_COMMANDS)}


def _run(name: str, args: list[str], timeout: int = 10) -> dict:
    path = command_path(name)
    if path is None:
        return {
            "ok": False,
            "available": False,
            "command": name,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": f"{name} is not installed or not available in PATH.",
        }
    for arg in args:
        if not isinstance(arg, str):
            return _invalid("all arguments must be strings", name)
    try:
        completed = subprocess.run(
            [path, *args],
            check=False,
            timeout=timeout,
            capture_output=True,
            text=True,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "available": True,
            "command": name,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": f"{name} timed out after {timeout} seconds.",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "available": False,
            "command": name,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": f"{name} could not be executed.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "available": True,
            "command": name,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": str(exc),
        }
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "ok": completed.returncode == 0,
        "available": True,
        "command": name,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "error": (stderr.strip() or f"{name} exited with code {completed.returncode}") if completed.returncode != 0 else None,
    }


def _invalid(message: str, command: str = "") -> dict:
    return {
        "ok": False,
        "available": False,
        "command": command,
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "error": message,
    }


def notify(title: str, body: str = "", notification_id: str | None = None, timeout: int = 10) -> dict:
    title = (title or "").strip()
    body = body or ""
    if not title or len(title) > 200:
        return _invalid("notification title must be 1..200 characters", "termux-notification")
    if len(body) > 4000:
        return _invalid("notification body is too long", "termux-notification")
    args = ["--title", title, "--content", body]
    if notification_id:
        args.extend(["--id", str(notification_id)])
    return _run("termux-notification", args, timeout)


def speak(text: str, language: str = "en-US", timeout: int = 30) -> dict:
    text = (text or "").strip()
    language = language or "en-US"
    if not text or len(text) > 8000:
        return _invalid("speech text must be 1..8000 characters", "termux-tts-speak")
    if language not in LANGUAGES:
        return _invalid("unsupported speech language", "termux-tts-speak")
    return _run("termux-tts-speak", ["-l", language, text], timeout)


def battery_status(timeout: int = 5) -> dict:
    result = _run("termux-battery-status", [], timeout)
    if result["ok"]:
        try:
            result["data"] = json.loads(result["stdout"])
        except json.JSONDecodeError:
            result["ok"] = False
            result["error"] = "termux-battery-status returned invalid JSON"
            result["data"] = None
    else:
        result["data"] = None
    return result


def open_url(url: str, timeout: int = 10) -> dict:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in URL_SCHEMES or not parsed.netloc:
        return _invalid("URL must be a valid http or https URL", "termux-open-url")
    if len(url) > 2048:
        return _invalid("URL is too long", "termux-open-url")
    if any(ch in url for ch in (";", "&", "|", "$", "`", "\n", "\r")):
        return _invalid("URL contains unsafe characters", "termux-open-url")
    return _run("termux-open-url", [url], timeout)


def toast(message: str, short: bool = True, timeout: int = 5) -> dict:
    message = (message or "").strip()
    if not message or len(message) > 280:
        return _invalid("toast message must be 1..280 characters", "termux-toast")
    args = ["-s" if short else "-l", message]
    return _run("termux-toast", args, timeout)


def vibrate(duration_ms: int = 200, timeout: int = 5) -> dict:
    duration_ms = max(1, min(int(duration_ms), 5000))
    return _run("termux-vibrate", ["-d", str(duration_ms)], timeout)


def wake_lock(timeout: int = 10) -> dict:
    return _run("termux-wake-lock", [], timeout)


def wake_unlock(timeout: int = 10) -> dict:
    return _run("termux-wake-unlock", [], timeout)


def device_capabilities() -> dict:
    return {
        "termux_api": capabilities(),
        "termux_tools_info": bool(shutil.which("termux-info")),
        "termux_open_url": bool(shutil.which("termux-open-url")),
        "termux_wake_lock": bool(shutil.which("termux-wake-lock")),
    }
