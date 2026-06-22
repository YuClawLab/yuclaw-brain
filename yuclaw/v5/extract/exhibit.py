"""YUCLAW v5 Layer 1 Day 5B — earnings/guidance Exhibit 99.x text extraction.

Day-5A finding: earnings/guidance 8-Ks store only the cover ("see Exhibit 99.1") in
events_raw.raw_text, so EarningsQuality + SentimentDrift ground 0.0 — the results/guidance prose
lives in the un-captured exhibit. Same root-cause family as the Day-3 XBRL finding.

This module re-fetches the EXHIBIT from the filing's EDGAR directory (the index.json lists every
document, including ex*99*.htm) and extracts its prose, REUSING narrative.py's fetch+strip+sanity
(declared UA, polite delay, disk cache) — not a fork. Output is additive to
yuclaw_v5.swarm_inputs (narrative_section='exhibit99'); public.* is read-only.
"""

from __future__ import annotations

import html as _html
import re
from typing import Optional

import httpx
import psycopg2

from yuclaw.v5.extract.narrative import (
    DEFAULT_DSN, USER_AGENT, SEC_SLEEP_SECONDS, NARRATIVE_CAP,
    fetch_primary, strip_filing, _alpha_ratio, _WS_RE,
)
import time

# Exhibit 99.x is the press release / results body. Prefer .htm over .txt; skip images.
_EX99_RE = re.compile(r"(ex|exhibit)[-_]?99", re.I)


def _index_url(source_url: str) -> str:
    return source_url.rsplit("/", 1)[0] + "/index.json"


_R_FILE_RE = re.compile(r"^R\d+\.htm", re.I)            # XBRL viewer fragments
_INDEX_RE = re.compile(r"index", re.I)


def find_exhibit_url(source_url: str, *, timeout: float = 30.0) -> Optional[str]:
    """List the filing directory (index.json) and return the URL of the results-body exhibit.
    Exhibit naming varies (TSLA: exhibit991.htm; PSX: psx-2026_q1prexrelease.htm), so:
      1. prefer an explicitly Exhibit-99-named .htm;
      2. else the LARGEST .htm that is not the primary/cover doc, an XBRL R-file, or an index.
    Deterministic; one request."""
    base = source_url.rsplit("/", 1)[0] + "/"
    primary = source_url.rsplit("/", 1)[1].lower()
    r = httpx.get(base + "index.json", headers={"User-Agent": USER_AGENT}, timeout=timeout)
    time.sleep(SEC_SLEEP_SECONDS)
    r.raise_for_status()
    items = r.json().get("directory", {}).get("item", [])

    ex99, others = [], []
    for it in items:
        name = it.get("name", "")
        low = name.lower()
        if not low.endswith((".htm", ".html")):
            continue
        if low == primary or _R_FILE_RE.match(name) or _INDEX_RE.search(low):
            continue
        try:
            size = int(it.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        (ex99 if _EX99_RE.search(name) else others).append((size, name))

    pool = ex99 or others
    if not pool:
        return None
    pool.sort(reverse=True)  # largest
    return base + pool[0][1]


def extract_exhibit(accession: str, *, dsn: str = DEFAULT_DSN, persist: bool = True,
                    cap: int = NARRATIVE_CAP) -> dict:
    """Locate + fetch the Exhibit 99.x for an earnings/guidance 8-K, strip to prose, store
    additively in swarm_inputs. Returns the record (with narrative_text)."""
    cn = psycopg2.connect(dsn); cn.set_session(readonly=True)
    with cn.cursor() as cur:
        cur.execute("SELECT source_type, source_url FROM public.events_raw "
                    "WHERE accession_number=%s LIMIT 1", (accession,))
        row = cur.fetchone()
    cn.close()
    if not row or not row[1]:
        raise RuntimeError(f"no source_url for {accession!r}")
    source_type, source_url = row
    ex_url = find_exhibit_url(source_url)
    if not ex_url:
        raise RuntimeError(f"no Exhibit 99.x found in filing dir for {accession!r}")
    stripped = strip_filing(fetch_primary(ex_url))            # reuse Day-3 fetch+strip (cached)
    # the exhibit body is prose throughout; take from the first sustained-prose offset
    start = 0
    for i in range(0, max(1, len(stripped) - 1000), 300):
        if _alpha_ratio(stripped[i:i + 1000]) >= 0.72:
            start = i
            break
    narrative = stripped[start:start + cap].strip()
    rec = {"accession_number": accession, "source_type": source_type, "source_url": ex_url,
           "narrative_text": narrative, "narrative_section": "exhibit99",
           "char_len": len(narrative), "alpha_ratio": round(_alpha_ratio(narrative), 3),
           "http_count": narrative.count("http"), "full_doc_len": len(stripped)}
    if persist:
        _persist_exhibit(rec, dsn)
    return rec


def _persist_exhibit(rec: dict, dsn: str) -> None:
    cn = psycopg2.connect(dsn)
    try:
        with cn, cn.cursor() as cur:
            cur.execute(
                """INSERT INTO yuclaw_v5.swarm_inputs
                   (accession_number, source_type, source_url, narrative_text,
                    narrative_section, char_len, alpha_ratio, http_count, full_doc_len)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (accession_number) DO UPDATE SET
                     source_url=EXCLUDED.source_url, narrative_text=EXCLUDED.narrative_text,
                     narrative_section=EXCLUDED.narrative_section, char_len=EXCLUDED.char_len,
                     alpha_ratio=EXCLUDED.alpha_ratio, http_count=EXCLUDED.http_count,
                     full_doc_len=EXCLUDED.full_doc_len, extracted_at=now()""",
                (rec["accession_number"], rec["source_type"], rec["source_url"],
                 rec["narrative_text"], rec["narrative_section"], rec["char_len"],
                 rec["alpha_ratio"], rec["http_count"], rec["full_doc_len"]))
    finally:
        cn.close()


if __name__ == "__main__":
    import sys
    from yuclaw.v5.extract.narrative import sanity_ok
    acc = sys.argv[1] if len(sys.argv) > 1 else "0001628280-26-026551"
    rec = extract_exhibit(acc, persist=False)
    ok, probs = sanity_ok(rec)
    print(f"{acc}  section={rec['narrative_section']}  chars={rec['char_len']}  "
          f"alpha={rec['alpha_ratio']}  http={rec['http_count']}  full={rec['full_doc_len']:,}  "
          f"sanity={'OK' if ok else 'FAIL '+str(probs)}")
    print("url:", rec["source_url"])
    print("--- head ---"); print(rec["narrative_text"][:600])
