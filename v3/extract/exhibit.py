"""YUCLAW v5 Layer 1 Day 5B — earnings/guidance Exhibit 99.x text extraction.

Day-5A finding: earnings/guidance 8-Ks store only the cover ("see Exhibit 99.1") in
events_raw.raw_text, so EarningsQuality + SentimentDrift ground 0.0 — the results/guidance prose
lives in the un-captured exhibit. Same root-cause family as the Day-3 XBRL finding.

This module re-fetches the EXHIBIT from the filing's EDGAR directory (the index.json lists every
document, including ex*99*.htm) and extracts its prose, REUSING narrative.py's fetch+strip+sanity
(declared UA, polite delay, disk cache) — not a fork. Output is additive to
yuclaw_v5.swarm_inputs (narrative_section='exhibit99'); public.* is read-only.
"""
# LIVE-INGESTION COPY (2026-07-06) of yuclaw/v5/extract/exhibit.py from the v5-layer1
# worktree (verbatim except this header and the intra-package import). DUAL-COPY
# RULE (same discipline as reclassify): any change to the v5 module MUST be applied
# here identically, and vice versa.


from __future__ import annotations

import html as _html
import re
from typing import Optional

import httpx
import psycopg2

from v3.extract.narrative import (
    DEFAULT_DSN, USER_AGENT, SEC_SLEEP_SECONDS, NARRATIVE_CAP,
    extract_narrative, fetch_primary, strip_filing, _alpha_ratio, _WS_RE, _ZWSP_RE,
)
import time

# Exhibit 99.x is the press release / results body. Prefer .htm over .txt; skip images.
_EX99_RE = re.compile(r"(ex|exhibit)[-_]?99", re.I)
# 6-K variant (TC Energy class): quarterly MD&A/financials furnished as EX-13.x instead
# of EX-99.x. Second-preference pool — an ingester cannot assume EX-99-only for 6-Ks.
_EX13_RE = re.compile(r"(ex|exhibit)[-_]?13", re.I)


def _index_url(source_url: str) -> str:
    return source_url.rsplit("/", 1)[0] + "/index.json"


_R_FILE_RE = re.compile(r"^R\d+\.htm", re.I)            # XBRL viewer fragments
_INDEX_RE = re.compile(r"index", re.I)

# -index.htm document-table row: <td>seq</td><td>desc</td><td><a href="file">..</a></td><td>TYPE</td>
_INDEX_HTM_ROW_RE = re.compile(
    r'href="[^"]*/([^"/]+\.html?)"[^>]*>.*?</a>\s*</td>\s*<td[^>]*>\s*(EX-[\d.]+|6-K|8-K|40-F|10-K|10-Q)',
    re.I | re.S)


def _exhibit_types_from_index_htm(base: str, accession_nodash: str, *,
                                  timeout: float = 30.0) -> dict:
    """Map document filename -> declared exhibit TYPE (EX-99.1, EX-13.2, ...) from the
    filing's -index.htm table. Needed for filers (TC Energy class) whose exhibit
    FILENAMES carry no ex99/ex13 marker — the type column is authoritative."""
    acc = f"{accession_nodash[:10]}-{accession_nodash[10:12]}-{accession_nodash[12:]}"
    r = httpx.get(f"{base}{acc}-index.htm", headers={"User-Agent": USER_AGENT}, timeout=timeout)
    time.sleep(SEC_SLEEP_SECONDS)
    r.raise_for_status()
    return {name.lower(): typ.upper() for name, typ in _INDEX_HTM_ROW_RE.findall(r.text)}


def find_exhibit_url(source_url: str, *, timeout: float = 30.0,
                     prefer: Optional[re.Pattern] = None) -> Optional[str]:
    """List the filing directory (index.json) and return the URL of the results-body exhibit.
    Exhibit naming varies (TSLA: exhibit991.htm; PSX: psx-2026_q1prexrelease.htm), so:
      1. if ``prefer`` is given, an .htm whose name matches it wins first (e.g. an MD&A
         exhibit for 40-F annual filings);
      2. else prefer an explicitly Exhibit-99-named .htm;
      3. else an Exhibit-13-named .htm (6-K variant, TC Energy class);
      4. else the LARGEST .htm that is not the primary/cover doc, an XBRL R-file, or an index.
    Largest-first within each pool. Deterministic; one request."""
    base = source_url.rsplit("/", 1)[0] + "/"
    primary = source_url.rsplit("/", 1)[1].lower()
    r = httpx.get(base + "index.json", headers={"User-Agent": USER_AGENT}, timeout=timeout)
    time.sleep(SEC_SLEEP_SECONDS)
    r.raise_for_status()
    items = r.json().get("directory", {}).get("item", [])

    preferred, ex99, ex13, others = [], [], [], []
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
        if prefer is not None and prefer.search(name):
            preferred.append((size, name))
        elif _EX99_RE.search(name):
            ex99.append((size, name))
        elif _EX13_RE.search(name):
            ex13.append((size, name))
        else:
            others.append((size, name))

    if not (preferred or ex99 or ex13) and others:
        # Filename carries no exhibit marker (TC Energy class: trp-...xnewsrelease.htm is
        # EX-99.1). Fall back to the -index.htm TYPE column and re-pool; on any failure
        # keep the largest-other behavior unchanged.
        try:
            nodash = base.rstrip("/").rsplit("/", 1)[1]
            types = _exhibit_types_from_index_htm(base, nodash)
            re_ex99 = [(sz, nm) for sz, nm in others if types.get(nm.lower(), "").startswith("EX-99")]
            re_ex13 = [(sz, nm) for sz, nm in others if types.get(nm.lower(), "").startswith("EX-13")]
            ex99, ex13 = re_ex99, re_ex13
        except Exception:
            pass

    pool = preferred or ex99 or ex13 or others
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
        # AU class (AngloGold): some foreign filers furnish the substance AS the
        # primary document — the filing dir has no exhibit .htm at all. Only in
        # that no-exhibit case, treat the primary as the prose body; the caller's
        # sanity gate still rejects thin/boilerplate covers, so a true envelope
        # cover can never be false-persisted through this branch.
        ex_url, section_override = source_url, "primary_body"
    else:
        section_override = None
    stripped = strip_filing(fetch_primary(ex_url))            # reuse Day-3 fetch+strip (cached)
    # the exhibit body is prose throughout; take from the first sustained-prose offset
    start = 0
    for i in range(0, max(1, len(stripped) - 1000), 300):
        if _alpha_ratio(stripped[i:i + 1000]) >= 0.72:
            start = i
            break
    narrative = stripped[start:start + cap].strip()
    ex_name = ex_url.rsplit("/", 1)[1]
    section = section_override or (
        "exhibit13" if (_EX13_RE.search(ex_name) and not _EX99_RE.search(ex_name)) else "exhibit99")
    rec = {"accession_number": accession, "source_type": source_type, "source_url": ex_url,
           "narrative_text": narrative, "narrative_section": section,
           "char_len": len(narrative), "alpha_ratio": round(_alpha_ratio(narrative), 3),
           "http_count": narrative.count("http"), "full_doc_len": len(stripped)}
    if persist:
        _persist_exhibit(rec, dsn)
    return rec


# 6-K/40-F cover pages carry a one-line exhibit index ("99.1 News release dated ...").
# That line is a TYPING HINT for the classifier — context prepended to the exhibit body,
# never a replacement for it.
_EXHIBIT_INDEX_RE = re.compile(r"\b(?:EX[-_ ]?|Exhibit\s+)?(99\.\d{1,2}|13\.\d{1,2})\b[\s:–—-]*")


def cover_exhibit_hint(cover_text: str, max_len: int = 300) -> str:
    """Extract the exhibit-index one-liners from a 6-K/40-F cover page (already-stripped
    text, e.g. events_raw.raw_text). Returns a single bounded hint line, or '' when the
    cover carries no recognizable exhibit index."""
    # events_raw cover text is tag-stripped but NOT entity-unescaped (poller's
    # _strip_html); unescape + drop zero-width chars so Suncor-class covers don't
    # leak "&#8203;" soup into the classifier hint.
    t = _html.unescape(cover_text or "")
    t = _ZWSP_RE.sub("", t)
    t = _WS_RE.sub(" ", t)
    parts = _EXHIBIT_INDEX_RE.split(t)
    entries = []
    # split() yields [pre, num1, desc1, num2, desc2, ...]
    for i in range(1, len(parts) - 1, 2):
        desc = parts[i + 1].strip()[:120].strip()
        if desc:
            entries.append(f"{parts[i]} {desc}")
    if not entries:
        return ""
    return ("COVER EXHIBIT INDEX: " + "; ".join(entries))[:max_len]


# A real annual-report primary (CNQ class: full iXBRL report in the 40-F document itself)
# strips to hundreds of KB; a cover envelope (SU class) strips to <20K yet still ANCHORS
# on "Management's Discussion and Analysis" because the exhibit index cites it — the
# cover-only false-success trap. Size-gate the primary path before trusting its anchor.
_PRIMARY_ANNUAL_MIN_CHARS = 50_000


def extract_exhibit_narrative(accession: str, *, dsn: str = DEFAULT_DSN, persist: bool = True,
                              cap: int = NARRATIVE_CAP) -> dict:
    """40-F-class annual filings, two structural variants:
      1. CNQ class — the primary document IS the annual report (large iXBRL); the
         10-K-style MD&A anchor search applies to it directly.
      2. SU class — the primary is a thin cover; MD&A/AIF prose is furnished as
         EX-99.x exhibits. Locate the exhibit (preferring an MD&A-named one) and run
         the anchor search inside it.
    The primary path is only trusted when the stripped primary is annual-report-sized
    (see _PRIMARY_ANNUAL_MIN_CHARS) AND the anchor hit a named section — a small cover
    that quotes 'Management's Discussion and Analysis' in its exhibit index must fall
    through to the exhibit path, never be persisted as prose."""
    from v3.extract.narrative import sanity_ok
    cn = psycopg2.connect(dsn); cn.set_session(readonly=True)
    with cn.cursor() as cur:
        cur.execute("SELECT source_type, source_url FROM public.events_raw "
                    "WHERE accession_number=%s LIMIT 1", (accession,))
        row = cur.fetchone()
    cn.close()
    if not row or not row[1]:
        raise RuntimeError(f"no source_url for {accession!r}")
    source_type, source_url = row

    primary_stripped = strip_filing(fetch_primary(source_url))
    if len(primary_stripped) >= _PRIMARY_ANNUAL_MIN_CHARS:
        nrec = extract_narrative(primary_stripped, cap=cap)
        if nrec["narrative_section"] != "fallback" and sanity_ok(nrec)[0]:
            rec = {"accession_number": accession, "source_type": source_type,
                   "source_url": source_url, "narrative_text": nrec["narrative_text"],
                   "narrative_section": nrec["narrative_section"], "char_len": nrec["char_len"],
                   "alpha_ratio": nrec["alpha_ratio"], "http_count": nrec["http_count"],
                   "full_doc_len": len(primary_stripped)}
            if persist:
                _persist_exhibit(rec, dsn)
            return rec

    ex_url = find_exhibit_url(source_url, prefer=re.compile(r"mda|manag|discussion", re.I))
    if not ex_url:
        raise RuntimeError(f"no exhibit found in filing dir for {accession!r}")
    stripped = strip_filing(fetch_primary(ex_url))
    nrec = extract_narrative(stripped, cap=cap)
    rec = {"accession_number": accession, "source_type": source_type, "source_url": ex_url,
           "narrative_text": nrec["narrative_text"], "narrative_section": nrec["narrative_section"],
           "char_len": nrec["char_len"], "alpha_ratio": nrec["alpha_ratio"],
           "http_count": nrec["http_count"], "full_doc_len": len(stripped)}
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
    from v3.extract.narrative import sanity_ok
    acc = sys.argv[1] if len(sys.argv) > 1 else "0001628280-26-026551"
    rec = extract_exhibit(acc, persist=False)
    ok, probs = sanity_ok(rec)
    print(f"{acc}  section={rec['narrative_section']}  chars={rec['char_len']}  "
          f"alpha={rec['alpha_ratio']}  http={rec['http_count']}  full={rec['full_doc_len']:,}  "
          f"sanity={'OK' if ok else 'FAIL '+str(probs)}")
    print("url:", rec["source_url"])
    print("--- head ---"); print(rec["narrative_text"][:600])
