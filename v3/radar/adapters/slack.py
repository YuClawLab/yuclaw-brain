"""
Slack adapter — Incoming Webhook.

Required env var (loaded from ~/.yuclaw_env):
    SLACK_WEBHOOK_URL

Slack's incoming webhook spec is just an HTTP POST of {"text": "..."} to
the provided URL — no auth header, no extra payload required. Slack
treats the body as the message; we send the same plain-text body that
goes to Telegram/Email so cross-posted readers see identical content.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from v3.radar.notifier import Notifier, load_env_file


def _webhook() -> Optional[str]:
    load_env_file()
    w = os.environ.get("SLACK_WEBHOOK_URL") or None
    return w.strip() if w else None


def is_configured() -> bool:
    return _webhook() is not None


class SlackNotifier(Notifier):
    channel_id = "slack"

    def is_configured(self) -> bool:
        return is_configured()

    def send(self, body: str) -> str:
        url = _webhook()
        if not url:
            return "NOT_CONFIGURED"
        try:
            r = httpx.post(url, json={"text": body}, timeout=20.0)
            if r.status_code != 200:
                return f"ERROR: HTTP {r.status_code} {r.text[:120]}"
            return "SENT"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {str(e)[:120]}"
