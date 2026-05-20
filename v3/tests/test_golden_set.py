"""
Golden-set regression test for the v3.0 extraction pipeline.

Loads v3/tests/golden_set.json, runs each entry through the LIVE extraction
pipeline (prompt + Ollama + SourceLock Guard), and compares against the
expected labels. Prints per-entry pass/fail and a summary, plus FN/FP lists.

Usage:
    python3 -m v3.tests.test_golden_set            # run all entries
    python3 -m v3.tests.test_golden_set --limit 4  # first N
    python3 -m v3.tests.test_golden_set --quick    # skip Ollama, validate harness only

NOTE: Each entry takes ~60-120s on Llama 70B. Full 20-entry runs are ~30 min.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from v3.extract.event_worker import _ollama_extract
from v3.extract.sourcelock import validate

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_set.json"


def _check_match(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (overall_pass, list_of_field_failures)."""
    fails: list[str] = []

    # no_event sentinel comparison
    expect_no = expected.get("no_event") is True
    actual_no = actual.get("no_event") is True
    if expect_no != actual_no:
        return False, [f"no_event mismatch: expected={expect_no} actual={actual_no}"]

    # If both no_event, we're done.
    if expect_no:
        return True, []

    # Otherwise, check event fields.
    if expected["event_type"] != actual.get("event_type"):
        fails.append(f"event_type: expected={expected['event_type']} actual={actual.get('event_type')}")

    if expected["direction"] != actual.get("direction"):
        fails.append(f"direction: expected={expected['direction']} actual={actual.get('direction')}")

    mag_lo, mag_hi = expected["magnitude_range"]
    if not (mag_lo <= actual.get("magnitude", -1) <= mag_hi):
        fails.append(f"magnitude: expected [{mag_lo},{mag_hi}] actual={actual.get('magnitude')}")

    if actual.get("confidence", 0) < expected["confidence_floor"]:
        fails.append(f"confidence: floor={expected['confidence_floor']} actual={actual.get('confidence')}")

    return (len(fails) == 0), fails


def run(limit: int | None = None, quick: bool = False) -> int:
    if not GOLDEN_PATH.exists():
        print(f"ERROR: {GOLDEN_PATH} missing")
        return 2

    data = json.loads(GOLDEN_PATH.read_text())
    entries = data.get("entries", [])
    if limit:
        entries = entries[:limit]

    print(f"=== golden-set regression: {len(entries)} entries ===")
    print(f"=== golden_set.json version: {data.get('version')}  as_of: {data.get('as_of')} ===")
    print()

    if quick:
        print("--- QUICK MODE: validating harness only (no Ollama) ---")
        for e in entries:
            print(f"  [scaffold-OK] {e['id']} ticker={e['ticker']} source_type={e['source_type']}")
        return 0

    stats = {"pass": 0, "fail": 0, "errors": 0, "false_neg": 0, "false_pos": 0}
    failures: list[dict] = []

    for i, entry in enumerate(entries, 1):
        t0 = time.time()
        eid = entry["id"]
        ticker = entry["ticker"]
        try:
            actual = _ollama_extract(ticker, entry["source_type"], entry["raw_text"])
        except Exception as e:
            stats["errors"] += 1
            print(f"  [{i}/{len(entries)}] ERROR  {eid}  ({type(e).__name__}: {str(e)[:80]})")
            continue

        # Sourcelock validation independently (informational)
        sl_ok, sl_reason = (True, None)
        if not actual.get("no_event"):
            sl_ok, sl_reason = validate(actual, entry["raw_text"], ticker)

        ok, fails = _check_match(entry["expected"], actual)
        elapsed = time.time() - t0

        # Track FN / FP for narrative reporting
        expect_event = not entry["expected"].get("no_event")
        actual_event = not actual.get("no_event")
        if expect_event and not actual_event:
            stats["false_neg"] += 1
        if (not expect_event) and actual_event:
            stats["false_pos"] += 1

        if ok and sl_ok:
            stats["pass"] += 1
            extra = "" if actual.get("no_event") else f"  → {actual.get('event_type')}/{actual.get('direction')}/{actual.get('magnitude')}"
            print(f"  [{i}/{len(entries)}] PASS   {eid}  ({elapsed:.0f}s){extra}")
        else:
            stats["fail"] += 1
            reasons = list(fails)
            if not sl_ok:
                reasons.append(f"SourceLock={sl_reason}")
            print(f"  [{i}/{len(entries)}] FAIL   {eid}  ({elapsed:.0f}s)  {reasons}")
            failures.append({"id": eid, "expected": entry["expected"], "actual": actual, "reasons": reasons})

    print()
    print(f"=== summary ===")
    print(f"  pass:        {stats['pass']} / {len(entries)}")
    print(f"  fail:        {stats['fail']}")
    print(f"  errors:      {stats['errors']}")
    print(f"  false_neg:   {stats['false_neg']} (event expected but model said no_event)")
    print(f"  false_pos:   {stats['false_pos']} (no_event expected but model emitted event)")
    if failures:
        print()
        print("--- failure detail ---")
        for f in failures:
            print(f"  {f['id']}: {f['reasons']}")
            print(f"    expected: {f['expected']}")
            print(f"    actual:   {f['actual']}")

    return 0 if stats["fail"] == 0 and stats["errors"] == 0 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None, help="run only first N entries")
    p.add_argument("--quick", action="store_true", help="scaffold check only, skip Ollama")
    args = p.parse_args(argv)
    return run(limit=args.limit, quick=args.quick)


if __name__ == "__main__":
    sys.exit(main())
