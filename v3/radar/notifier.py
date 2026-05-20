"""
Notifier ABC + shared formatting helpers.

A Notifier represents one delivery channel (Telegram, Email, Slack...).
Subclasses report whether they are configured (`is_configured`), and
deliver one prebuilt message via `send`. The orchestrator (`run.py`)
handles fan-out, audit logging, and threshold/profile interaction.

All three adapters use the same plain-text format. Some channels could
benefit from Markdown / HTML in future, but at v3.0 we ship one
deterministic body so a reader cross-posting between channels sees
identical content.
"""
from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from v3.radar import COMPLIANCE_FOOTER
from v3.radar.detector import ChangeEvent

# Lightweight loader for ~/.yuclaw_env. We don't depend on python-dotenv
# because the adapter modules need to work in cron with whatever env
# the parent shell happens to provide. This populates os.environ in-place
# from KEY=VALUE lines, then is idempotent.
_ENV_PATH = Path(os.environ.get("YUCLAW_ENV_PATH",
                                str(Path.home() / ".yuclaw_env")))


def load_env_file() -> None:
    if not _ENV_PATH.exists():
        return
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Don't overwrite values explicitly set in the parent environment —
        # this matches `set -a; source` semantics where parent wins.
        os.environ.setdefault(key, value)


def format_body(changes: Iterable[ChangeEvent]) -> str:
    """Plain-text body used by every channel.

    Header → per-change block → locked compliance footer.
    """
    changes = list(changes)
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"YUCLAW Signal Radar — {when}",
        f"{len(changes)} material change(s):",
        "",
    ]
    for c in changes:
        lines.append(
            f"  {c.ticker}: {c.old_label} → {c.new_label}   "
            f"score {c.old_score:+.2f} → {c.new_score:+.2f}  "
            f"(Δ {c.delta_score:+.2f})"
        )
        if c.top_evidence:
            lines.append(f"     evidence: {c.top_evidence}")
    lines.append("")
    lines.append(COMPLIANCE_FOOTER)
    return "\n".join(lines)


def content_hash(body: str) -> str:
    """SHA-256/16 of the body — for idempotency + audit log."""
    return hashlib.sha256(body.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
class Notifier(ABC):
    """One delivery channel."""

    channel_id: str = ""   # "telegram" | "email" | "slack"

    @abstractmethod
    def is_configured(self) -> bool:
        """True iff all required env vars / settings are present."""

    @abstractmethod
    def send(self, body: str) -> str:
        """Deliver `body`. Returns a status string:
            "SENT"             — successful delivery
            "NOT_CONFIGURED"   — adapter intentionally inert
            "DRY_RUN"          — dry-run mode, no API call
            "ERROR: <detail>"  — delivery failed
        Must never raise.
        """
