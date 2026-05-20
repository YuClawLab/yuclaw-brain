"""
Signal Radar orchestrator.

  python3 -m v3.radar.run            # detect + send via every enabled channel
  python3 -m v3.radar.run --dry-run  # detect + format; never call any external API

Behavior:
  1. detect_changes() compares the two most-recent OOS snapshots per ticker.
  2. If zero changes, log a single "no_changes" line and exit (no spam).
  3. Otherwise, for each enabled channel in profile.channels:
       - look up the adapter
       - if not configured → audit-log "NOT_CONFIGURED" and continue
       - else send the formatted body and audit-log the status
  4. Audit log path: ~/.yuclaw/radar_broadcasts.jsonl
       lines are JSON: {timestamp, channel, status, n_changes, content_hash}
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from v3.profile.store import load_profile
from v3.radar.adapters.email import EmailNotifier
from v3.radar.adapters.slack import SlackNotifier
from v3.radar.adapters.telegram import TelegramNotifier
from v3.radar.detector import detect_changes
from v3.radar.notifier import Notifier, content_hash, format_body

AUDIT_LOG = Path.home() / ".yuclaw" / "radar_broadcasts.jsonl"


def _adapters() -> dict[str, Notifier]:
    return {
        "telegram": TelegramNotifier(),
        "email":    EmailNotifier(),
        "slack":    SlackNotifier(),
    }


def _audit(line: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line["timestamp"] = datetime.now(timezone.utc).isoformat()
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(line) + "\n")


def run(dry_run: bool = False) -> int:
    prof = load_profile()
    changes = detect_changes()
    n = len(changes)

    if n == 0:
        _audit({"channel": "_orchestrator", "status": "NO_CHANGES",
                "n_changes": 0, "content_hash": None})
        print(f"[radar] no material changes detected — no broadcast sent")
        return 0

    body = format_body(changes)
    h = content_hash(body)
    print(f"[radar] {n} change(s) detected, body hash={h}")
    print("-" * 60)
    print(body)
    print("-" * 60)

    enabled_channels = [k for k, v in (prof.get("channels") or {}).items() if v]
    if not enabled_channels:
        print("[radar] no channels enabled in profile — nothing to send")
        _audit({"channel": "_orchestrator", "status": "NO_CHANNELS_ENABLED",
                "n_changes": n, "content_hash": h})
        return 0

    adapters = _adapters()
    for ch in enabled_channels:
        notifier = adapters.get(ch)
        if notifier is None:
            status = "UNKNOWN_CHANNEL"
        elif dry_run:
            status = "DRY_RUN" if notifier.is_configured() else "NOT_CONFIGURED"
        else:
            status = notifier.send(body)
        print(f"[radar] channel={ch:<10s} status={status}")
        _audit({"channel": ch, "status": status,
                "n_changes": n, "content_hash": h})
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="YUCLAW Signal Radar — change detector + multi-channel notifier")
    p.add_argument("--dry-run", action="store_true",
                   help="detect + format; never call any external API")
    args = p.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
