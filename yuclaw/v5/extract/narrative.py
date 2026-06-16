"""YUCLAW v5 Layer 1 Day 3 — MD&A / narrative prose extractor (deterministic, no LLM).

Day-2 root cause: the swarm reads ``public.events_raw.raw_text``, but for 10-K/10-Q that
is the first 8000 chars of the iXBRL primary document — the ``<ix:header>`` cover, all
taxonomy URLs (``http://fasb.org/us-gaap/...``), never reaching the MD&A. Bull/Bear ground
~0.0 because there is no quotable prose.

The primary document fetched by the v3 poller is the RIGHT file — the narrative (Item 7
MD&A, Item 1A Risk Factors, Item 1 Business) lives ~70k chars deep. This module re-fetches
the full primary document from the SAME ``source_url`` already on record, strips the iXBRL
noise properly, locates the narrative section, and returns clean prose for the swarm to
quote.

Storage is ADDITIVE: ``yuclaw_v5.swarm_inputs`` only. ``events_raw`` and every ``public.*``
table are read-only here. EDGAR is hit with the declared User-Agent and a polite delay; this
module fetches ONE document per call (smoke/batch = a handful), never a bulk sweep.
"""

from __future__ import annotations

import hashlib
import html as _html
import os
import re
import time
from pathlib import Path
from typing import Optional

import httpx
import psycopg2

DEFAULT_DSN = os.environ.get("YUCLAW_V5_DSN", "dbname=yuclaw_events")
# Declared SEC User-Agent (with contact). SEC asks for a UA identifying the requester.
USER_AGENT = os.environ.get("YUCLAW_V5_EDGAR_UA", "YuClawLab v5 research yuclawlab@example.com")
SEC_SLEEP_SECONDS = float(os.environ.get("YUCLAW_V5_EDGAR_SLEEP", "0.2"))  # <10 req/s
NARRATIVE_CAP = int(os.environ.get("YUCLAW_V5_NARRATIVE_CAP", "16000"))    # stored prose cap

# Narrative section anchors, in priority order. MD&A is the richest for a bull/bear case.
_ANCHORS = [
    ("mdna", re.compile(r"Management['’]s Discussion and Analysis", re.I)),
    ("risk_factors", re.compile(r"Risk Factors", re.I)),
    ("business", re.compile(r"\bItem\s*1\.\s*Business\b", re.I)),
]

_IX_HEADER_RE = re.compile(r"<ix:header\b.*?</ix:header>", re.I | re.S)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


# --------------------------------------------------------------------------
# Fetch + strip
# --------------------------------------------------------------------------
_CACHE_DIR = Path(os.environ.get("YUCLAW_V5_EDGAR_CACHE", "/tmp/yuclaw_v5_edgar_cache"))


def fetch_primary(url: str, *, timeout: float = 60.0, use_cache: bool = True) -> str:
    """GET the primary document with the declared UA + a polite delay (one request).

    Caches the raw response on disk keyed by URL so repeated runs/tests never re-hit EDGAR
    for the same document (fair-access courtesy)."""
    cache_file = _CACHE_DIR / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".html")
    if use_cache and cache_file.exists():
        return cache_file.read_text(encoding="utf-8", errors="replace")
    r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
                  timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    time.sleep(SEC_SLEEP_SECONDS)
    if use_cache:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(r.text, encoding="utf-8", errors="replace")
    return r.text


def strip_filing(raw_html: str) -> str:
    """HTML/iXBRL -> plain text. Crucially removes the ``<ix:header>`` block (the source of
    the taxonomy-URL soup), plus scripts/styles/comments, then tags; unescapes entities."""
    s = _IX_HEADER_RE.sub(" ", raw_html)
    s = _SCRIPT_STYLE_RE.sub(" ", s)
    s = _COMMENT_RE.sub(" ", s)
    s = _TAG_RE.sub(" ", s)
    s = _html.unescape(s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def _alpha_ratio(s: str) -> float:
    if not s:
        return 0.0
    return sum(c.isalpha() for c in s) / len(s)


# --------------------------------------------------------------------------
# Narrative location
# --------------------------------------------------------------------------
# A table-of-contents entry looks like "<title> <pagenum> Item NN." right after the anchor.
_TOC_AFTER_RE = re.compile(r"\d{1,4}\s+Item\b", re.I)


def _is_toc_hit(text: str, end: int, look: int = 110) -> bool:
    """True if the anchor at this position is a table-of-contents line (title immediately
    followed by a page number and the next 'Item NN'), not the section body."""
    return bool(_TOC_AFTER_RE.search(text[end:end + look]))


def _best_anchor_pos(text: str, rx: re.Pattern, probe: int = 4000) -> Optional[int]:
    """Among all matches of ``rx``, return the start offset of the real section BODY — the
    densest-prose occurrence that is NOT a table-of-contents entry. TOC entries are followed
    by '<pagenum> Item NN' and are excluded; only if every hit looks like TOC do we fall back
    to the densest one."""
    body, body_score = None, -1.0
    any_pos, any_score = None, -1.0
    for m in rx.finditer(text):
        p = m.start()
        score = sum(c.isalpha() for c in text[p:p + probe])  # dense prose scores high
        if score > any_score:
            any_score, any_pos = score, p
        if _is_toc_hit(text, m.end()):
            continue
        if score > body_score:
            body_score, body = score, p
    return body if body is not None else any_pos


def _fallback_prose_start(text: str, win: int = 1200) -> int:
    """For docs without a clear section anchor (e.g. 8-K): first offset where a sustained
    high-alpha prose region begins, skipping any iXBRL/cover prefix."""
    step = 400
    for i in range(0, max(1, len(text) - win), step):
        if _alpha_ratio(text[i:i + win]) >= 0.70:
            return i
    return 0


def extract_narrative(stripped: str, *, cap: int = NARRATIVE_CAP) -> dict:
    """Locate and return the narrative slice from already-stripped filing text.

    Returns {narrative_text, narrative_section, char_len, alpha_ratio, http_count}.
    """
    section, pos = "fallback", None
    for name, rx in _ANCHORS:
        p = _best_anchor_pos(stripped, rx)
        # require the chosen anchor to actually sit in front of prose, not be a lone TOC hit
        if p is not None and _alpha_ratio(stripped[p:p + 2000]) >= 0.68:
            section, pos = name, p
            break
    if pos is None:
        section, pos = "fallback", _fallback_prose_start(stripped)

    narrative = stripped[pos:pos + cap].strip()
    return {
        "narrative_text": narrative,
        "narrative_section": section,
        "char_len": len(narrative),
        "alpha_ratio": round(_alpha_ratio(narrative), 3),
        "http_count": narrative.count("http"),
    }


def sanity_ok(rec: dict, *, min_chars: int = 1500, min_alpha: float = 0.65,
              max_http: int = 5) -> tuple[bool, list]:
    """Content sanity: narrative must look like prose, not URL/taxonomy soup."""
    problems = []
    if rec["char_len"] < min_chars:
        problems.append(f"too short ({rec['char_len']} < {min_chars})")
    if rec["alpha_ratio"] < min_alpha:
        problems.append(f"low alpha_ratio ({rec['alpha_ratio']} < {min_alpha})")
    if rec["http_count"] > max_http:
        problems.append(f"too many residual URLs ({rec['http_count']} > {max_http})")
    return (not problems), problems


# --------------------------------------------------------------------------
# Orchestration: read-only events_raw -> fetch -> extract -> upsert swarm_inputs
# --------------------------------------------------------------------------
def _lookup_filing(accession: str, dsn: str) -> Optional[dict]:
    cn = psycopg2.connect(dsn)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT source_type, source_url FROM public.events_raw "
                        "WHERE accession_number = %s LIMIT 1", (accession,))
            row = cur.fetchone()
    finally:
        cn.close()
    return {"source_type": row[0], "source_url": row[1]} if row else None


def extract_and_store(accession: str, *, dsn: str = DEFAULT_DSN, persist: bool = True) -> dict:
    """Full path for one filing. Returns the swarm_inputs record (with narrative_text)."""
    meta = _lookup_filing(accession, dsn)
    if not meta or not meta["source_url"]:
        raise RuntimeError(f"no source_url for accession={accession!r}")
    stripped = strip_filing(fetch_primary(meta["source_url"]))
    rec = extract_narrative(stripped)
    rec.update({"accession_number": accession, "source_type": meta["source_type"],
                "source_url": meta["source_url"], "full_doc_len": len(stripped)})
    if persist:
        _persist(rec, dsn)
    return rec


def _persist(rec: dict, dsn: str) -> None:
    cn = psycopg2.connect(dsn)
    try:
        with cn, cn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO yuclaw_v5.swarm_inputs
                    (accession_number, source_type, source_url, narrative_text,
                     narrative_section, char_len, alpha_ratio, http_count, full_doc_len)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (accession_number) DO UPDATE SET
                    source_type=EXCLUDED.source_type, source_url=EXCLUDED.source_url,
                    narrative_text=EXCLUDED.narrative_text,
                    narrative_section=EXCLUDED.narrative_section, char_len=EXCLUDED.char_len,
                    alpha_ratio=EXCLUDED.alpha_ratio, http_count=EXCLUDED.http_count,
                    full_doc_len=EXCLUDED.full_doc_len, extracted_at=now()
                """,
                (rec["accession_number"], rec["source_type"], rec["source_url"],
                 rec["narrative_text"], rec["narrative_section"], rec["char_len"],
                 rec["alpha_ratio"], rec["http_count"], rec["full_doc_len"]))
    finally:
        cn.close()


if __name__ == "__main__":
    import sys
    acc = sys.argv[1] if len(sys.argv) > 1 else "0000097745-26-000018"
    r = extract_and_store(acc, persist=False)
    ok, probs = sanity_ok(r)
    print(f"{acc}  section={r['narrative_section']}  chars={r['char_len']}  "
          f"alpha={r['alpha_ratio']}  http={r['http_count']}  full_doc={r['full_doc_len']:,}")
    print(f"sanity: {'OK' if ok else 'FAIL ' + str(probs)}")
    print("--- narrative head ---")
    print(r["narrative_text"][:700])
