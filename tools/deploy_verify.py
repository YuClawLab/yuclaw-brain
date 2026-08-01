#!/usr/bin/env python3
"""
Deploy-verify — push ≠ live (usefulness build, 2026-07-16).

After the daily chain pushes docs/ to GitHub Pages, this script fetches every
public page from the LIVE site and compares content sha-256 against the local
build, polling until they match or the deadline passes. Exit 0 = every listed
artifact is live and byte-identical; exit 1 = at least one is stale/missing.

Stdlib only. CLI:
    python3 tools/deploy_verify.py                 # poll up to 15 min
    python3 tools/deploy_verify.py --timeout 60    # one-shot-ish check
    python3 tools/deploy_verify.py --paths index.html lane.html
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
BASE = "https://yuclawlab.github.io/yuclaw-brain"

# Every public artifact the daily chain publishes (repo-relative under docs/).
DEFAULT_PATHS = [
    "index.html",
    "validation.html",
    "validation_lab.html",
    "etf_evidence.html",
    "xlk_evidence.html",
    "llms.txt",
    "evidence_index.json",
    "weekly_note.html",
    "canada_resources.html",
    "replication.html",
    "todays_evidence.html",
    "lane.html",
    "trace_su.html",
    "usage.md",
    "examples/evidence_memo_su.md",
    # copy artifacts edited outside the daily renders (2026-07-23 rail
    # extension) — previously checked by hand after copy orders
    "YUCLAW_User_Guide.pdf",
    "YUCLAW_User_Guide_source.html",
    "methodology/backfill.md",
    "replay/lab_replay_bundle.json",
    "packets/manifest.json",
    "packets/yuclaw_validation_lab_packet.zip",
    "packets/yuclaw_open_index_evidence_packet.zip",
    "packets/yuclaw_canada_resources_packet.zip",
]

POLL_SECONDS = 30


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "yuclaw-deploy-verify",
            "Cache-Control": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify the live site matches the local build")
    p.add_argument("--timeout", type=int, default=900, help="seconds (default 900)")
    p.add_argument("--paths", nargs="*", default=None, help="subset of paths")
    args = p.parse_args(argv)

    paths = args.paths or DEFAULT_PATHS
    local: dict[str, str] = {}
    missing_local = []
    for rel in paths:
        f = _REPO / "docs" / rel
        if not f.exists():
            missing_local.append(rel)
        else:
            local[rel] = _sha(f.read_bytes())
    if missing_local:
        print(f"[deploy-verify] local build missing: {missing_local}", file=sys.stderr)
        return 1

    pending = dict(local)
    deadline = time.time() + args.timeout
    while pending:
        for rel in sorted(pending):
            data = _fetch(f"{BASE}/{rel}")
            if data is not None and _sha(data) == pending[rel]:
                print(f"[deploy-verify] LIVE  {rel}")
                del pending[rel]
        if not pending:
            break
        if time.time() >= deadline:
            for rel in sorted(pending):
                print(f"[deploy-verify] STALE {rel} — live content does not match local build",
                      file=sys.stderr)
            print(f"[deploy-verify] FAIL: {len(pending)}/{len(paths)} artifacts not live "
                  f"after {args.timeout}s", file=sys.stderr)
            return 1
        time.sleep(POLL_SECONDS)

    print(f"[deploy-verify] OK: all {len(paths)} artifacts live and byte-identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
