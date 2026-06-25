"""YUCLAW v5 Layer 1 Day 5A — deterministic, SourceLock-backed event-type re-classifier.

The v4 extractor mis-tags some events (the Day-4 finding: a $5B credit facility tagged
M_AND_A_ANNOUNCE; a Cooperation Agreement tagged M&A; earnings/financings dumped into
OTHER_MATERIAL). This module re-classifies events DETERMINISTICALLY by matching ordered
verbatim signature phrases against the FULL filing text (not the truncated raw_excerpt the v4
extractor sometimes saw). No LLM: every corrected tag is justified by a verbatim span found in
the filing (SourceLock by construction). If no signature matches, the v4 tag is kept — no
unsupported re-tags.

Writes to yuclaw_v5.event_type_corrected ONLY. public.events / public.* are never mutated.
Insider events (Form 4, no filing text) are correct by construction and skipped.
"""

from __future__ import annotations

import html as _html
import os
import re
from typing import Optional

import psycopg2

DSN = os.environ.get("YUCLAW_V5_DSN", "dbname=yuclaw_events")

# Refined taxonomy. Ordered MOST-SPECIFIC first: a credit facility is FINANCING even though it
# is an "agreement"; a divestiture is M&A even though it is a "sale". Each rule is a verbatim
# regex; the matched text becomes the SourceLock span. Tuned to the confusion patterns found in
# Part 1 (financings & earnings hiding in OTHER_MATERIAL / mis-tagged as M&A).
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
    ("REGULATORY_ACTION", re.compile(  # consumers (L1 query + SPAWN_MAP) key on REGULATORY_ACTION
        r"(consent decree|settlement agreement|regulatory action|department of justice|"
        r"securities and exchange commission[^.]{0,40}(?:investigation|action)|antitrust)", re.I)),
    ("DIVIDEND", re.compile(
        r"(declared a (?:quarterly )?(?:cash )?dividend|increased its (?:quarterly )?dividend|dividend of \$)", re.I)),
    ("EXEC_CHANGE", re.compile(
        r"(appointed [^.]{0,40}(?:chief|president|officer|director)|resignation of|"
        r"will retire as|named [^.]{0,30}(?:chief executive|cfo|ceo))", re.I)),
]

# v4 tags we trust as-is (no filing-text re-class needed / already specific enough).
_KEEP_IF_NO_MATCH = True


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
    multi-event filing can't cross-contaminate (a divestiture elsewhere in the filing must not
    re-tag a regulatory event). Falls back to the full filing text ONLY when the excerpt is too
    short to classify (e.g. the v4 extractor truncated it, as in the AMD credit-facility case).
    Keeps v4_type if nothing matches — no unsupported re-tag."""
    ex = _clean(excerpt)
    hit = _match(ex)
    if hit:
        label, m, span = hit
        return {"corrected_type": label, "signature": m.group(0)[:80], "span": span[:300],
                "start": m.start(), "source": "excerpt"}
    # excerpt yielded nothing AND it looks truncated -> consult the full filing
    if full_text and len(ex) < excerpt_min:
        hit = _match(_clean(full_text))
        if hit:
            label, m, span = hit
            return {"corrected_type": label, "signature": m.group(0)[:80], "span": span[:300],
                    "start": m.start(), "source": "filing(excerpt-truncated)"}
    return {"corrected_type": v4_type, "signature": None, "span": None, "start": None,
            "source": "kept"}


def _filing_text_for(accession: str, source_url: str) -> Optional[str]:
    """Prefer the Day-3 extracted MD&A narrative (prose); else the raw events_raw text."""
    cn = psycopg2.connect(DSN); cn.set_session(readonly=True)
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


def reclassify_all(persist: bool = True, only_event_id: Optional[str] = None) -> list[dict]:
    """Re-classify every ORIGINAL (non-cascade) event that has a reachable filing. READ-ONLY on
    public.*; writes corrected tags to yuclaw_v5.event_type_corrected."""
    cn = psycopg2.connect(DSN); cn.set_session(readonly=True)
    cur = cn.cursor()
    q = ("SELECT e.event_id, e.ticker, e.event_type, e.raw_excerpt, e.source_url, er.accession_number "
         "FROM public.events e JOIN public.events_raw er ON er.source_url=e.source_url "
         "WHERE e.event_id NOT LIKE 'CASCADE%%'")
    params: tuple = ()
    if only_event_id:
        q += " AND e.event_id=%s"; params = (only_event_id,)
    cur.execute(q, params)
    rows = cur.fetchall(); cn.close()

    results = []
    for event_id, ticker, v4_type, excerpt, source_url, accession in rows:
        full = _filing_text_for(accession, source_url)  # fallback for truncated excerpts
        c = classify(excerpt or "", v4_type, full_text=full)
        rec = {"event_id": event_id, "accession_number": accession, "ticker": ticker,
               "v4_event_type": v4_type, "corrected_event_type": c["corrected_type"],
               "changed": c["corrected_type"] != v4_type, "match_signature": c["signature"],
               "source_span": c["span"], "source_start": c["start"], "source": c["source"]}
        results.append(rec)
    if persist:
        _persist(results)
    return results


def _persist(recs: list[dict]) -> None:
    cn = psycopg2.connect(DSN)
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


def corrected_event_types(accession: str, dsn: str = DSN) -> list[dict]:
    """Spawn helper: corrected event types for a filing (falls back to v4 tags for events with no
    corrected row). Returns [{event_type, source}] — source = 'corrected' | 'v4'."""
    cn = psycopg2.connect(dsn); cn.set_session(readonly=True)
    try:
        with cn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(c.corrected_event_type, e.event_type) AS et, "
                "       CASE WHEN c.event_id IS NULL THEN 'v4' ELSE 'corrected' END "
                "FROM public.events e "
                "JOIN public.events_raw er ON er.source_url=e.source_url "
                "LEFT JOIN yuclaw_v5.event_type_corrected c ON c.event_id=e.event_id "
                "WHERE er.accession_number=%s AND e.event_id NOT LIKE 'CASCADE%%'", (accession,))
            return [{"event_type": et, "source": src} for et, src in cur.fetchall()]
    finally:
        cn.close()


if __name__ == "__main__":
    import sys, json
    recs = reclassify_all(persist=False)
    changed = [r for r in recs if r["changed"]]
    print(f"re-classified {len(recs)} events; {len(changed)} changed")
    for r in changed:
        print(f"\n[{r['ticker']}] {r['v4_event_type']} -> {r['corrected_event_type']}  ({r['match_signature']!r})")
        print(f"   span: {r['source_span']!r}")
