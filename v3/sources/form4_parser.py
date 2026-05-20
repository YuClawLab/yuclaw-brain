"""
Form 4 (insider transactions) — deterministic XML parser.

Form 4 filings are structured XML; using a 70B LLM on them is overkill.
This parser fetches each Form 4 directly from SEC, extracts non-derivative
transactions, filters out non-trades + de minimis amounts, and writes
INSIDER_BUY / INSIDER_SELL rows directly into the events table.

CLI:
    python3 -m v3.sources.form4_parser --start YYYY-MM-DD --end YYYY-MM-DD
    python3 -m v3.sources.form4_parser ... --dry-run
    python3 -m v3.sources.form4_parser ... --ticker AAPL

Filters:
- Equities only (the 50 equities in v3/universe.json; sector ETFs et al.
  don't file insider transactions in any meaningful way).
- transactionCode: only P (Open-Market Purchase) and S (Open-Market Sale).
  Skip A / G / I / M / F (grants / gifts / discretionary / exercise / tax).
- De minimis: skip transactions where shares × price < $50,000.

Scoring rules:
- event_type:      INSIDER_BUY for code P, INSIDER_SELL for code S
- direction:       +1 for buy, -1 for sell
- magnitude:       min(1.0, value / $5,000,000)  — caps at $5M
- llm_confidence:  1.0  (deterministic)
- llm_model:       deterministic-xml-parser
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, date, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import psycopg2
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from v3.sources.edgar_poll import _load_universe, _cik_lookup, USER_AGENT, DB_DSN

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_SLEEP_SECONDS = 0.15  # SEC publishes 10 req/sec cap; 0.15s sleep ~ 6.6 req/sec
DE_MINIMIS_USD = 50_000
MAGNITUDE_CAP_USD = 5_000_000
TRADE_CODES = {"P", "S"}  # P = open-market purchase, S = open-market sale


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


def _archive_dir(cik: str, accession: str) -> str:
    """URL of the filing's directory."""
    cik_int = int(cik)
    accession_clean = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_clean}"


def _equities_universe() -> set[str]:
    """Form 4 only applies to operating companies — equities slot only."""
    u = json.loads((Path(__file__).resolve().parent.parent / "universe.json").read_text())
    return set(u.get("equities", []))


def _filter_form4_filings(submissions: dict, start_date: date, end_date: date) -> list[dict]:
    """Extract form='4' filings within window from submissions JSON."""
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        return []
    n = len(recent.get("accessionNumber", []))
    forms = recent.get("form", [])
    fdates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    primaries = recent.get("primaryDocument", [])
    accept_dts = recent.get("acceptanceDateTime", [])

    out = []
    for i in range(n):
        if i >= len(forms) or forms[i] != "4":
            continue
        try:
            filing_date = datetime.strptime(fdates[i], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            continue
        if not (start_date <= filing_date <= end_date):
            continue
        accept_dt_str = (accept_dts[i] if i < len(accept_dts) else None) \
            or (fdates[i] + "T00:00:00Z")
        try:
            publish_time = datetime.fromisoformat(accept_dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            publish_time = datetime(filing_date.year, filing_date.month, filing_date.day,
                                    tzinfo=timezone.utc)
        out.append({
            "accession": accs[i],
            "filing_date": filing_date,
            "publish_time": publish_time,
            "primary": primaries[i] if i < len(primaries) else "",
        })
    return out


def _find_xml_url(cik: str, accession: str, primary: str) -> str | None:
    """Locate the Form 4 XML within a filing package.

    The /submissions API gives us `primaryDocument` which may be either the
    XML directly or a rendered HTML wrapper. We try the JSON index of the
    filing dir, which always contains the actual file list.
    """
    arch = _archive_dir(cik, accession)
    # Try the index.json first — most reliable
    try:
        r = _fetch(f"{arch}/index.json")
        idx = r.json()
        for item in idx.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.endswith(".xml") and "form" in name.lower():
                return f"{arch}/{name}"
        # Fallback: any .xml file
        for item in idx.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.endswith(".xml"):
                return f"{arch}/{name}"
    except Exception:
        pass
    # Fallback: try primaryDocument if it already ends .xml
    if primary and primary.endswith(".xml"):
        return f"{arch}/{primary}"
    return None


def _parse_form4_xml(xml_text: str) -> tuple[str, list[dict]]:
    """Parse Form 4 XML. Returns (insider_name, [transactions]).

    Each transaction dict:
        code:        P / S / etc.
        shares:      float (signed by direction)
        price:       float USD
        date:        ISO YYYY-MM-DD string
        value:       shares × price (USD)
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "", []

    insider_name = ""
    for el in root.iter():
        tag = el.tag.split("}")[-1]  # strip namespace
        if tag == "rptOwnerName":
            insider_name = (el.text or "").strip()
            break

    transactions = []
    # Walk all <nonDerivativeTransaction> elements
    for tx in root.iter():
        tag = tx.tag.split("}")[-1]
        if tag != "nonDerivativeTransaction":
            continue
        record = {"code": "", "shares": 0.0, "price": 0.0, "date": "", "value": 0.0}
        for child in tx.iter():
            ctag = child.tag.split("}")[-1]
            # transactionCode contains <value>P</value> inside <transactionCoding>
            if ctag == "transactionCode" and child.text:
                record["code"] = child.text.strip()
            elif ctag == "transactionDate":
                for v in child.iter():
                    if v.tag.split("}")[-1] == "value" and v.text:
                        record["date"] = v.text.strip()
                        break
            elif ctag == "transactionShares":
                for v in child.iter():
                    if v.tag.split("}")[-1] == "value" and v.text:
                        try:
                            record["shares"] = float(v.text.strip())
                        except ValueError:
                            pass
                        break
            elif ctag == "transactionPricePerShare":
                for v in child.iter():
                    if v.tag.split("}")[-1] == "value" and v.text:
                        try:
                            record["price"] = float(v.text.strip())
                        except ValueError:
                            pass
                        break
        record["value"] = record["shares"] * record["price"]
        transactions.append(record)
    return insider_name, transactions


def _event_id(ticker: str, accession: str, idx: int) -> str:
    return f"{ticker}_F4_{accession.replace('-', '')}_{idx}"


def _content_hash(ticker: str, accession: str, tx: dict) -> str:
    payload = f"{ticker}|{accession}|{tx['code']}|{tx['shares']}|{tx['price']}|{tx['date']}"
    return hashlib.sha256(payload.encode()).hexdigest()


def parse_filing(cik: str, ticker: str, filing: dict, dry_run: bool, conn) -> dict:
    """Parse one Form 4 filing and insert qualifying rows into events."""
    stats = {"transactions": 0, "trades": 0, "kept": 0, "de_minimis": 0, "inserted": 0}

    xml_url = _find_xml_url(cik, filing["accession"], filing["primary"])
    if not xml_url:
        return stats

    try:
        r = _fetch(xml_url)
    except Exception:
        return stats

    insider, txs = _parse_form4_xml(r.text)
    stats["transactions"] = len(txs)

    accepted = []
    for i, tx in enumerate(txs):
        if tx["code"] not in TRADE_CODES:
            continue
        stats["trades"] += 1
        if tx["value"] < DE_MINIMIS_USD:
            stats["de_minimis"] += 1
            continue
        stats["kept"] += 1
        accepted.append((i, tx))

    if dry_run or not accepted:
        return stats

    publish_time = filing["publish_time"]
    available_as_of = publish_time
    with conn.cursor() as cur:
        for idx, tx in accepted:
            event_type = "INSIDER_BUY" if tx["code"] == "P" else "INSIDER_SELL"
            direction = 1 if tx["code"] == "P" else -1
            magnitude = min(1.0, tx["value"] / MAGNITUDE_CAP_USD)
            ch = _content_hash(ticker, filing["accession"], tx)
            eid = _event_id(ticker, filing["accession"], idx)
            raw_excerpt = (f"{insider} {tx['code']} {tx['shares']:.0f} shares "
                           f"@ ${tx['price']:.2f} on {tx['date']} "
                           f"(${tx['value']:,.0f})")[:400]
            cur.execute("""
                INSERT INTO events (
                    event_id, ticker, event_type, magnitude, direction,
                    event_time, source_publish_time, source_ingested_time,
                    available_as_of, source_type, source_url, raw_excerpt,
                    llm_model, llm_confidence, llm_reasoning,
                    content_hash, prompt_version, event_status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, now(),
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, 'accepted'
                )
                ON CONFLICT (content_hash, ticker, (date_trunc('day', available_as_of AT TIME ZONE 'UTC')))
                DO NOTHING
            """, (
                eid, ticker, event_type, magnitude, direction,
                publish_time, publish_time,
                available_as_of, "4-parsed", xml_url, raw_excerpt,
                "deterministic-xml-parser", 1.0,
                f"Form 4 {tx['code']} transaction by {insider}; value ${tx['value']:,.0f}",
                ch, "form4-v1",
            ))
            stats["inserted"] += 1
        conn.commit()

    return stats


def backfill_form4(ticker: str, cik: str, start_date: date, end_date: date,
                   dry_run: bool, conn) -> dict:
    """All Form 4 filings for one ticker in window."""
    stats = {"ticker": ticker, "filings": 0, "transactions": 0, "trades": 0,
             "kept": 0, "de_minimis": 0, "inserted": 0}

    try:
        r = _fetch(SUBMISSIONS_URL.format(cik=cik))
        submissions = r.json()
    except Exception as e:
        print(f"[form4] {ticker}: submissions fetch failed: {e}", file=sys.stderr)
        return stats

    filings = _filter_form4_filings(submissions, start_date, end_date)
    stats["filings"] = len(filings)

    for f in filings:
        s = parse_filing(cik, ticker, f, dry_run, conn)
        for k in ("transactions", "trades", "kept", "de_minimis", "inserted"):
            stats[k] += s[k]

    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Form 4 deterministic XML parser (v3.0)")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--ticker", help="single ticker (otherwise all equities)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        print("[form4] invalid date. use YYYY-MM-DD", file=sys.stderr)
        return 2

    equities = _equities_universe()
    cik_map = _cik_lookup()
    if args.ticker:
        t = args.ticker.upper()
        if t not in equities:
            print(f"[form4] {t} not in equities universe", file=sys.stderr)
            return 2
        tickers = [t]
    else:
        tickers = sorted([t for t in equities if t in cik_map])

    print(f"[form4] starting: {len(tickers)} tickers, {start_date} → {end_date}, dry_run={args.dry_run}",
          flush=True)

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    grand = {"tickers_done": 0, "filings": 0, "transactions": 0, "trades": 0,
             "kept": 0, "de_minimis": 0, "inserted": 0}
    try:
        for t in tickers:
            cik = cik_map[t]
            try:
                s = backfill_form4(t, cik, start_date, end_date, args.dry_run, conn)
            except Exception as e:
                print(f"[form4] {t}: ERROR {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                conn.rollback()
                continue
            print(f"[form4] {t}: filings={s['filings']} trades={s['trades']} "
                  f"kept={s['kept']} de_minimis={s['de_minimis']} inserted={s['inserted']}",
                  flush=True)
            grand["tickers_done"] += 1
            for k in ("filings", "transactions", "trades", "kept", "de_minimis", "inserted"):
                grand[k] += s[k]
    finally:
        conn.close()

    print(f"[form4] DONE: {grand}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
