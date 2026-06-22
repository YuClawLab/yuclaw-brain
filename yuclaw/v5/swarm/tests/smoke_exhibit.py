"""YUCLAW v5 Layer 1 Day 5B — exhibit-extraction HARD GATE.

Before: EarningsQuality + SentimentDrift grounded 0.0 because earnings/guidance 8-K raw_text is
only the cover. After: extract the Exhibit 99.x results/guidance prose and re-run the same
specialists. Prints grounding before -> after, verbatim. Gate passes only if grounding LIFTS.

Usage: python3 -m yuclaw.v5.swarm.tests.smoke_exhibit
"""

from __future__ import annotations

import subprocess
import sys

import psycopg2

from yuclaw.v5.extract.exhibit import extract_exhibit
from yuclaw.v5.extract.narrative import sanity_ok
from yuclaw.v5.swarm.specialists import SpecialistAgent
from yuclaw.v5.swarm.worker import WORKER_MODEL

# (specialist, accession, label) — earnings -> earningsquality; guidance -> sentimentdrift
CASES = [
    ("earningsquality", "0001628280-26-026551", "TSLA earnings 8-K"),
    ("sentimentdrift",  "0001534701-26-000015", "PSX guidance-cut 8-K"),
]


def _preflight() -> None:
    ps = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    bad = [l for l in ps.splitlines() if any(t in l for t in ("llama-server", "vllm")) and "ollama" not in l.lower()]
    if bad:
        print("PREFLIGHT FAIL:", bad[:2]); sys.exit(3)


def _raw_text(acc: str) -> str:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("SELECT raw_text FROM public.events_raw WHERE accession_number=%s", (acc,))
    row = cur.fetchone(); cn.close()
    return row[0] if row else ""


def _run(key: str, text: str) -> dict:
    g = SpecialistAgent(key, model=WORKER_MODEL).run(text)["grounding"]
    return {"rate": g["grounding_rate"], "grounded": g["points_grounded"],
            "total": g["points_total"], "cv": g["citations_verified"], "ct": g["citations_total"]}


def main() -> int:
    _preflight()
    print(f"=== DAY-5B EXHIBIT GATE (WORKER_MODEL={WORKER_MODEL}) ===\n")
    ok_all = True
    for key, acc, label in CASES:
        before = _run(key, _raw_text(acc))                       # cover-only (Day-5A: 0.0)
        rec = extract_exhibit(acc, persist=False)                 # fetch exhibit prose
        san, probs = sanity_ok(rec)
        if not san:
            print(f"[{key}] {label}: exhibit sanity FAIL {probs}"); ok_all = False; continue
        after = _run(key, rec["narrative_text"])
        lifted = after["rate"] > before["rate"]
        ok_all = ok_all and lifted
        print(f"[{key.upper()}] {label}  (exhibit {rec['char_len']} chars, alpha {rec['alpha_ratio']})")
        print(f"   BEFORE (cover raw_text): grounding={before['rate']} "
              f"grounded={before['grounded']}/{before['total']} cites={before['cv']}/{before['ct']}")
        print(f"   AFTER  (exhibit prose) : grounding={after['rate']} "
              f"grounded={after['grounded']}/{after['total']} cites={after['cv']}/{after['ct']}")
        print(f"   -> {'LIFTED' if lifted else 'NOT improved'}\n")
    print("=== GATE:", "PASS" if ok_all else "FAIL", "===")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
