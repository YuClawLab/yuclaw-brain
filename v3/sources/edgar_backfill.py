"""
Historical EDGAR backfill — per-ticker iteration via SEC's submissions API.

For each ticker in v3/universe.json that has a CIK, fetches the company's
filing history, filters to relevant form types within a date range, fetches
each primary document (HTML stripped to plain text), and inserts a row into
events_raw for the running extraction worker to consume.

Uses https://data.sec.gov/submissions/CIK{padded}.json (per-ticker filings
list) rather than scraping daily-index files. Resumable via
v3/backfill_state.json.

CLI:
    python3 -m v3.sources.edgar_backfill --start YYYY-MM-DD --end YYYY-MM-DD
    python3 -m v3.sources.edgar_backfill --start ... --end ... --dry-run
    python3 -m v3.sources.edgar_backfill --start ... --end ... --ticker AAPL
    python3 -m v3.sources.edgar_backfill --start ... --end ... --resume

SEC rate limit (10 req/sec) honored via 0.15s sleep between requests.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, date, timezone
from pathlib import Path

import httpx
import psycopg2
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from v3.sources.edgar_poll import _load_universe, _cik_lookup, USER_AGENT, DB_DSN

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
STATE_PATH = Path(__file__).resolve().parent.parent / "backfill_state.json"

# Form types we ingest into events_raw for LLM extraction. Form 4 (insider
# transactions) is intentionally OMITTED — it's structured XML, deterministic,
# and dominates filing volume (~70% of universe traffic). A dedicated parser
# in v3/sources/form4_parser.py (Day 3) handles Form 4 separately at <1ms/row
# instead of ~120s LLM extraction. Decision recorded in CHANGELOG; reinstate
# here if Day 3 parser slips and we still want Form 4 coverage via LLM fallback.
FORM_TYPES = {"8-K", "10-Q", "10-K", "6-K"}

# SEC published cap is 10 req/sec. 0.15s sleep → ~6.6 req/sec, comfortable margin.
SEC_SLEEP_SECONDS = 0.15

# Cap on raw_text per filing — much more than the worker's 4000-char truncation,
# with headroom for the worker to see "Item N. ..." headers + first paragraphs.
RAW_TEXT_CAP = 8000

# Tag-stripping regexes
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.HTTPStatusError)),
)
def _fetch(url: str) -> httpx.Response:
    r = httpx.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
        timeout=30.0,
    )
    r.raise_for_status()
    time.sleep(SEC_SLEEP_SECONDS)
    return r


def _strip_html(html: str) -> str:
    """Strip HTML/XML tags and collapse whitespace. Cheap and dependency-free."""
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _get_universe_tickers() -> list[str]:
    """Active universe tickers (post-deferred filter) that also have a CIK."""
    universe = _load_universe()
    cik_map = _cik_lookup()
    return sorted([t for t in universe if t in cik_map])


def _filter_filings(submissions: dict, start_date: date, end_date: date) -> list[dict]:
    """Extract filings within [start_date, end_date] matching FORM_TYPES."""
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        return []

    n = len(recent.get("accessionNumber", []))
    forms = recent.get("form", []) + [""] * (n - len(recent.get("form", [])))
    fdates = recent.get("filingDate", []) + [""] * (n - len(recent.get("filingDate", [])))
    accs = recent.get("accessionNumber", [])
    primaries = recent.get("primaryDocument", []) + [""] * (n - len(recent.get("primaryDocument", [])))
    descs = recent.get("primaryDocDescription", []) + [""] * (n - len(recent.get("primaryDocDescription", [])))
    accept_dts = recent.get("acceptanceDateTime", []) + [None] * (n - len(recent.get("acceptanceDateTime", [])))

    out = []
    for i in range(n):
        form = forms[i]
        if form not in FORM_TYPES:
            continue
        try:
            filing_date = datetime.strptime(fdates[i], "%Y-%m-%d").date()
        except Exception:
            continue
        if not (start_date <= filing_date <= end_date):
            continue

        accept_dt_str = accept_dts[i] or (fdates[i] + "T00:00:00Z")
        try:
            publish_time = datetime.fromisoformat(accept_dt_str.replace("Z", "+00:00"))
        except Exception:
            publish_time = datetime(filing_date.year, filing_date.month, filing_date.day, tzinfo=timezone.utc)

        out.append({
            "form": form,
            "filing_date": filing_date,
            "publish_time": publish_time,
            "accession": accs[i],
            "primary": primaries[i],
            "description": descs[i] or "",
        })
    return out


def _archive_url(cik: str, accession: str, primary: str) -> str:
    """EDGAR archive URL for the primary document of a filing."""
    cik_int = int(cik)
    accession_clean = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}/{primary}"


def _fetch_filing_text(url: str, form: str, description: str, filing_date) -> str:
    """Fetch primary doc + strip HTML to plain text. Returns capped string.

    On fetch failure, falls back to a metadata-only stub so the row still gets
    inserted (the extraction worker will mostly return no_event on these).
    """
    try:
        r = _fetch(url)
        text = _strip_html(r.text)[:RAW_TEXT_CAP]
        if text:
            return text
    except Exception as e:
        # Log error but don't fail — fall through to metadata stub
        print(f"[backfill] doc fetch failed for {url}: {type(e).__name__}: {str(e)[:80]}",
              file=sys.stderr, flush=True)
    # Metadata stub fallback
    return f"{form} filing on {filing_date}. {description}".strip()


def backfill_ticker(
    ticker: str, cik: str,
    start_date: date, end_date: date,
    dry_run: bool,
) -> dict:
    """Backfill one ticker. Returns stats."""
    stats = {
        "ticker": ticker, "filings_seen": 0, "in_range": 0,
        "inserted": 0, "skipped_dedup": 0, "doc_fetch_failed": 0,
    }

    # 1. Fetch the per-ticker submissions index
    try:
        r = _fetch(SUBMISSIONS_URL.format(cik=cik))
        submissions = r.json()
    except Exception as e:
        print(f"[backfill] {ticker} CIK={cik}: submissions fetch failed: {e}",
              file=sys.stderr, flush=True)
        return stats

    recent = submissions.get("filings", {}).get("recent", {})
    stats["filings_seen"] = len(recent.get("accessionNumber", []))

    # 2. Filter to our window + form types
    filings = _filter_filings(submissions, start_date, end_date)
    stats["in_range"] = len(filings)

    if dry_run or not filings:
        return stats

    # 3. Fetch each primary doc + insert
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for f in filings:
                src_url = _archive_url(cik, f["accession"], f["primary"])
                raw_text = _fetch_filing_text(
                    src_url, f["form"], f["description"], f["filing_date"]
                )
                if raw_text.startswith(f"{f['form']} filing on "):
                    # used the metadata stub due to fetch failure
                    stats["doc_fetch_failed"] += 1

                cur.execute(
                    """INSERT INTO events_raw
                           (ticker, source_type, source_url, raw_text,
                            source_publish_time, accession_number)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       -- Populate accession_number (canonical, dashed) so backfill
                       -- rows match the live poller's accession dedup and are valid
                       -- for the v5 corpus query. Untargeted ON CONFLICT covers BOTH
                       -- the source_url and accession_number unique constraints.
                       ON CONFLICT DO NOTHING
                       RETURNING raw_id""",
                    (ticker, f["form"], src_url, raw_text, f["publish_time"], f["accession"]),
                )
                if cur.fetchone():
                    stats["inserted"] += 1
                else:
                    stats["skipped_dedup"] += 1
    finally:
        conn.close()

    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Historical EDGAR backfill (v3.0)")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--ticker", help="single ticker (otherwise all in universe)")
    p.add_argument("--dry-run", action="store_true", help="report counts, do not insert")
    p.add_argument("--resume", action="store_true", help="skip tickers already in state file")
    args = p.parse_args(argv)

    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        print("[backfill] invalid date. use YYYY-MM-DD", file=sys.stderr)
        return 2

    cik_map = _cik_lookup()
    if args.ticker:
        ticker = args.ticker.upper()
        if ticker not in cik_map:
            print(f"[backfill] ticker {ticker} not in CIK map", file=sys.stderr)
            return 2
        tickers = [ticker]
    else:
        tickers = _get_universe_tickers()

    state = _load_state() if args.resume else {}
    completed = set(state.get("completed_tickers", []))

    grand = {"tickers_done": 0, "tickers_skipped": 0, "in_range": 0,
             "inserted": 0, "skipped_dedup": 0, "doc_fetch_failed": 0}

    print(f"[backfill] starting: {len(tickers)} tickers, {start_date} → {end_date}, "
          f"dry_run={args.dry_run} resume={args.resume}", flush=True)
    if args.resume and completed:
        print(f"[backfill] resume mode: {len(completed)} tickers already completed", flush=True)

    for ticker in tickers:
        if ticker in completed:
            grand["tickers_skipped"] += 1
            continue
        cik = cik_map[ticker]
        try:
            s = backfill_ticker(ticker, cik, start_date, end_date, args.dry_run)
            print(f"[backfill] {ticker}: in_range={s['in_range']} inserted={s['inserted']} "
                  f"skipped_dedup={s['skipped_dedup']} doc_fetch_failed={s['doc_fetch_failed']}",
                  flush=True)
            grand["tickers_done"] += 1
            grand["in_range"] += s["in_range"]
            grand["inserted"] += s["inserted"]
            grand["skipped_dedup"] += s["skipped_dedup"]
            grand["doc_fetch_failed"] += s["doc_fetch_failed"]
        except Exception as e:
            print(f"[backfill] {ticker}: ERROR {type(e).__name__}: {e}",
                  file=sys.stderr, flush=True)
            continue

        if not args.dry_run:
            completed.add(ticker)
            state["completed_tickers"] = sorted(completed)
            state["last_completed_ticker"] = ticker
            state["last_run"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

    print(f"[backfill] DONE: {grand}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
