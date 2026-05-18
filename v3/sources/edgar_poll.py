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
CIK_CACHE_PATH = Path("/tmp/sec_company_tickers.json")
CIK_REFRESH_SECONDS = 86400  # refresh once per day
EDGAR_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
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
    if (CIK_CACHE_PATH.exists()
            and time.time() - CIK_CACHE_PATH.stat().st_mtime < CIK_REFRESH_SECONDS):
        return
    r = _fetch(COMPANY_TICKERS_URL)
    CIK_CACHE_PATH.write_text(r.text)


def _cik_lookup() -> dict[str, str]:
    """Map ticker -> 10-digit zero-padded CIK string."""
    _refresh_cik_cache()
    d = json.loads(CIK_CACHE_PATH.read_text())
    out = {}
    for row in d.values():
        ticker = row.get("ticker", "").upper()
        cik = row.get("cik_str")
        if ticker and cik is not None:
            out[ticker] = f"{int(cik):010d}"
    return out


def _cik_to_ticker_for_universe(universe: set[str]) -> dict[str, str]:
    """Inverse map, filtered to tickers in our universe."""
    full = _cik_lookup()
    return {cik: t for t, cik in full.items() if t in universe}


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
        "cik_map_size": len(cik_map),
        "feed_entries": len(entries),
        "matched_universe": 0,
        "inserted": 0,
        "skipped_dedup": 0,
    }

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for entry in entries:
                cik = _extract_cik(entry)
                if not cik or cik not in cik_map:
                    continue
                ticker = cik_map[cik]
                stats["matched_universe"] += 1

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "") or entry.get("id", "")
                raw_text = f"{title}\n\n{summary}".strip() or title
                publish_time = _parse_publish_time(entry)

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
