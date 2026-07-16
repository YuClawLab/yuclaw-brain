"""
EDGAR live poller v2 — per-company SEC submissions API (Approach A).

Replaces the broken firehose poller (edgar_poll.py, which polled the global
`getcurrent` atom feed and matched ~0 of our 64-CIK universe). Instead this
sweeps each universe CIK's own submissions index, filters to a bounded recent
window, dedups on the canonical accession number, and inserts new filings into
events_raw with extraction_status='pending' so the live (GPU-backed)
event_worker picks them up automatically.

Design doc: docs/edgar_live_poller_design.md (Approach A).

Key choices (Order: EDGAR poller fix, 2026-05-30):
  - Endpoint     : https://data.sec.gov/submissions/CIK{cik}.json (per company)
  - Rate         : 0.15s sleep between requests (~6.6 req/s, < SEC's 10/s cap)
  - Interval     : 5 min (64 req/sweep ≈ 0.2 req/s avg — trivial load)
  - Window       : 7-day filingDate lookback per sweep; accession dedup drops
                   everything already seen (covers multi-hour outages w/o gaps)
  - Dedup        : events_raw.accession_number UNIQUE (canonical, URL-shape-
                   independent). Existence-checked BEFORE doc fetch to avoid
                   re-fetching known filings; ON CONFLICT DO NOTHING as final guard
  - User-Agent   : real monitored contact (SEC compliance), env-overridable
  - 429/Retry-After + 403 handled explicitly
  - Form 4      : (2026-07-16) filings for the covered set (US-domestic scoring
                  equities + 8 Canada evidence-tier names) are picked out of the
                  same submissions JSON and parsed DETERMINISTICALLY on arrival
                  (v3/sources/form4_parser.py — no GPU, never the LLM worker),
                  available_as_of = ingestion time, accession-deduped via an
                  events_raw ledger row with extraction_status='done'.

CLI:
    python3 -m v3.sources.edgar_poll_v2 --once            # one sweep, all 64 CIKs
    python3 -m v3.sources.edgar_poll_v2 --once --dry-run --tickers AAPL,NVDA,AMD,MSFT,AMZN
    python3 -m v3.sources.edgar_poll_v2                   # loop, 5-min interval
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, date, timedelta, timezone

import httpx
import psycopg2

from v3.sources.edgar_poll import _load_universe, _cik_lookup, DB_DSN
from v3.sources.edgar_backfill import (
    SUBMISSIONS_URL,
    FORM_TYPES,
    SEC_SLEEP_SECONDS,
    RAW_TEXT_CAP,
    _filter_filings,
    _archive_url,
    _strip_html,
)
# Form 4 is deliberately NOT in FORM_TYPES (never routed to the LLM worker).
# The live sweep handles it via the deterministic XML parser below — same
# submissions JSON, no extra submissions requests (order of 2026-07-16).
from v3.sources.form4_parser import (
    _archive_dir as _form4_archive_dir,
    _filter_form4_filings,
    form4_covered_universe,
    parse_filing as _parse_form4_filing,
)

# SEC requires a real, monitored contact in the User-Agent (NOT @example.com).
# Env-overridable so it's not hard-coded; default is the configured contact.
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "YuClawLab vzhang2188@gmail.com")

LOOKBACK_DAYS = 7
POLL_INTERVAL_SECONDS = 300  # 5 minutes
FETCH_TIMEOUT = 30.0
MAX_RETRIES = 5


def _fetch_sec(url: str) -> httpx.Response:
    """GET an SEC URL with gzip + real UA, honoring 429/Retry-After and flagging 403.

    - 429 → sleep Retry-After (or exponential backoff) and retry.
    - 403 → raise loudly (User-Agent / identification problem, not transient).
    - transient network errors → exponential backoff retry.
    Sleeps SEC_SLEEP_SECONDS after a successful response (rate courtesy).
    """
    headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip"}
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = httpx.get(url, headers=headers, timeout=FETCH_TIMEOUT)
        except httpx.HTTPError as e:
            last_exc = e
            time.sleep(min(2 ** attempt, 8))
            continue

        if r.status_code == 429:
            ra = r.headers.get("Retry-After", "")
            wait = float(ra) if ra.isdigit() else min(2 ** attempt, 30)
            print(f"[edgar_poll_v2] 429 rate-limited (Retry-After={ra or 'n/a'}), "
                  f"backing off {wait}s", file=sys.stderr, flush=True)
            time.sleep(wait)
            continue

        if r.status_code == 403:
            raise RuntimeError(
                f"403 Forbidden from SEC for {url} — User-Agent likely rejected "
                f"(current: {SEC_USER_AGENT!r}). SEC requires a real contact."
            )

        r.raise_for_status()
        time.sleep(SEC_SLEEP_SECONDS)
        return r

    raise last_exc or RuntimeError(f"SEC fetch failed after {MAX_RETRIES} retries: {url}")


def _fetch_filing_text(url: str, form: str, description: str, filing_date) -> tuple[str, bool]:
    """Fetch primary doc, strip to plain text (capped). Returns (text, used_stub).

    On fetch failure, returns a metadata stub so the row still gets inserted
    (worker will typically return no_event). Mirrors edgar_backfill behavior.
    """
    try:
        r = _fetch_sec(url)
        text = _strip_html(r.text)[:RAW_TEXT_CAP]
        if text:
            return text, False
    except Exception as e:
        print(f"[edgar_poll_v2] doc fetch failed for {url}: {type(e).__name__}: {str(e)[:80]}",
              file=sys.stderr, flush=True)
    return f"{form} filing on {filing_date}. {description}".strip(), True


def _accession_exists(cur, accession: str) -> bool:
    cur.execute("SELECT 1 FROM events_raw WHERE accession_number = %s LIMIT 1", (accession,))
    return cur.fetchone() is not None


def _ledger_form4(cur, ticker: str, cik: str, filing: dict, parse_stats: dict) -> None:
    """Record a processed Form-4 accession in events_raw (extraction_status
    'done' — the LLM worker only reads 'pending', so the 70B path never sees
    it). This is the sweep's dedup ledger: without it, a Form 4 with zero
    qualifying trades leaves no row anywhere and would be re-fetched every
    sweep for the whole lookback window."""
    accession = filing["accession"]
    raw_text = (f"Form 4 filing on {filing['filing_date']}. Parsed deterministically "
                f"(v3/sources/form4_parser.py): {parse_stats['transactions']} transaction(s), "
                f"{parse_stats['kept']} qualifying trade(s), "
                f"{parse_stats['inserted']} event(s) inserted.")
    cur.execute(
        """INSERT INTO events_raw
               (ticker, source_type, source_url, raw_text,
                source_publish_time, accession_number, extraction_status)
           VALUES (%s, '4', %s, %s, %s, %s, 'done')
           ON CONFLICT DO NOTHING""",
        (ticker, _form4_archive_dir(cik, accession), raw_text,
         filing["publish_time"], accession),
    )


def poll_once(tickers: list[str], cik_map: dict, dry_run: bool,
              lookback_days: int = LOOKBACK_DAYS,
              form4_tickers: frozenset | set = frozenset()) -> dict:
    """One sweep over `tickers`. Returns stats dict.

    For tickers in `form4_tickers` (US-domestic scoring equities + the 8
    Canada evidence-tier names with a Form-4 substrate), the same submissions
    JSON is additionally filtered for Form 4 filings, which are parsed
    deterministically on arrival (no GPU) with available_as_of = ingestion
    time. Dedup is by canonical accession via the events_raw ledger.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    stats = {
        "tickers": len(tickers), "window": f"{start_date}→{end_date}",
        "candidates": 0, "inserted": 0, "skipped_dedup": 0,
        "doc_fetch_stub": 0, "ticker_errors": 0,
        "form4_candidates": 0, "form4_new": 0, "form4_dedup": 0,
        "form4_events": 0, "form4_fetch_failed": 0,
    }

    conn = None
    cur = None
    if not dry_run:
        conn = psycopg2.connect(DB_DSN)
        conn.autocommit = True
        cur = conn.cursor()

    try:
        for ticker in tickers:
            cik = cik_map.get(ticker)
            if not cik:
                continue
            try:
                r = _fetch_sec(SUBMISSIONS_URL.format(cik=cik))
                submissions = r.json()
            except Exception as e:
                stats["ticker_errors"] += 1
                print(f"[edgar_poll_v2] {ticker} CIK={cik}: submissions fetch failed: "
                      f"{type(e).__name__}: {str(e)[:100]}", file=sys.stderr, flush=True)
                continue

            filings = _filter_filings(submissions, start_date, end_date)
            for f in filings:
                stats["candidates"] += 1
                accession = f["accession"]
                src_url = _archive_url(cik, accession, f["primary"])

                if dry_run:
                    print(f"[dry-run] {ticker:6s} {f['form']:5s} {f['filing_date']} "
                          f"{accession}  {src_url}", flush=True)
                    continue

                # Dedup BEFORE doc fetch — avoids re-fetching the ~280 known filings.
                if _accession_exists(cur, accession):
                    stats["skipped_dedup"] += 1
                    continue

                raw_text, used_stub = _fetch_filing_text(
                    src_url, f["form"], f["description"], f["filing_date"]
                )
                if used_stub:
                    stats["doc_fetch_stub"] += 1

                cur.execute(
                    """INSERT INTO events_raw
                           (ticker, source_type, source_url, raw_text,
                            source_publish_time, accession_number)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       -- events_raw has TWO unique constraints (accession_number
                       -- AND source_url). Use untargeted ON CONFLICT so a match on
                       -- EITHER is a clean no-op, not a UniqueViolation that aborts
                       -- the sweep (e.g. backfill rows whose accession differs/NULL).
                       ON CONFLICT DO NOTHING
                       RETURNING raw_id""",
                    (ticker, f["form"], src_url, raw_text, f["publish_time"], accession),
                )
                if cur.fetchone():
                    stats["inserted"] += 1
                    print(f"[edgar_poll_v2] NEW {ticker} {f['form']} {f['filing_date']} "
                          f"{accession} → events_raw (pending)", flush=True)
                else:
                    # Lost an insert race (another sweep) — treat as dedup.
                    stats["skipped_dedup"] += 1

            # ── Form 4 (deterministic, no GPU) — same submissions JSON ──
            if ticker not in form4_tickers:
                continue
            for f4 in _filter_form4_filings(submissions, start_date, end_date):
                stats["form4_candidates"] += 1
                if dry_run:
                    print(f"[dry-run] {ticker:6s} 4     {f4['filing_date']} "
                          f"{f4['accession']}", flush=True)
                    continue
                if _accession_exists(cur, f4["accession"]):
                    stats["form4_dedup"] += 1
                    continue
                s4 = _parse_form4_filing(cik, ticker, f4, False, conn,
                                         as_of_ingestion=True)
                if s4["fetch_failed"]:
                    # transient EDGAR failure — no ledger row, retry next sweep
                    stats["form4_fetch_failed"] += 1
                    continue
                stats["form4_new"] += 1
                stats["form4_events"] += s4["inserted"]
                _ledger_form4(cur, ticker, cik, f4, s4)
                if s4["inserted"]:
                    print(f"[edgar_poll_v2] NEW {ticker} Form4 {f4['filing_date']} "
                          f"{f4['accession']} → {s4['inserted']} insider event(s) "
                          f"(deterministic, as_of=ingestion)", flush=True)
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="EDGAR live poller v2 (submissions API)")
    p.add_argument("--once", action="store_true", help="single sweep then exit")
    p.add_argument("--dry-run", action="store_true", help="no DB writes; print candidates")
    p.add_argument("--tickers", help="comma-separated subset (default: full universe)")
    p.add_argument("--interval", type=int, default=POLL_INTERVAL_SECONDS,
                   help="seconds between sweeps in loop mode")
    p.add_argument("--lookback", type=int, default=LOOKBACK_DAYS,
                   help="filingDate lookback window (days)")
    args = p.parse_args(argv)

    # Evidence-tier CIKs come from universe metadata, not the SEC ticker map —
    # OTC proxy lines (WCPRF class) are missing from company_tickers.json.
    from v3.universe_tiers import evidence_cik_map
    cik_map = {**_cik_lookup(), **evidence_cik_map()}
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        missing = [t for t in tickers if t not in cik_map]
        if missing:
            print(f"[edgar_poll_v2] WARN: no CIK for {missing} — skipping", file=sys.stderr)
        tickers = [t for t in tickers if t in cik_map]
    else:
        universe = _load_universe()
        tickers = sorted([t for t in universe if t in cik_map])

    # Live Form-4 coverage (2026-07-16): US-domestic scoring equities + the 8
    # Canada evidence-tier names with a Form-4 substrate. Always a subset of
    # the sweep — Form 4s are picked out of the same submissions JSON.
    form4_tickers = frozenset(form4_covered_universe()[0]) & set(tickers)

    print(f"[edgar_poll_v2] config: tickers={len(tickers)} form4_tickers={len(form4_tickers)} "
          f"interval={args.interval}s "
          f"lookback={args.lookback}d dry_run={args.dry_run} UA={SEC_USER_AGENT!r}", flush=True)

    def _sweep() -> dict:
        t0 = time.time()
        s = poll_once(tickers, cik_map, args.dry_run, args.lookback,
                      form4_tickers=form4_tickers)
        s["latency_s"] = round(time.time() - t0, 1)
        print(f"[edgar_poll_v2] sweep: {s}", flush=True)
        return s

    if args.once or args.dry_run:
        _sweep()
        return 0

    while True:
        try:
            _sweep()
        except Exception as e:
            print(f"[edgar_poll_v2] sweep error: {type(e).__name__}: {e}",
                  file=sys.stderr, flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
