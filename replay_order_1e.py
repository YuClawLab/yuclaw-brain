#!/usr/bin/env python3
"""Order 1E — replay the 45 R7-rejected filings through the now-live v2 + html-decode R7 chain.

Confirmed design (2026-05-30):
  - archive-then-replay : the 45 `R7_excerpt_verifiable` rows in rejected_events are copied
                          to rejected_events_archive (preserves the v1 audit trail) and then
                          deleted, so recovered filings move cleanly to `events` and the
                          still-failing ones get exactly one fresh reject row.
  - dedicated + isolated: target rows are marked extraction_status='replay_1e'. The live
                          event_worker selects only 'pending', so it never touches these.
  - idempotent          : phase0 runs once (guarded by the archive table); phase1 processes
                          one row per transaction with FOR UPDATE SKIP LOCKED; the events
                          insert is ON CONFLICT DO NOTHING. Safe to re-run after interruption.

Reuses event_worker's EXACT extract/validate/insert logic (no behavioral divergence).

Usage:
    python3 replay_order_1e.py --phase0-only   # archive + mark (fast, verifiable)
    python3 replay_order_1e.py --phase1-only   # drain replay_1e rows (the ~3.5h LLM pass)
    python3 replay_order_1e.py                 # both
"""
import argparse
import json
import time

import psycopg2
import psycopg2.extras

import v3.extract.event_worker as ew
from v3.extract.sourcelock import validate

DSN = ew.DB_DSN
R7 = "R7_excerpt_verifiable"
REPLAY = "replay_1e"
ARCHIVE_REASON = "order_1e_v2_replay"


def log(m: str) -> None:
    print(f"[order_1e] {time.strftime('%Y-%m-%d %H:%M:%S')} {m}", flush=True)


def phase0() -> None:
    """Archive the 45 R7 reject rows, delete them, mark their raw rows for replay.

    Guarded: if the archive already holds ARCHIVE_REASON rows, phase0 has run before —
    skip (do NOT re-query by reject_reason, which would re-capture fresh reject rows
    that phase1 creates for still-failing filings). Resume straight to phase1.
    """
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS rejected_events_archive (
                       reject_id     bigint,
                       raw_id        bigint,
                       ticker        text,
                       reject_reason text,
                       llm_output    jsonb,
                       rejected_at   timestamptz,
                       archived_at   timestamptz NOT NULL DEFAULT now(),
                       archive_reason text
                   )"""
            )
            cur.execute(
                "SELECT count(*) FROM rejected_events_archive WHERE archive_reason=%s",
                (ARCHIVE_REASON,),
            )
            already = cur.fetchone()[0]
            if already:
                cur.execute(
                    "SELECT count(*) FROM events_raw WHERE extraction_status=%s", (REPLAY,)
                )
                remaining = cur.fetchone()[0]
                conn.commit()
                log(
                    f"phase0: already initialized (archive has {already} rows); "
                    f"{remaining} rows still at '{REPLAY}'. Skipping archive/mark; resuming phase1."
                )
                return

            cur.execute(
                "SELECT raw_id FROM rejected_events WHERE reject_reason=%s ORDER BY raw_id",
                (R7,),
            )
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                conn.commit()
                log("phase0: no R7 rows found in rejected_events and no archive — nothing to replay.")
                return

            cur.execute(
                """INSERT INTO rejected_events_archive
                       (reject_id, raw_id, ticker, reject_reason, llm_output, rejected_at, archive_reason)
                   SELECT reject_id, raw_id, ticker, reject_reason, llm_output, rejected_at, %s
                   FROM rejected_events WHERE reject_reason=%s""",
                (ARCHIVE_REASON, R7),
            )
            archived = cur.rowcount
            cur.execute("DELETE FROM rejected_events WHERE reject_reason=%s", (R7,))
            deleted = cur.rowcount
            cur.execute(
                "UPDATE events_raw SET extraction_status=%s WHERE raw_id = ANY(%s)",
                (REPLAY, ids),
            )
            marked = cur.rowcount
            conn.commit()
            log(
                f"phase0: archived={archived} deleted={deleted} marked_for_replay={marked}"
            )
            log(f"phase0: target raw_ids = {ids}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def phase1() -> dict:
    """Drain all rows at status='replay_1e', one per transaction. Mirrors event_worker."""
    stats = {"processed": 0, "accepted": 0, "rejected": 0, "no_event": 0, "errors": 0}
    while True:
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT raw_id, ticker, source_type, source_url,
                              raw_text, source_publish_time
                       FROM events_raw
                       WHERE extraction_status=%s
                       ORDER BY raw_id
                       LIMIT 1
                       FOR UPDATE SKIP LOCKED""",
                    (REPLAY,),
                )
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    break

                rid = row["raw_id"]
                ticker = row["ticker"] or "?"
                stats["processed"] += 1

                # 1. LLM call
                try:
                    llm = ew._ollama_extract(ticker, row["source_type"], row["raw_text"])
                except Exception as e:
                    cur.execute(
                        """INSERT INTO rejected_events (raw_id, ticker, reject_reason, llm_output)
                           VALUES (%s, %s, %s, %s)""",
                        (rid, ticker, f"LLM_ERROR: {str(e)[:200]}", None),
                    )
                    cur.execute(
                        "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s", (rid,)
                    )
                    conn.commit()
                    stats["errors"] += 1
                    log(f"  raw_id={rid} {ticker}: LLM_ERROR {str(e)[:80]}")
                    continue

                # 2. no-event sentinel
                if llm.get("no_event") is True:
                    cur.execute(
                        "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s", (rid,)
                    )
                    conn.commit()
                    stats["no_event"] += 1
                    log(f"  raw_id={rid} {ticker}: no_event")
                    continue

                # 3. SourceLock Guard (validate against FULL raw_text, as in prod)
                ok, reason = validate(llm, row["raw_text"], ticker)
                if not ok:
                    cur.execute(
                        """INSERT INTO rejected_events (raw_id, ticker, reject_reason, llm_output)
                           VALUES (%s, %s, %s, %s)""",
                        (rid, ticker, reason, json.dumps(llm)),
                    )
                    cur.execute(
                        "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s", (rid,)
                    )
                    conn.commit()
                    stats["rejected"] += 1
                    log(f"  raw_id={rid} {ticker}: REJECT {reason}")
                    continue

                # 4. Accept — write events row (idempotent ON CONFLICT)
                pt = row["source_publish_time"]
                ch = ew._content_hash(ticker, llm["event_type"], llm["raw_excerpt"])
                eid = ew._event_id(ticker, ch, pt)
                cur.execute(
                    """INSERT INTO events (
                           event_id, ticker, event_type, magnitude, direction,
                           event_time, source_publish_time, source_ingested_time,
                           available_as_of, source_type, source_url, raw_excerpt,
                           llm_model, llm_confidence, llm_reasoning,
                           content_hash, prompt_version, event_status
                       )
                       VALUES (%s, %s, %s, %s, %s,
                               %s, %s, now(),
                               %s, %s, %s, %s,
                               %s, %s, %s,
                               %s, %s, 'accepted')
                       ON CONFLICT (content_hash, ticker,
                                    (date_trunc('day', available_as_of AT TIME ZONE 'UTC')))
                       DO NOTHING""",
                    (
                        eid, ticker, llm["event_type"],
                        llm["magnitude"], llm["direction"],
                        pt, pt,
                        pt, row["source_type"], row["source_url"], llm["raw_excerpt"],
                        ew.OLLAMA_MODEL, llm["confidence"], llm.get("rationale", ""),
                        ch, ew.PROMPT_VERSION,
                    ),
                )
                inserted = cur.rowcount
                cur.execute(
                    "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s", (rid,)
                )
                conn.commit()
                stats["accepted"] += 1
                log(
                    f"  raw_id={rid} {ticker}: ACCEPT {llm['event_type']} "
                    f"(event_inserted={bool(inserted)})"
                )
        except Exception as e:
            conn.rollback()
            log(f"  FATAL (rolled back this row): {type(e).__name__}: {str(e)[:160]}")
            raise
        finally:
            conn.close()
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description="Order 1E — replay 45 R7-rejected filings")
    p.add_argument("--phase0-only", action="store_true", help="archive + mark, then stop")
    p.add_argument("--phase1-only", action="store_true", help="drain replay_1e rows only")
    a = p.parse_args()

    log(f"=== Order 1E start — prompt={ew.PROMPT_PATH.name} model={ew.OLLAMA_MODEL} ===")
    if not a.phase1_only:
        phase0()
    if a.phase0_only:
        log("=== phase0 complete (--phase0-only) ===")
        return 0
    s = phase1()
    log(
        f"=== Order 1E DONE — processed={s['processed']} accepted={s['accepted']} "
        f"rejected={s['rejected']} no_event={s['no_event']} errors={s['errors']} ==="
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
