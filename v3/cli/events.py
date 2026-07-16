"""CLI: yuclaw events --ticker SU [--since YYYY-MM-DD] [--json | --csv]

Accepted-events export — YUCLAW-derived data only (typed classifications,
verified excerpts; never raw vendor price data). Default output is a human
table; --json / --csv for machine use. Usefulness build, 2026-07-16.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime

import psycopg2

DSN = "dbname=yuclaw_events"

COLUMNS = ("event_id", "ticker", "event_type", "magnitude", "direction",
           "available_as_of", "source_type", "source_url", "llm_confidence",
           "raw_excerpt")


def fetch_events(ticker: str, since: str | None, dsn: str = DSN) -> list[dict]:
    q = """SELECT event_id, ticker, event_type, magnitude, direction,
                  available_as_of, source_type, source_url, llm_confidence,
                  raw_excerpt
           FROM events
           WHERE event_status='accepted' AND ticker = %s"""
    params: list = [ticker.upper()]
    if since:
        q += " AND available_as_of >= %s"
        params.append(since)
    q += " ORDER BY available_as_of"
    with psycopg2.connect(dsn) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(q, params)
            return [dict(zip(COLUMNS, r)) for r in cur.fetchall()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw events",
                                description="Export accepted evidence events (derived data only)")
    p.add_argument("--ticker", required=True)
    p.add_argument("--since", help="YYYY-MM-DD (available_as_of lower bound)")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true")
    fmt.add_argument("--csv", action="store_true")
    a = p.parse_args(argv)

    if a.since:
        try:
            datetime.strptime(a.since, "%Y-%m-%d")
        except ValueError:
            print("--since must be YYYY-MM-DD", file=sys.stderr)
            return 2

    rows = fetch_events(a.ticker, a.since)

    if a.json:
        print(json.dumps(rows, indent=1, default=str))
    elif a.csv:
        w = csv.writer(sys.stdout)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in COLUMNS])
    else:
        if not rows:
            print(f"no accepted events for {a.ticker.upper()}"
                  + (f" since {a.since}" if a.since else ""))
            return 0
        for r in rows:
            ex = (r["raw_excerpt"] or "").strip()
            ex = ex[:90] + "…" if len(ex) > 90 else ex
            print(f"{str(r['available_as_of'])[:10]}  {r['event_type']:<18} "
                  f"dir {r['direction']:+d}  mag {r['magnitude']:.2f}  {r['source_type']:<8} {ex}")
        print(f"\n{len(rows)} accepted event(s) · research classifications, not recommendations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
