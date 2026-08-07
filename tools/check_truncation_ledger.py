#!/usr/bin/env python3
"""
Truncation-ledger gate (Truncation & Error Budget v1, order of 2026-08-06
P0-B — active immediately). Fails the chain when:

  (a) SCHEMA   — a ledger entry is missing a required field, or its
      interpretation_change flag is outside {yes, no, unknown};
  (b) DRIFT    — an anchored truncation-bearing file's sha256 differs
      from the ledger (truncation code changed without a same-commit
      ledger update);
  (c) DETECTOR — a truncation-shaped constant (CAP / LIMIT / MAX_* /
      _BUDGET assignment) or exclusion enum (EXCLU*= ) exists in v3/ or
      tools/ without a versioned-allowlist entry.

Detector posture (amendment A-3): narrow-and-trusted. The pattern set is
deliberately conservative so the gate never cries wolf; it widens only by
versioned allowlist review. Exit 0 = green; exit 1 = findings.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
LEDGER = _REPO / "registry" / "truncation_ledger.json"

REQUIRED = ("site_key", "reason", "count", "retained_mass",
            "interpretation_change", "rerun_threshold", "anchors")
FLAGS = {"yes", "no", "unknown"}
SCAN_DIRS = ("v3", "tools")
RE_CAP = re.compile(
    r"^([A-Z0-9_]*(?:CAP|LIMIT|MAX_[A-Z0-9_]+|_BUDGET)[A-Z0-9_]*)\s*=\s*\d",
    re.M)
RE_EXCL = re.compile(r"^(EXCLU[A-Z0-9_]*)\s*=", re.M)
SKIP_NAMES = {"__pycache__"}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    findings: list[str] = []
    if not LEDGER.exists():
        print("[truncation-gate] FAIL registry/truncation_ledger.json missing "
              "— the gate fails closed", file=sys.stderr)
        return 1
    led = json.loads(LEDGER.read_text())

    # (a) schema
    for e in led.get("entries", []):
        key = e.get("site_key", "<missing site_key>")
        for f in REQUIRED:
            if f not in e:
                findings.append(f"schema: {key} missing field '{f}'")
        if e.get("interpretation_change") not in FLAGS:
            findings.append(f"schema: {key} interpretation_change "
                            f"{e.get('interpretation_change')!r} not in "
                            f"{sorted(FLAGS)}")
        # (b) anchor drift
        for a in e.get("anchors", []):
            p = _REPO / a["path"]
            if not p.exists():
                findings.append(f"drift: {key} anchor {a['path']} missing")
            elif _sha(p) != a["sha256"]:
                findings.append(
                    f"drift: {key} anchor {a['path']} changed — update this "
                    f"ledger entry (and its numbers if the mechanism moved) "
                    f"in the same commit")

    # (c) detector: new cap constants / exclusion enums vs allowlist
    allow = {(c["file"], c["name"])
             for c in led.get("detector_allowlist", {}).get("constants", [])}
    for d in SCAN_DIRS:
        for p in sorted((_REPO / d).rglob("*.py")):
            if any(part in SKIP_NAMES for part in p.parts) or "test" in p.name:
                continue
            rel = str(p.relative_to(_REPO))
            text = p.read_text(errors="replace")
            for m in list(RE_CAP.finditer(text)) + list(RE_EXCL.finditer(text)):
                if (rel, m.group(1)) not in allow:
                    findings.append(
                        f"detector: {rel}: {m.group(1)} looks like a new "
                        f"truncation/filter/cap — add a ledger entry (or a "
                        f"reviewed allowlist line, version-bumped) in the "
                        f"same commit")

    if findings:
        print(f"[truncation-gate] {len(findings)} finding(s):")
        for f in findings:
            print(f"  FAIL {f}")
        return 1
    n = len(led.get("entries", []))
    na = len(led.get("detector_allowlist", {}).get("constants", []))
    print(f"[truncation-gate] OK — {n} ledger entries (schema + anchors "
          f"verified), detector clean over {'/'.join(SCAN_DIRS)} "
          f"(allowlist v{led.get('detector_allowlist', {}).get('version')}, "
          f"{na} constants)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
