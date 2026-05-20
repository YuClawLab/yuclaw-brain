"""
Telegram adapter — Bot API sendMessage.

v3.0 launch (Day 14): the v3.0 Signal Radar IS the legitimate owner of
@yuclaw_signals — the v2.3.0 daily broadcast was retired in the cron
cutover. The sprint-time safety rail that refused @yuclaw_signals is
now removed; the channel is what the radar broadcasts to.

Required env vars (loaded from ~/.yuclaw_env by notifier.load_env_file):
    TELEGRAM_BOT_TOKEN
    RADAR_TELEGRAM_CHANNEL      (default channel for radar broadcasts —
                                 e.g. @yuclaw_signals after Day 14 cutover)

If RADAR_TELEGRAM_CHANNEL is unset, the adapter reports NOT_CONFIGURED
and the orchestrator falls through to dry-run logging — no message is
ever sent without an explicitly named channel.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from v3.radar.notifier import Notifier, load_env_file


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
    return bool(_bot_token() and _channel())


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
