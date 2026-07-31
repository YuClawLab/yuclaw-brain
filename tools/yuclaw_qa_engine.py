#!/usr/bin/env python3
"""
Q&A engine v1 (E-tranche; STAGED — the public surface is LAWYER-GATED:
nothing here may be wired to any public page or external channel until
counsel signs off on the engagement/disclaimer framework; CLI and staged
preview only, per the standing gate).

Evidence-constrained answering over the events store. Zero generation:
retrieval + deterministic template assembly under the memo rail —
restricted vocabulary (full-rail lint on every answer, build fails on a
banned term), a mandatory citation verifier (every accession/event cited
must exist in the store, checked before emission), the frozen implication
line on every answer, and refusal with a stated reason for anything
outside evidence scope (price questions, advice-shaped questions,
unknown tickers).

CLI: python3 tools/yuclaw_qa_engine.py "What evidence events does MU have?"
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from check_language import lint_text

DSN = "dbname=yuclaw_events"
IMPLICATION = ("Investment implication: none established — no buy, sell, or "
               "alpha conclusion is supported by this answer.")
ADVICE_WORDS = ("should i", "buy", "sell", "price target", "forecast",
                "predict", "will it go", "worth investing", "recommend")


def _known_tickers():
    from v3.lab.etf_evidence import _universe
    from v3.universe_tiers import evidence_cik_map
    return set(_universe()) | set(evidence_cik_map())


def answer(question: str) -> dict:
    q = question.strip()
    ql = q.lower()
    for w in ADVICE_WORDS:
        if w in ql:
            return {"refused": True,
                    "reason": ("outside evidence scope: the question asks for "
                               "advice, prediction, or price direction; this "
                               "engine reports recorded evidence only")}
    tickers = [t for t in re.findall(r"\b[A-Z]{1,5}\b", q)
               if t in _known_tickers()]
    if not tickers:
        return {"refused": True,
                "reason": ("outside evidence scope: no covered ticker "
                           "recognized in the question; coverage = the "
                           "scored universe plus the evidence tier")}
    tk = tickers[0]
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT event_type, direction, event_time::date, event_id
                   FROM events WHERE event_status='accepted' AND ticker=%s
                   ORDER BY event_time DESC LIMIT 10""", (tk,))
            events = cur.fetchall()
            cur.execute(
                """SELECT count(*) FROM events
                   WHERE event_status='accepted' AND ticker=%s""", (tk,))
            total = cur.fetchone()[0]
    if not events:
        return {"refused": True,
                "reason": f"no accepted evidence events recorded for {tk}"}

    # citation verifier: every cited event_id must round-trip to the store
    cited = [e[3] for e in events]
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT count(*) FROM events WHERE event_id = ANY(%s)",
                        (cited,))
            if cur.fetchone()[0] != len(cited):
                raise RuntimeError("citation verifier FAILED — refusing to emit")

    lines = [f"{tk} has {total} accepted evidence events on record. "
             f"The {len(events)} most recent:"]
    for et, dirn, d, eid in events:
        lines.append(f"  - {d} {et} (direction {dirn:+d}) [cite: {eid}]")
    lines.append(IMPLICATION)
    text = "\n".join(lines)
    problems = lint_text(text, pages_mode=True)
    if problems:
        raise RuntimeError(f"language rail FAILED on assembled answer: "
                           f"{problems[:2]} — refusing to emit")
    return {"refused": False, "ticker": tk, "answer": text,
            "citations": cited,
            "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: yuclaw_qa_engine.py \"<question>\"")
        return 2
    r = answer(" ".join(sys.argv[1:]))
    if r["refused"]:
        print(f"REFUSED — {r['reason']}")
        return 1
    print(r["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
