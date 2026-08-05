"""
Evidence core (v5.3 "Ground Truth") — the ONE shared implementation of
EvidenceObject construction, used by the why-JSON generator, the
Evidence Passport claim-checker, the MCP v2 tools, and EvidenceBench,
so the four surfaces can never disagree.

EvidenceObject v1 (frozen in schemas/EvidenceObject.v1.json), exactly:
  ticker, evidence_type, filing_date, accession_number, excerpt,
  source_hash, available_as_of, protocol_id

protocol_id is nullable and currently null for every object: evidence
EXTRACTION predates per-event protocol coverage (statistics computed on
events name their protocols in the registry) — disclosed, not faked.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import psycopg2
import psycopg2.extras

DSN = "dbname=yuclaw_events"

# .../edgar/data/<cik>/<18-digit accession, undashed>/<doc>
_ACC_RE = re.compile(r"/edgar/data/\d+/(\d{18})/")
# Form-4 event_ids embed the accession: TICKER_F4_<18 digits>_<n>
_F4_RE = re.compile(r"_F4_(\d{18})_")


def _accession(event_id: str, url: str) -> Optional[str]:
    m = _F4_RE.search(event_id) or _ACC_RE.search(url or "")
    if not m:
        return None
    a = m.group(1)
    return f"{a[:10]}-{a[10:12]}-{a[12:]}"


def evidence_objects(ticker: str, as_of: Optional[str] = None,
                     limit: int = 200) -> list[dict[str, Any]]:
    """Accepted events for `ticker` as frozen EvidenceObjects, newest
    first. as_of (ISO date/timestamp) applies the point-in-time filter
    available_as_of <= as_of — the same rule every scorer uses."""
    q = """SELECT event_id, ticker, event_type,
                  source_publish_time::date AS filing_date,
                  source_url, raw_excerpt, content_hash, available_as_of
           FROM events
           WHERE ticker = %s AND event_status = 'accepted'"""
    params: list[Any] = [ticker.upper()]
    if as_of:
        q += " AND available_as_of <= %s"
        params.append(as_of)
    q += " ORDER BY available_as_of DESC LIMIT %s"
    params.append(limit)
    out = []
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(q, params)
            for (eid, tk, etype, fdate, url, excerpt, chash,
                 avail) in cur.fetchall():
                out.append({
                    "ticker": tk,
                    "evidence_type": etype,
                    "filing_date": fdate.isoformat() if fdate else None,
                    "accession_number": _accession(eid, url),
                    "excerpt": (excerpt or "")[:400],
                    "source_hash": chash,
                    "available_as_of": avail.isoformat(),
                    "protocol_id": None,
                    "_event_id": eid,          # internal join key, stable
                    "_source_url": url,
                })
    return out


def in_universe(ticker: str) -> bool:
    from v3.universe_tiers import scoring_universe
    return ticker.upper() in scoring_universe()
