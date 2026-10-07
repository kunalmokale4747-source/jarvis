"""Integration status registry.

Phase 1 reality: no external service is connected. The status function reads
the same environment variables the real integrations will use, so once
credentials appear the status changes honestly — and a module that reports
"connected" must actually be able to serve the integration.
"""

from __future__ import annotations

import os
from typing import Literal

IntegrationStatus = Literal["connected", "pending_oauth", "not_configured", "error"]

_REQUIRED_ENV: dict[str, list[str]] = {
    "gmail": ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"],
    "calendar": ["GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET"],
    "linkedin": ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"],
    "instagram": ["INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET"],
    "github": ["GITHUB_TOKEN"],
    "browser": [],  # no credentials needed, but the agent is not implemented yet
    "n8n": ["N8N_URL"],
}

# Providers that need an implementation module before "connected" is possible.
_IMPLEMENTED = set()

INTEGRATION_PHASE = {
    "gmail": 5,
    "calendar": 5,
    "linkedin": 7,
    "instagram": 7,
    "github": 8,
    "browser": 10,
    "n8n": 8,
}


def status() -> dict[str, dict[str, str | int]]:
    result: dict[str, dict[str, str | int]] = {}
    for name, env_vars in _REQUIRED_ENV.items():
        if name not in _IMPLEMENTED:
            state: IntegrationStatus = "not_configured"
        elif env_vars and all(os.environ.get(v) for v in env_vars):
            state = "connected"
        elif any(os.environ.get(v) for v in env_vars):
            state = "pending_oauth"
        else:
            state = "not_configured"
        result[name] = {"status": state, "phase": INTEGRATION_PHASE[name]}
    return result
