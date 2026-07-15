"""Live prose-first ingestion hook (ports the proven f130983e fix to production).

Called by the event worker AFTER its transaction commits, best-effort, for every
processed filing row. Mirrors the v5 validation chain
(yuclaw/v5/swarm/tests/validate_scale.py::_acquire_text) with persistence ON:

  * 8-K            -> exhibit extractor (ANY 8-K, not just earnings types —
                      FINANCING/M&A/governance 8-Ks carry prose exhibits too)
  * 10-K / 10-Q    -> MD&A narrative extractor
  * sanity-gated   -> prose is persisted to yuclaw_v5.swarm_inputs ONLY when it
                      passes narrative.sanity_ok; otherwise NOTHING is written
                      and the swarm's raw_cover fallback stands (M&A no-exhibit
                      cases fall back silently — never an error).

Storage is ADDITIVE (yuclaw_v5.swarm_inputs upsert); public.* stays read-only
here. Idempotent: an accession already holding a narrative is skipped without
an EDGAR fetch. Never raises — a prose failure must not fail ingestion.
"""

from __future__ import annotations

import psycopg2

from v3.extract.exhibit import (_persist_exhibit, cover_exhibit_hint, extract_exhibit,
                                extract_exhibit_narrative)
from v3.extract.narrative import DEFAULT_DSN, _persist, extract_and_store, sanity_ok

# 6-K/40-F (MJDS foreign private issuers, Canada Resources evidence tier, 2026-07-14):
# both are cover-page envelopes whose substance is furnished as EX-99.x/EX-13.x exhibits
# — the exhibit extractor is the ONLY correct prose source; the primary doc is boilerplate.
PROSE_FORMS = ("8-K", "10-K", "10-Q", "6-K", "40-F")


def _existing(accession: str) -> bool:
    cn = psycopg2.connect(DEFAULT_DSN)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT 1 FROM yuclaw_v5.swarm_inputs "
                        "WHERE accession_number=%s AND narrative_text IS NOT NULL",
                        (accession,))
            return cur.fetchone() is not None
    finally:
        cn.close()


def ingest_prose(accession: str | None, form: str | None) -> tuple[str, str]:
    """Best-effort prose acquisition for one filing. Returns (status, detail);
    status in {'exhibit99','mdna','risk_factors','business','existing','skip',
    'fallback_raw_cover'}. NEVER raises."""
    try:
        if not accession or form not in PROSE_FORMS:
            return ("skip", form or "no-form")
        if _existing(accession):
            return ("existing", "")
        if form in ("8-K", "6-K"):
            rec = extract_exhibit(accession, persist=False)
            ok, probs = sanity_ok(rec)
            if ok:
                _persist_exhibit(rec, DEFAULT_DSN)
                return (rec["narrative_section"], f"{rec['char_len']} chars")
            return ("fallback_raw_cover", f"exhibit sanity {probs}")
        if form == "40-F":
            # annual-report prose path: MD&A anchor search inside the exhibit
            rec = extract_exhibit_narrative(accession, persist=False)
            ok, probs = sanity_ok(rec)
            if ok:
                _persist_exhibit(rec, DEFAULT_DSN)
                return (rec["narrative_section"], f"{rec['char_len']} chars")
            return ("fallback_raw_cover", f"exhibit narrative sanity {probs}")
        # 10-K / 10-Q -> MD&A narrative
        rec = extract_and_store(accession, persist=False)
        ok, probs = sanity_ok(rec)
        if ok:
            _persist(rec, DEFAULT_DSN)
            return (rec["narrative_section"], f"{rec['char_len']} chars")
        return ("fallback_raw_cover", f"narrative sanity {probs}")
    except Exception as e:  # silent fallback — raw_cover remains the swarm's source
        return ("fallback_raw_cover", f"{type(e).__name__}: {str(e)[:100]}")


# ---------------------------------------------------------------------------
# 6-K/40-F classifier input (Canada Resources evidence tier, 2026-07-14)
# ---------------------------------------------------------------------------
def _stored_narrative(accession: str) -> str | None:
    cn = psycopg2.connect(DEFAULT_DSN)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT narrative_text FROM yuclaw_v5.swarm_inputs "
                        "WHERE accession_number=%s", (accession,))
            row = cur.fetchone()
            return row[0] if row and row[0] else None
    finally:
        cn.close()


def compose_foreign_input(accession: str | None, form: str | None,
                          cover_text: str | None) -> str | None:
    """LLM input for a 6-K/40-F: cover-page exhibit-index HINT + exhibit prose BODY.

    The cover page alone is boilerplate — classifying on it is the false-success mode
    (filing looks ingested, only cover persisted). The hint is prepended context; the
    body is always the exhibit prose. Ensures the prose is persisted (sanity-gated)
    as a side effect. Returns None when no sanity-passing exhibit prose is available —
    the caller falls back to the raw cover, which typically yields no_event."""
    if not accession or form not in ("6-K", "40-F"):
        return None
    try:
        ingest_prose(accession, form)          # idempotent; persists when sane
        prose = _stored_narrative(accession)
        if not prose:
            return None
        hint = cover_exhibit_hint(cover_text or "")
        return (hint + "\n\n" + prose) if hint else prose
    except Exception:
        return None
