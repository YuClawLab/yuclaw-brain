#!/usr/bin/env python3
"""
Client deliverable packager (BYOS lane) — one command, box-local output.

Builds output/byos_dryrun/client_deliverable.zip containing:
  - CLIENT_MEMO.pdf + CLIENT_MEMO.md
  - METHODOLOGY.md (client-facing note, full-rail language lint at build
    time — the build FAILS if a banned term slips in)
  - bundle/ (reproduction bundle: inputs, hashes, environment, rerun.sh)
  - SHA256SUMS (every file in the zip)
  - README_VERIFICATION.md (how to verify checksums + rerun)

The delivery CHANNEL stays a human/counsel decision — this tool only
packages. Everything stays inside the gitignored client directory.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from check_language import lint_text

OUT_DIR = _REPO / "output" / "byos_dryrun"
ZIP = OUT_DIR / "client_deliverable.zip"

# ---- Tier fulfillment profiles (Signal Review order, 2026-08-04) ----------
# Each tier lists the memo/deliverable SECTIONS it produces. The page's
# tier-scope promises (v3/web/render_signal_review.py TIER_*_ITEMS) map
# onto these; selftest_page_promises() diffs them — the page may never
# promise what the pipeline does not produce.
TIER_PROFILES = {
    "A": {   # Founding Pilot A — signal validation core (CAD 2,500)
        "sections": [
            "locked protocol (spec + hash)",
            "signal decomposition suite",
            "methodology note",
            "reproduction bundle",
            "research memo (suite results)",
        ],
        "artifacts": ["CLIENT_MEMO.pdf", "CLIENT_MEMO.md",
                      "METHODOLOGY.md", "bundle/", "SHA256SUMS",
                      "README_VERIFICATION.md"],
        "memo_excludes": ["estimands", "falsification"],
    },
    "B": {   # Founding Pilot B — full signal review (CAD 5,000)
        "sections": [
            "locked protocol (spec + hash)",
            "signal decomposition suite",
            "methodology note",
            "reproduction bundle",
            "research memo (suite results)",
            "basket event-study panel (cluster-robust)",
            "falsification battery",
            "coverage and exclusion anatomy",
            "written questions window + findings session",
        ],
        "artifacts": ["CLIENT_MEMO.pdf", "CLIENT_MEMO.md",
                      "METHODOLOGY.md", "bundle/", "SHA256SUMS",
                      "README_VERIFICATION.md"],
        "memo_excludes": [],
    },
}

# page-promise -> profile-section mapping used by the self-test
_PROMISE_MAP = {
    "Locked protocol registered before computation": "locked protocol (spec + hash)",
    "Signal decomposition suite": "signal decomposition suite",
    "Methodology note": "methodology note",
    "Reproduction bundle": "reproduction bundle",
    "Research memo covering the suite results": "research memo (suite results)",
    "Basket event-study panel": "basket event-study panel (cluster-robust)",
    "Falsification battery": "falsification battery",
    "Coverage and exclusion anatomy": "coverage and exclusion anatomy",
    "30 days of written questions": "written questions window + findings session",
}


def selftest_page_promises() -> list[str]:
    """Diff the Signal Review page's tier promises against TIER_PROFILES.
    Returns a list of problems (empty = green)."""
    from v3.web.render_signal_review import TIER_A_ITEMS, TIER_B_ITEMS
    problems = []
    for tier, items in (("A", TIER_A_ITEMS), ("B", TIER_B_ITEMS)):
        produced = set(TIER_PROFILES[tier]["sections"])
        for item in items:
            matched = next((v for k, v in _PROMISE_MAP.items()
                            if item.startswith(k)), None)
            if matched is None:
                problems.append(f"tier {tier}: page promise has no "
                                f"profile mapping: '{item[:60]}'")
            elif matched not in produced:
                problems.append(f"tier {tier}: page promises '{item[:50]}' "
                                f"but profile does not produce '{matched}'")
    # one-pager consistency (v2, 2026-08-05): the counsel one-pager must
    # name both tiers with the page's exact CAD figures.
    src = (_REPO / "tools" / "yuclaw_counsel_packet.py").read_text()
    for needle in ("Founding Pilot A", "CAD 2,500",
                   "Founding Pilot B", "CAD 5,000"):
        if needle not in src:
            problems.append(f"one-pager: missing '{needle}' — page and "
                            f"one-pager tier terms must match")
    return problems

METHODOLOGY = """# Methodology Note — Reading Your Results

*User-defined research lens — not part of the canonical public record.
Research classifications, not advice of any kind.*

## How your signal is measured

Each dated signal value is compared with what the named stock did AFTER the
signal date, relative to the broad U.S. market (the SPY fund): the stock's
return over the next k trading days minus SPY's return over the same days.
Entry is the close of the first trading day AFTER the signal date — we never
assume the signal could be acted on the same day it is dated.
Coverage basis: names in YUCLAW's canonical 79-name universe or its
expanded research universe (Phase-A manifest) with price history in the
research store are measurable; anything else is excluded and listed with
the reason, never silently scored.

**What the SPY comparison controls for:** the broad market moving as a
whole. A signal that merely tracks the whole market rising or falling scores
near zero.

**What it does not control for:** sector and style composition. If your
names are concentrated in one sector, sector-wide moves still flow through.
For the event-study panel we therefore also use a basket-peer comparison —
each name against the equal-weight average of the OTHER names you submitted
— which removes movement common to your basket.

## When a custom comparison becomes a scoped customization

Swapping SPY for a sector index, a factor series, or a comparison basket of
your choosing changes the question being asked, so it is handled as a scoped
customization: specified in writing, registered as its own protocol variant
in your client chain, and priced separately. It is never a silent switch.

## The 15-name floor

The rank-association statistic (IC) is computed per date across your names.
With fewer than 15 names on a date, that cross-section is too small for the
number to carry weight on its own; the suite marks such results UNDERPOWERED
and they should be read as descriptive, not as evidence for or against the
signal. Ten names — a common submission size — will always carry this badge:
that is honesty about sample size, not a defect in your signal.

## Badges, in one line each

- UNDERPOWERED — too little data for the interval to mean much; accrue more.
- DESCRIPTIVE — measured as stated; the interval includes zero.
- PRELIMINARY — the interval excludes zero, but the record is young.
"""

README = """# Verifying this deliverable

1. Checksums: `sha256sum -c SHA256SUMS` from inside the unzipped folder —
   every file must report OK.
2. Reproduction: `bash bundle/rerun.sh` on the analysis box re-computes the
   signal-suite numbers from the bundled inputs and compares them with the
   delivered results, printing REPRODUCTION OK on an exact match.
3. Chain: `bundle/registry_client.jsonl` is a hash-chained record of your
   lens's protocol and runs; any edit breaks the chain and is detectable
   with the registry verifier.

Questions are covered for 30 days from delivery per the engagement terms.
"""


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=("A", "B"), default="B",
                    help="fulfillment profile (default B, full review)")
    ap.add_argument("--selftest", action="store_true",
                    help="diff page promises vs tier profiles and exit")
    args = ap.parse_args()
    if args.selftest:
        probs = selftest_page_promises()
        if probs:
            print("PAGE-PROMISE SELF-TEST FAILED:")
            for x in probs:
                print(f"  · {x}")
            return 1
        print("[deliverable] self-test OK — every page promise maps to a "
              "produced section in its tier profile (A and B)")
        return 0
    profile = TIER_PROFILES[args.tier]
    print(f"[deliverable] tier {args.tier} profile: "
          f"{len(profile['sections'])} sections")
    problems = lint_text(METHODOLOGY, pages_mode=False)
    if problems:
        print("METHODOLOGY LINT FAILED — banned terms present:")
        for p in problems:
            print(f"  · line {p['line_no']}: {p['word']} — {p['line']}")
        return 1
    (OUT_DIR / "METHODOLOGY.md").write_text(METHODOLOGY)

    files = [OUT_DIR / "CLIENT_MEMO.pdf", OUT_DIR / "CLIENT_MEMO.md",
             OUT_DIR / "METHODOLOGY.md"]
    bundle_files = sorted((OUT_DIR / "bundle").rglob("*"))
    missing = [f for f in files if not f.exists()]
    if missing:
        print(f"missing deliverable inputs: {[str(m) for m in missing]} — "
              "run tools/yuclaw_byos_dryrun.py first")
        return 1

    sums = []
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)
            sums.append((hashlib.sha256(f.read_bytes()).hexdigest(), f.name))
        for f in bundle_files:
            if f.is_file():
                arc = f"bundle/{f.relative_to(OUT_DIR / 'bundle')}"
                z.write(f, arc)
                sums.append((hashlib.sha256(f.read_bytes()).hexdigest(), arc))
        sha_text = "".join(f"{h}  {n}\n" for h, n in sums)
        z.writestr("SHA256SUMS", sha_text)
        z.writestr("README_VERIFICATION.md", README)
    print(f"[deliverable] {ZIP} ({ZIP.stat().st_size/1024:.0f} KB, "
          f"{len(sums) + 2} files) · methodology linted clean · "
          f"built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
