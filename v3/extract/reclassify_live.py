"""Live, in-ingestion-path event re-classifier (the "rescue" that makes coarse producer
tags usable by the v5 consumers).

The producer LLM (event_worker) is low-precision on the refined categories: it routinely
dumps earnings / financings / M&A into the OTHER_MATERIAL catch-all and emits
M_AND_A_ANNOUNCE / EARNINGS_BEAT rather than the M_AND_A / EARNINGS_RESULT strings the v5
L1 corpus + spawn logic read. The Day-5A batch re-classifier
(yuclaw/v5/extract/reclassify.py, on the v5-layer1 branch) rescues those via verbatim
signature matching, but it is BATCH-ONLY, so new events were never rescued and 4/8 L1 types
were unreachable for new flow.

This module ports that re-classifier into the live event_worker path. The classify/_RULES/
_clean/_match/_filing_text_for logic below is a VERBATIM copy of the v5 batch module so the
live re-tags reproduce the batch corrected-layer exactly (validated against the 28-filing
corpus before shipping). It is ADDITIVE: it writes only to yuclaw_v5.event_type_corrected
(keeping the original producer tag as v4_event_type for audit); public.events.event_type is
never mutated. The v5 consumers read COALESCE(corrected, raw), so a rescue here makes a new
earnings/financing/M&A filing become L1 fuel and spawn its specialist.

SourceLock by construction: every re-tag is justified by a verbatim span; if no signature
matches, the producer tag is kept (no unsupported re-tag). Excerpt-FIRST: each event is
classified against its OWN raw_excerpt, full filing text consulted only when the excerpt is
too short (the D5A cross-contamination guard).
"""

from __future__ import annotations

import html as _html
import re
from typing import Optional

import psycopg2

DB_DSN = "dbname=yuclaw_events"

# ---- VERBATIM from yuclaw/v5/extract/reclassify.py (keep in sync; reproduction-critical) ----
_RULES = [
    ("FINANCING", re.compile(
        r"(revolving credit facility|credit agreement|term loan|senior notes due|notes due 20\d\d|"
        r"aggregate principal amount|underwritten public offering|unsecured revolving|"
        r"\$[\d.,]+ ?(?:billion|million) (?:unsecured )?(?:revolving )?(?:credit|notes|senior notes))", re.I)),
    ("M_AND_A", re.compile(
        r"(merger agreement|business combination|definitive agreement to acquire|agreement to acquire|"
        r"to purchase all of the|tender offer|sale and disposition of|divestiture|"
        r"repurchased from [^.]{0,60}equity interest|closed on the sale)", re.I)),
    ("GOVERNANCE", re.compile(
        r"(cooperation agreement|standstill|letter agreement[^.]{0,40}(?:nominat|board|director)|"
        r"director nominee|proxy contest)", re.I)),
    ("EARNINGS_RESULT", re.compile(
        r"(financial results for|results for (?:its|the) (?:first|second|third|fourth) quarter|"
        r"announced its (?:financial|quarterly) results|reported (?:net|total) revenue|earnings per share)", re.I)),
    ("REGULATORY", re.compile(
        r"(consent decree|settlement agreement|regulatory action|department of justice|"
        r"securities and exchange commission[^.]{0,40}(?:investigation|action)|antitrust)", re.I)),
    ("DIVIDEND", re.compile(
        r"(declared a (?:quarterly )?(?:cash )?dividend|increased its (?:quarterly )?dividend|dividend of \$)", re.I)),
    ("EXEC_CHANGE", re.compile(
        r"(appointed [^.]{0,40}(?:chief|president|officer|director)|resignation of|"
        r"will retire as|named [^.]{0,30}(?:chief executive|cfo|ceo))", re.I)),
]


def _clean(text: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", text or ""))


def _match(t: str):
    for label, rx in _RULES:
        m = rx.search(t)
        if m:
            start = max(0, m.start() - 40)
            return label, m, t[start:m.end() + 60].strip()
    return None


def classify(excerpt: str, v4_type: str, full_text: Optional[str] = None,
             excerpt_min: int = 160) -> dict:
    """Deterministic re-classification, SourceLock against the EVENT's own excerpt FIRST so a
    multi-event filing can't cross-contaminate. Falls back to the full filing text ONLY when the
    excerpt is too short to classify. Keeps v4_type if nothing matches — no unsupported re-tag."""
    ex = _clean(excerpt)
    hit = _match(ex)
    if hit:
        label, m, span = hit
        return {"corrected_type": label, "signature": m.group(0)[:80], "span": span[:300],
                "start": m.start(), "source": "excerpt"}
    if full_text and len(ex) < excerpt_min:
        hit = _match(_clean(full_text))
        if hit:
            label, m, span = hit
            return {"corrected_type": label, "signature": m.group(0)[:80], "span": span[:300],
                    "start": m.start(), "source": "filing(excerpt-truncated)"}
    return {"corrected_type": v4_type, "signature": None, "span": None, "start": None,
            "source": "kept"}


def _filing_text_for(accession: str, source_url: str, dsn: str = DB_DSN) -> Optional[str]:
    """Prefer the Day-3 extracted MD&A narrative (prose); else the raw events_raw text.
    For NEW events swarm_inputs has no row, so this returns the raw filing text."""
    cn = psycopg2.connect(dsn); cn.set_session(readonly=True)
    try:
        with cn.cursor() as cur:
            cur.execute("SELECT narrative_text FROM yuclaw_v5.swarm_inputs WHERE accession_number=%s", (accession,))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
            cur.execute("SELECT raw_text FROM public.events_raw WHERE source_url=%s", (source_url,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        cn.close()
# ---- end verbatim block ----


def reclassify_one(event_id: str, accession: str, ticker: str, v4_type: str,
                   excerpt: str, source_url: str, dsn: str = DB_DSN) -> dict:
    """Classify one event (excerpt-first, SourceLock) and persist the corrected tag additively
    to yuclaw_v5.event_type_corrected. Returns the result record. Used by the live event_worker
    right after it commits an accepted event."""
    full = _filing_text_for(accession, source_url, dsn)  # fallback for truncated excerpts
    c = classify(excerpt or "", v4_type, full_text=full)
    rec = {"event_id": event_id, "accession_number": accession, "ticker": ticker,
           "v4_event_type": v4_type, "corrected_event_type": c["corrected_type"],
           "changed": c["corrected_type"] != v4_type, "match_signature": c["signature"],
           "source_span": c["span"], "source_start": c["start"], "source": c["source"]}
    _persist([rec], dsn)
    return rec


def _persist(recs: list[dict], dsn: str = DB_DSN) -> None:
    cn = psycopg2.connect(dsn)
    try:
        with cn, cn.cursor() as cur:
            for r in recs:
                cur.execute(
                    """INSERT INTO yuclaw_v5.event_type_corrected
                       (event_id, accession_number, ticker, v4_event_type, corrected_event_type,
                        changed, match_signature, source_span, source_start, method)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'rules')
                       ON CONFLICT (event_id) DO UPDATE SET
                         corrected_event_type=EXCLUDED.corrected_event_type, changed=EXCLUDED.changed,
                         match_signature=EXCLUDED.match_signature, source_span=EXCLUDED.source_span,
                         source_start=EXCLUDED.source_start, corrected_at=now()""",
                    (r["event_id"], r["accession_number"], r["ticker"], r["v4_event_type"],
                     r["corrected_event_type"], r["changed"], r["match_signature"],
                     r["source_span"], r["source_start"]))
    finally:
        cn.close()
