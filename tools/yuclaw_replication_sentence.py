#!/usr/bin/env python3
"""
Replication sentence — GENERATED from docs/replication/replication_log.json
(ORDER 2026-09-05B B2). One sentence pair, derived, never typed:

  "Designed for reproduction from published artifacts. <N> affiliated
   external-machine reproduction(s) recorded; unaffiliated replications: <k>."

Written to docs/replication/replication_sentence.txt — the canonical source
file for the REPLICATION-SENTENCE copy block that README.md (and therefore
the PyPI long description) embeds verbatim between fixed markers;
tools/check_copy_consistency.py asserts the embedded copy byte-for-byte and
that this file is current against the log.

Usage: python3 tools/yuclaw_replication_sentence.py            # write
       python3 tools/yuclaw_replication_sentence.py --check    # exit 1 if stale
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
LOG = _REPO / "docs" / "replication" / "replication_log.json"
OUT = _REPO / "docs" / "replication" / "replication_sentence.txt"
_WORDS = {0: "No", 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
          6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}


def derive(log: dict) -> str:
    entries = log.get("replications", [])
    ext_ok = [e for e in entries if e.get("replication_machine_external") is True
              and str(e.get("replication_result", "")).upper() == "REPRODUCED"]
    n_aff = sum(1 for e in ext_ok if str(e.get("operator_affiliation", "")).upper() == "AFFILIATED")
    n_unaff = sum(1 for e in ext_ok if str(e.get("operator_affiliation", "")).upper() == "UNAFFILIATED")
    n_aff_word = _WORDS.get(n_aff, str(n_aff))
    noun = "reproduction" if n_aff == 1 else "reproductions"
    if n_aff == 0:
        second = "No affiliated external-machine reproduction recorded"
    else:
        second = f"{n_aff_word} affiliated external-machine {noun} recorded"
    return (f"Designed for reproduction from published artifacts. {second}; "
            f"unaffiliated replications: {n_unaff}.")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    sentence = derive(json.loads(LOG.read_text()))
    if "--check" in argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        if cur != sentence + "\n":
            print(f"[replication-sentence] STALE: file {cur!r} != derived {sentence!r}")
            return 1
        print(f"[replication-sentence] OK — {sentence}")
        return 0
    OUT.write_text(sentence + "\n", encoding="utf-8")
    print(f"[replication-sentence] wrote {OUT}: {sentence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
