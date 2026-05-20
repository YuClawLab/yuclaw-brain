"""
Email adapter — SMTP.

Required env vars (loaded from ~/.yuclaw_env by notifier.load_env_file):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO

If any are missing the adapter is "not configured" and is a no-op. Never
raises on missing creds — a partial config is a routine state during
launch ramp-up, not an error.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from v3.radar.notifier import Notifier, load_env_file

_REQUIRED = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM", "SMTP_TO")


def _read() -> Optional[dict[str, str]]:
    load_env_file()
    cfg: dict[str, str] = {}
    for k in _REQUIRED:
        v = os.environ.get(k)
        if not v:
            return None
        cfg[k] = v
    return cfg


def is_configured() -> bool:
    return _read() is not None


class EmailNotifier(Notifier):
    channel_id = "email"

    def is_configured(self) -> bool:
        return is_configured()

    def send(self, body: str) -> str:
        cfg = _read()
        if cfg is None:
            return "NOT_CONFIGURED"
        try:
            msg = MIMEText(body, _charset="utf-8")
            msg["Subject"] = "YUCLAW Signal Radar"
            msg["From"] = cfg["SMTP_FROM"]
            msg["To"] = cfg["SMTP_TO"]
            with smtplib.SMTP(cfg["SMTP_HOST"], int(cfg["SMTP_PORT"]), timeout=20) as s:
                s.starttls()
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASS"])
                s.sendmail(cfg["SMTP_FROM"], [cfg["SMTP_TO"]], msg.as_string())
            return "SENT"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {str(e)[:120]}"
