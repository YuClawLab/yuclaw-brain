"""
SEC EDGAR RSS poller.

Pulls the recent-filings atom feed every poll cycle, maps each entry to a
ticker via CIK reverse lookup, and inserts new (source_url-deduped) rows into
events_raw for downstream extraction.

CLI:
    python3 -m v3.sources.edgar_poll --once       # single poll, then exit
    python3 -m v3.sources.edgar_poll              # loop, 60s sleep
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import httpx
import psycopg2
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "universe.json"
# Local cache of the merged ticker→CIK map (operating companies + mutual funds/ETFs).
CIK_CACHE_PATH = Path(__file__).resolve().parent / "cik_cache.json"
CIK_REFRESH_SECONDS = 86400  # refresh once per day
EDGAR_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"
# Operating companies (form 10-K filers)
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# Mutual funds + ETFs (different SEC index, e.g. XLK / SPY / TLT)
COMPANY_TICKERS_MF_URL = "https://www.sec.gov/files/company_tickers_mf.json"
# SEC requires a contact User-Agent on programmatic access:
# https://www.sec.gov/os/accessing-edgar-data
USER_AGENT = "YuClawLab v3.0 yuclawlab@example.com"
DB_DSN = "dbname=yuclaw_events"


def _load_universe() -> set[str]:
    u = json.loads(UNIVERSE_PATH.read_text())
    return set(u["equities"] + u["sector_etfs"] + u["broad_etfs"] + u["macro"])


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.HTTPStatusError)),
)
def _fetch(url: str) -> httpx.Response:
    r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}, timeout=30.0)
    r.raise_for_status()
    return r


def _refresh_cik_cache() -> None:
    """Fetch both SEC ticker indexes (operating companies + mutual funds/ETFs)
    and merge them into a single local cache as {ticker: cik_10digit}.

    SEC publishes ticker→CIK in two separate JSONs:
      * company_tickers.json     — operating companies (10-K filers)
      * company_tickers_mf.json  — mutual funds & ETFs (different schema)
    Without the MF file, sector/broad/macro ETFs like XLK/SPY/TLT silently
    fail to map and their filings are skipped.
    """
    if (CIK_CACHE_PATH.exists()
            and time.time() - CIK_CACHE_PATH.stat().st_mtime < CIK_REFRESH_SECONDS):
        return

    merged: dict[str, str] = {}

    # 1) operating companies — dict-of-rows {idx: {cik_str, ticker, title}}
    r1 = _fetch(COMPANY_TICKERS_URL)
    for row in json.loads(r1.text).values():
        t = (row.get("ticker") or "").upper()
        cik = row.get("cik_str")
        if t and cik is not None:
            merged[t] = f"{int(cik):010d}"

    # 2) mutual funds + ETFs — {"fields": [cik, seriesId, classId, symbol], "data": [...]}
    # Note: the same symbol can recur across multiple share classes; we take the
    # first occurrence (typically the highest-volume class). The CIK is the
    # fund family (not the series/class), which is what EDGAR archives under.
    r2 = _fetch(COMPANY_TICKERS_MF_URL)
    mf = json.loads(r2.text)
    fields = mf.get("fields") or []
    try:
        cik_idx = fields.index("cik")
        sym_idx = fields.index("symbol")
    except ValueError:
        cik_idx, sym_idx = 0, 3  # fall back to expected positions
    for row in mf.get("data", []):
        try:
            t = (row[sym_idx] or "").upper()
            cik = row[cik_idx]
        except (IndexError, TypeError):
            continue
        if t and cik is not None and t not in merged:
            merged[t] = f"{int(cik):010d}"

    CIK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CIK_CACHE_PATH.write_text(json.dumps(merged, sort_keys=True))


def _cik_lookup() -> dict[str, str]:
    """Map ticker -> 10-digit zero-padded CIK string (merged company + MF)."""
    _refresh_cik_cache()
    return json.loads(CIK_CACHE_PATH.read_text())


def _cik_to_ticker_for_universe(universe: set[str]) -> dict[str, list[str]]:
    """Inverse map cik → [tickers], filtered to tickers in our universe.

    SEC has real CIK collisions for ETF trusts that hold multiple funds under
    one registered entity. Examples in our universe:
      CIK 0001064641 (Select Sector SPDR Trust) → XLK, XLF, XLY, XLP, XLU, XLI,
                                                   XLB, XLE, XLV, XLC, XLRE (11 tickers)
      CIK 0001100663 (iShares Trust)            → IBB, TLT, IWM, FXI, IEF
      CIK 0001064642 (SPDR Series Trust)        → XBI, KRE

    Filings from these trusts typically address the entire trust (e.g.,
    Form N-CSR, NT-NSAR) and don't disambiguate which fund. For Day 2 we
    return the full ticker list per CIK and let the caller decide
    (poll_once picks the first ticker alphabetically — see TODO).
    Day 3 work: title-based disambiguation.
    """
    full = _cik_lookup()
    out: dict[str, list[str]] = {}
    for t, cik in full.items():
        if t in universe:
            out.setdefault(cik, []).append(t)
    return out


_CIK_RE = re.compile(r"CIK=(\d+)", re.IGNORECASE)
_PATH_CIK_RE = re.compile(r"/Archives/edgar/data/(\d+)/")


def _extract_cik(entry: dict) -> str | None:
    """Pull a 10-digit CIK out of the atom entry's link/title/id fields."""
    candidates = [entry.get("link", ""), entry.get("id", ""), entry.get("title", "")]
    for c in candidates:
        m = _CIK_RE.search(c) or _PATH_CIK_RE.search(c)
        if m:
            return f"{int(m.group(1)):010d}"
    return None


def _parse_publish_time(entry: dict) -> datetime:
    raw = entry.get("updated") or entry.get("published") or ""
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            pass
    return datetime.now(timezone.utc)


def poll_once() -> dict:
    """Single poll cycle. Returns stats dict."""
    universe = _load_universe()
    cik_map = _cik_to_ticker_for_universe(universe)

    r = _fetch(EDGAR_FEED_URL)
    feed = feedparser.parse(r.text)
    entries = feed.entries or []

    stats = {
        "universe_size": len(universe),
        "unique_ciks": len(cik_map),
        "feed_entries": len(entries),
        "matched_universe": 0,
        "inserted": 0,
        "skipped_dedup": 0,
        "skipped_collision": 0,
    }

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for entry in entries:
                cik = _extract_cik(entry)
                if not cik or cik not in cik_map:
                    continue

                tickers = cik_map[cik]
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "") or entry.get("id", "")
                raw_text = f"{title}\n\n{summary}".strip() or title
                publish_time = _parse_publish_time(entry)

                # Disambiguation for CIK collisions (multi-ETF trusts).
                # Try title/summary string-match first; fall back to first
                # ticker alphabetically. TODO Day 3: proper series-id lookup
                # via sec-api ETF endpoint.
                if len(tickers) == 1:
                    ticker = tickers[0]
                else:
                    text_lc = (title + " " + summary).upper()
                    matches = [t for t in tickers if f" {t} " in f" {text_lc} " or f"({t})" in text_lc]
                    if len(matches) == 1:
                        ticker = matches[0]
                    elif len(matches) > 1:
                        # Multiple universe tickers mentioned — ambiguous, skip
                        stats["skipped_collision"] += 1
                        continue
                    else:
                        # No ticker mentioned — pick first alphabetically (deterministic)
                        ticker = sorted(tickers)[0]

                stats["matched_universe"] += 1

                cur.execute(
                    """INSERT INTO events_raw
                           (ticker, source_type, source_url, raw_text, source_publish_time)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (source_url) DO NOTHING
                       RETURNING raw_id""",
                    (ticker, "edgar", link, raw_text, publish_time),
                )
                if cur.fetchone():
                    stats["inserted"] += 1
                else:
                    stats["skipped_dedup"] += 1
    finally:
        conn.close()

    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SEC EDGAR RSS poller (v3.0)")
    p.add_argument("--once", action="store_true", help="single poll then exit")
    p.add_argument("--sleep", type=int, default=60, help="seconds between polls in loop mode")
    args = p.parse_args(argv)

    if args.once:
        s = poll_once()
        print(f"[edgar_poll] {s}")
        return 0

    while True:
        try:
            s = poll_once()
            print(f"[edgar_poll] {s}", flush=True)
        except Exception as e:
            print(f"[edgar_poll] error: {e}", file=sys.stderr, flush=True)
        time.sleep(args.sleep)


if __name__ == "__main__":
    sys.exit(main())
