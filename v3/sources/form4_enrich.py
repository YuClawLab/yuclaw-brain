"""
Backfill DISPLAY/MEMO-ONLY Form-4 attributes onto existing INSIDER_BUY /
INSIDER_SELL events (usefulness build, 2026-07-16).

For every insider event with attributes IS NULL, re-fetch the stored Form-4
XML (events.source_url is the XML URL written by form4_parser), extract the
reporting-person role and Rule 10b5-1 plan flag, and UPDATE events.attributes
for all events sharing that filing. EDGAR rate-respecting (same _fetch as the
parser). Idempotent — enriched events are skipped on re-run.

C6 and every scoring component read only the typed columns; attributes are
never consumed by scoring (frozen).

CLI:
    python3 -m v3.sources.form4_enrich            # all missing
    python3 -m v3.sources.form4_enrich --limit 10 # smoke
"""
from __future__ import annotations

import argparse
import json
import sys

import psycopg2

from v3.sources.edgar_poll import DB_DSN
from v3.sources.form4_parser import _fetch, _parse_form4_owner_attrs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backfill Form-4 display attributes")
    p.add_argument("--limit", type=int, default=None, help="cap filings (smoke)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = True
    stats = {"filings": 0, "events_updated": 0, "fetch_failed": 0, "parse_empty": 0}
    try:
        with conn.cursor() as cur:
            # One XML per filing; all its events share the source_url.
            cur.execute(
                """SELECT source_url, count(*) FROM events
                   WHERE event_type IN ('INSIDER_BUY','INSIDER_SELL')
                     AND attributes IS NULL
                   GROUP BY source_url ORDER BY source_url""")
            targets = cur.fetchall()
        if args.limit is not None:
            targets = targets[:args.limit]
        print(f"[form4_enrich] {len(targets)} filings to enrich "
              f"(dry_run={args.dry_run})", flush=True)

        for url, n_events in targets:
            stats["filings"] += 1
            try:
                r = _fetch(url)
            except Exception as e:
                stats["fetch_failed"] += 1
                print(f"[form4_enrich] fetch failed {url}: {type(e).__name__}",
                      file=sys.stderr, flush=True)
                continue
            attrs = _parse_form4_owner_attrs(r.text)
            if not attrs:
                stats["parse_empty"] += 1
                continue
            if args.dry_run:
                print(f"[dry-run] {url} -> {attrs} ({n_events} events)", flush=True)
                continue
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE events SET attributes = %s
                       WHERE source_url = %s
                         AND event_type IN ('INSIDER_BUY','INSIDER_SELL')
                         AND attributes IS NULL""",
                    (json.dumps(attrs), url))
                stats["events_updated"] += cur.rowcount
            if stats["filings"] % 100 == 0:
                print(f"[form4_enrich] progress: {stats}", flush=True)
    finally:
        conn.close()

    print(f"[form4_enrich] DONE: {stats}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
