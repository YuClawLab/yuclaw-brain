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

from v3.extract.exhibit import _persist_exhibit, extract_exhibit
from v3.extract.narrative import DEFAULT_DSN, _persist, extract_and_store, sanity_ok

PROSE_FORMS = ("8-K", "10-K", "10-Q")


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
        if form == "8-K":
            rec = extract_exhibit(accession, persist=False)
            ok, probs = sanity_ok(rec)
            if ok:
                _persist_exhibit(rec, DEFAULT_DSN)
                return (rec["narrative_section"], f"{rec['char_len']} chars")
            return ("fallback_raw_cover", f"exhibit sanity {probs}")
        # 10-K / 10-Q -> MD&A narrative
        rec = extract_and_store(accession, persist=False)
        ok, probs = sanity_ok(rec)
        if ok:
            _persist(rec, DEFAULT_DSN)
            return (rec["narrative_section"], f"{rec['char_len']} chars")
        return ("fallback_raw_cover", f"narrative sanity {probs}")
    except Exception as e:  # silent fallback — raw_cover remains the swarm's source
        return ("fallback_raw_cover", f"{type(e).__name__}: {str(e)[:100]}")
