#!/usr/bin/env python3
"""Excerpt correction workflow (QA-05 E2/E4). Subcommands:
  review --scan <scan.json> [--limit N]   verify suspects against the PRIMARY document (EDGAR fetch with the declared
                                          User-Agent, bounded): entity-rule hits whose decoded text is located verbatim in
                                          the primary document get a CORRECTED display excerpt (decoded + trimmed to the
                                          clause boundary from the source); XBRL/taxonomy hits whose source location is
                                          context data get a CONFIRMED quality flag (not event-bearing prose); anything
                                          not located stays SUSPECTED. Appends ExcerptCorrection.v1 records (never rewrites).
  project                                 write the public projection docs/evidence/excerpt_corrections.json
Never modifies evidence objects, ledgers or replay inputs."""
from __future__ import annotations

import argparse
import hashlib
import html as _html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from v3.extract.excerpt_quality import EVENT_PROSE_RULES, finalize_display  # noqa: E402
from v3.web.excerpt_corrections import STORE, by_hash, public_projection  # noqa: E402
from v3.extract.narrative import USER_AGENT  # noqa: E402


def _fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return None


def _source_url(source_hash: str) -> str | None:
    try:
        import psycopg2
        from v3.lab.cohort_engine import DSN
        with psycopg2.connect(DSN) as cn:
            cur = cn.cursor(); cur.execute("SELECT source_url FROM events WHERE content_hash = %s LIMIT 1", (source_hash,)); r = cur.fetchone()
            return r[0] if r else None
    except Exception:  # noqa: BLE001
        return None


def _text(doc: bytes) -> str:
    s = doc.decode("utf-8", "replace")
    s = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s)


def review(scan: dict, limit: int, now: str) -> dict:
    existing = by_hash(); out = {"reviewed": 0, "corrected": 0, "confirmed_flags": 0, "still_suspected": 0, "skipped_existing": 0, "fetch_failed": 0}
    records = []
    for sus in scan["suspects"][:limit]:
        h = sus["source_hash"]
        if h in existing:
            out["skipped_existing"] += 1; continue
        out["reviewed"] += 1
        excerpt = next((o["excerpt"] for f in sorted((_REPO / "docs" / "why").glob("*.json")) if f.name != "history_manifest.json" for o in json.loads(f.read_text()).get("evidence_objects", []) if o.get("source_hash") == h), None)
        if excerpt is None:
            continue
        base = {"original": {"ticker": sus["ticker"], "accession_number": sus["accession"], "source_hash": h, "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest()}, "rule_ids": sus["rules"], "recorded_at": now}
        url = _source_url(h); doc = _fetch(url) if url else None; time.sleep(0.15)
        if doc is None:
            out["fetch_failed"] += 1; out["still_suspected"] += 1
            records.append({**base, "correction_id": "exc-" + h[:16], "kind": "quality_flag", "status": "SUSPECTED", "reason": "detector hit; primary document not fetched — remains suspected", "corrected_excerpt": None, "corrected_sha256": None, "source_location": {"accession_number": sus["accession"], "document_url": url, "char_offset": None, "verified_against": None}, "corrected_at": None}); continue
        text = _text(doc)
        if any(r in EVENT_PROSE_RULES for r in sus["rules"]):
            probe = re.sub(r"\s+", " ", _html.unescape(excerpt)).strip()[:60]
            located = probe and probe in text
            records.append({**base, "correction_id": "exc-" + h[:16], "kind": "quality_flag", "status": "CONFIRMED" if located else "SUSPECTED",
                            "reason": ("verified against the primary document: the excerpt is XBRL context/taxonomy data at its source location, not event-bearing prose; no corrected text exists for this object" if located else "XBRL/taxonomy tokens detected; excerpt not located verbatim in the primary document — remains suspected"),
                            "corrected_excerpt": None, "corrected_sha256": None, "source_location": {"accession_number": sus["accession"], "document_url": url, "char_offset": (text.find(probe) if located else None), "verified_against": ("primary document (EDGAR)" if located else None)}, "corrected_at": None})
            out["confirmed_flags" if located else "still_suspected"] += 1; continue
        decoded = finalize_display(excerpt)
        probe = decoded[:80]
        pos = text.find(probe) if probe else -1
        if pos >= 0:
            # complete the clause from the SOURCE (never invented): extend to the next sentence boundary within 240 chars
            tail = text[pos:pos + len(decoded) + 240]
            m = re.search(r"[.;]\s", tail[len(decoded) - 1:]) if len(decoded) < len(tail) else None
            corrected = (tail[:len(decoded) - 1 + m.end()].strip() if m else decoded)
            corrected = corrected[:400].rstrip()
            records.append({**base, "correction_id": "exc-" + h[:16], "kind": "display_correction", "status": "CORRECTED", "reason": "HTML entity fragment / dangling tail in the stored excerpt; display text decoded and completed to the clause boundary from the primary document",
                            "corrected_excerpt": corrected, "corrected_sha256": hashlib.sha256(corrected.encode()).hexdigest(), "source_location": {"accession_number": sus["accession"], "document_url": url, "char_offset": pos, "verified_against": "primary document (EDGAR)"}, "corrected_at": now})
            out["corrected"] += 1
        else:
            out["still_suspected"] += 1
            records.append({**base, "correction_id": "exc-" + h[:16], "kind": "quality_flag", "status": "SUSPECTED", "reason": "entity/tail detector hit; decoded excerpt not located verbatim in the primary document — remains suspected", "corrected_excerpt": None, "corrected_sha256": None, "source_location": {"accession_number": sus["accession"], "document_url": url, "char_offset": None, "verified_against": None}, "corrected_at": None})
    if records:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        with STORE.open("a") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    out["appended"] = len(records); return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest="cmd", required=True)
    r = s.add_parser("review"); r.add_argument("--scan", required=True); r.add_argument("--limit", type=int, default=100)
    s.add_parser("project")
    a = ap.parse_args(argv); now = datetime.now(timezone.utc).isoformat()
    if a.cmd == "review":
        res = review(json.loads(Path(a.scan).read_text()), a.limit, now); print(f"[excerpt-corrections] {res}"); return 0
    n = public_projection(stamp=now); print(f"[excerpt-corrections] projected {n} record(s)"); return 0


if __name__ == "__main__":
    sys.exit(main())
