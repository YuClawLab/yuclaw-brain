"""
Telegram adapter — Bot API sendMessage.

SAFETY RAIL: the target channel comes from `RADAR_TELEGRAM_CHANNEL`, NOT
the live `TELEGRAM_CHANNEL` used by the v2.3.0 daily broadcast. If that
env var is missing, the adapter reports "not configured" and the orches-
trator falls through to dry-run logging — never posts to the live
@yuclaw_signals channel by accident.

Required env vars (loaded from ~/.yuclaw_env by notifier.load_env_file):
    TELEGRAM_BOT_TOKEN          (shared with the daily broadcast bot)
    RADAR_TELEGRAM_CHANNEL      (TEST channel id or @handle)
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from v3.radar.notifier import Notifier, load_env_file

LIVE_CHANNEL_VALUE = "@yuclaw_signals"   # never post to this from radar


def _bot_token() -> Optional[str]:
    load_env_file()
    t = os.environ.get("TELEGRAM_BOT_TOKEN") or None
    return t.strip() if t else None


def _channel() -> Optional[str]:
    load_env_file()
    ch = os.environ.get("RADAR_TELEGRAM_CHANNEL") or None
    return ch.strip() if ch else None


def is_configured() -> bool:
    """Module-level convenience for the smoke-test script."""
    token = _bot_token()
    ch = _channel()
    if not token or not ch:
        return False
    if ch == LIVE_CHANNEL_VALUE:
        # Explicit refusal — radar must not target the live broadcast channel.
        return False
    return True


class TelegramNotifier(Notifier):
    channel_id = "telegram"

    def is_configured(self) -> bool:
        return is_configured()

    def send(self, body: str) -> str:
        if not self.is_configured():
            return "NOT_CONFIGURED"
        token = _bot_token() or ""
        ch = _channel() or ""
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            r = httpx.post(
                url,
                json={"chat_id": ch, "text": body, "disable_web_page_preview": True},
                timeout=20.0,
            )
            if r.status_code != 200:
                return f"ERROR: HTTP {r.status_code} {r.text[:120]}"
            payload = r.json()
            if not payload.get("ok"):
                return f"ERROR: telegram {payload.get('description', '?')[:120]}"
            return "SENT"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {str(e)[:120]}"
