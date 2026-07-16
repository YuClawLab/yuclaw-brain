"""
Event extraction worker.

Pulls pending rows from events_raw, calls the local LLM (Ollama) with the
locked v1 prompt, runs SourceLock Guard validation on the JSON output, and
either:
  - inserts an accepted row into events
  - inserts a rejection row into rejected_events with a reject_reason
  - marks the raw row done with no event written (for {"no_event": true})

CLI:
    python3 -m v3.extract.event_worker --once          # single batch then exit
    python3 -m v3.extract.event_worker                 # loop, 30s sleep
    python3 -m v3.extract.event_worker --batch 10      # batch size
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
import psycopg2
import psycopg2.extras

from v3.extract.sourcelock import validate
from v3.extract import prose_live, reclassify_live

# Order 1D (2026-05-29): switched from v1.txt → v2.txt. v2 adds an explicit
# 4-step procedure that forces the LLM to locate a contiguous source span and
# copy it character-for-character before classifying. Recovers 27/45 (60%) of
# previously R7-rejected events including 5 cascade-eligible (ABT EARNINGS_BEAT,
# ARM/CVX GUIDANCE_RAISE, INTC M_AND_A_CLOSE, PSX GUIDANCE_CUT) when paired with
# the html-decode R7 fallback. v1.txt retained in prompts/ for instant rollback.
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "v2.txt"
PROMPT_VERSION = "v2"
# Day 3 timeout fix (2026-05-19): empirical Llama 70B latency on real
# SEC filings was ~250-400s with the old 4000-char cap, blowing past
# the old 180s httpx timeout. Causes: real filings have denser tokens
# than synthetic input. Mitigations applied here:
#   1. Drop prompt cap 4000 → 2500 chars (real material events are in
#      the first 1-2KB of the doc body anyway)
#   2. Raise httpx timeout 180 → 600s (10 min ceiling)
# Yesterday's 90-day backfill produced 255/259 LLM_ERROR: timed out
# before this fix.
RAW_TEXT_MAX_CHARS = 2500
OLLAMA_TIMEOUT_SECONDS = 600.0

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.environ.get("YUCLAW_SUPER_MODEL", "yuclaw-llm-70b")
DB_DSN = "dbname=yuclaw_events"

_PROMPT_TEMPLATE = PROMPT_PATH.read_text()

# Strip optional ```json ... ``` fence in case the model adds one
_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"\s*```\s*$")


def _build_prompt(ticker: str, source_type: str, raw_text: str) -> str:
    return (_PROMPT_TEMPLATE
            .replace("{{TICKER}}", ticker or "?")
            .replace("{{SOURCE_TYPE}}", source_type or "unknown")
            .replace("{{RAW_TEXT}}", raw_text[:RAW_TEXT_MAX_CHARS]))


def _ollama_extract(ticker: str, source_type: str, raw_text: str) -> dict:
    """Call local LLM. Returns parsed JSON dict.
    Raises on HTTP failure or unparseable response.
    """
    prompt = _build_prompt(ticker, source_type, raw_text)
    resp = httpx.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 600},
        },
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    text = (resp.json().get("response") or "").strip()
    text = _FENCE_OPEN.sub("", text)
    text = _FENCE_CLOSE.sub("", text)
    # Robustness against LLM output drift:
    # - leading prose before the JSON      → seek to first '{'
    # - trailing prose AFTER the JSON      → raw_decode discards remainder
    # - markdown fences                    → already stripped above
    # This handles all three corner cases that broke yesterday's batch.
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found in LLM output: {text[:120]!r}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def _content_hash(ticker: str, event_type: str, raw_excerpt: str) -> str:
    payload = f"{ticker}|{event_type}|{raw_excerpt.lower().strip()}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _event_id(ticker: str, content_hash: str, publish_time) -> str:
    return f"{ticker}_{publish_time.strftime('%Y%m%d')}_{content_hash[:12]}"


def process_batch(limit: int = 5) -> dict:
    """One batch: FOR UPDATE SKIP LOCKED, process each row, commit."""
    stats = {
        "processed": 0,
        "accepted": 0,
        "no_event": 0,
        "rejected": 0,
        "duplicate": 0,
        "errors": 0,
    }

    # Accepted events to re-classify (the "rescue") AFTER the events txn commits, so the
    # live re-classifier sees a committed event and its write to event_type_corrected stays
    # additive / outside the worker's transaction. (taxonomy fix, 2026-06-24)
    to_reclassify: list[dict] = []
    # Prose-first ingestion (f130983e port, 2026-07-06): every processed filing —
    # accepted, rejected, or no-event alike — gets a best-effort prose extraction
    # AFTER the txn commits, so the production swarm reads exhibit/MD&A prose from
    # yuclaw_v5.swarm_inputs instead of raw_cover soup. Additive; never blocks.
    to_prose: list[dict] = []

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT raw_id, ticker, source_type, source_url,
                          raw_text, source_publish_time, accession_number
                   FROM events_raw
                   WHERE extraction_status='pending'
                   ORDER BY fetched_at
                   LIMIT %s
                   FOR UPDATE SKIP LOCKED""",
                (limit,),
            )
            rows = cur.fetchall()

            for row in rows:
                stats["processed"] += 1
                ticker = row["ticker"] or "?"
                to_prose.append({"accession": row["accession_number"],
                                 "form": row["source_type"], "ticker": ticker})

                # 6-K/40-F are cover-page envelopes: classify on the EXHIBIT prose
                # (with the cover's exhibit-index one-liner as a typing hint), never
                # on the cover alone. SourceLock below validates against the SAME
                # text the LLM saw, so raw_excerpt stays a verbatim substring.
                # (Canada Resources evidence tier, 2026-07-14.)
                llm_text = row["raw_text"]
                if row["source_type"] in ("6-K", "40-F"):
                    composed = prose_live.compose_foreign_input(
                        row["accession_number"], row["source_type"], row["raw_text"])
                    if composed:
                        llm_text = composed
                        print(f"[event_worker] {row['source_type']} exhibit-input "
                              f"{ticker} {row['accession_number']}: hint="
                              f"{composed.splitlines()[0][:100]!r} chars={len(composed)}",
                              flush=True)
                    else:
                        print(f"[event_worker] {row['source_type']} exhibit-input "
                              f"{ticker} {row['accession_number']}: UNAVAILABLE — "
                              f"falling back to raw cover", flush=True)

                # 1. LLM call
                try:
                    llm_json = _ollama_extract(
                        ticker, row["source_type"], llm_text
                    )
                except Exception as e:
                    cur.execute(
                        """INSERT INTO rejected_events
                               (raw_id, ticker, reject_reason, llm_output)
                           VALUES (%s, %s, %s, %s)""",
                        (row["raw_id"], ticker, f"LLM_ERROR: {str(e)[:200]}", None),
                    )
                    cur.execute(
                        "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s",
                        (row["raw_id"],),
                    )
                    stats["errors"] += 1
                    continue

                # 2. Explicit no-event sentinel
                if llm_json.get("no_event") is True:
                    cur.execute(
                        "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s",
                        (row["raw_id"],),
                    )
                    stats["no_event"] += 1
                    continue

                # 3. SourceLock Guard (against the text the LLM actually saw)
                ok, reason = validate(llm_json, llm_text, ticker)
                if not ok:
                    cur.execute(
                        """INSERT INTO rejected_events
                               (raw_id, ticker, reject_reason, llm_output)
                           VALUES (%s, %s, %s, %s)""",
                        (row["raw_id"], ticker, reason, json.dumps(llm_json)),
                    )
                    cur.execute(
                        "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s",
                        (row["raw_id"],),
                    )
                    stats["rejected"] += 1
                    continue

                # 4. Accept — write events row
                publish_time = row["source_publish_time"]
                ch = _content_hash(ticker, llm_json["event_type"], llm_json["raw_excerpt"])
                eid = _event_id(ticker, ch, publish_time)

                # event_id is built from the LOCAL publish day while the dedup
                # index below is keyed on the UTC day, so two same-content
                # filings straddling UTC midnight dodge ON CONFLICT yet collide
                # on events_pkey — aborting the whole batch and poisoning the
                # queue head (IAG 2026-02-17 pair, 2026-07-15 stall). Treat an
                # existing event_id as the duplicate it is: audit + mark done.
                cur.execute("SELECT 1 FROM events WHERE event_id=%s", (eid,))
                if cur.fetchone():
                    cur.execute(
                        """INSERT INTO rejected_events
                               (raw_id, ticker, reject_reason, llm_output)
                           VALUES (%s, %s, %s, %s)""",
                        (row["raw_id"], ticker,
                         f"DUPLICATE_EVENT_ID: {eid}", json.dumps(llm_json)),
                    )
                    cur.execute(
                        "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s",
                        (row["raw_id"],),
                    )
                    stats["duplicate"] += 1
                    print(f"[event_worker] duplicate event_id {eid} "
                          f"(raw_id={row['raw_id']}, accession="
                          f"{row['accession_number']}) — marked done", flush=True)
                    continue

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
                        eid, ticker, llm_json["event_type"],
                        llm_json["magnitude"], llm_json["direction"],
                        publish_time, publish_time,
                        publish_time, row["source_type"], row["source_url"],
                        llm_json["raw_excerpt"],
                        OLLAMA_MODEL, llm_json["confidence"],
                        llm_json.get("rationale", ""),
                        ch, PROMPT_VERSION,
                    ),
                )
                cur.execute(
                    "UPDATE events_raw SET extraction_status='done' WHERE raw_id=%s",
                    (row["raw_id"],),
                )
                stats["accepted"] += 1
                to_reclassify.append({
                    "event_id": eid, "accession": row["accession_number"], "ticker": ticker,
                    "v4_type": llm_json["event_type"], "excerpt": llm_json["raw_excerpt"],
                    "source_url": row["source_url"],
                })

            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Live re-classify rescue (additive to event_type_corrected; never mutates events).
    # Best-effort: a re-class failure must not fail ingestion — the event is already
    # committed and the corrected layer can be rebuilt by the batch re-classifier.
    for r in to_reclassify:
        try:
            res = reclassify_live.reclassify_one(
                r["event_id"], r["accession"], r["ticker"], r["v4_type"],
                r["excerpt"], r["source_url"])
            if res["changed"]:
                print(f"[event_worker] reclassify {r['ticker']} {r['v4_type']} -> "
                      f"{res['corrected_event_type']} ({res['source']})", flush=True)
        except Exception as e:
            print(f"[event_worker] reclassify FAILED for {r['event_id']}: "
                  f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)

    # Prose-first persistence (best-effort; ingest_prose never raises).
    for p in to_prose:
        status, detail = prose_live.ingest_prose(p["accession"], p["form"])
        if status not in ("skip", "existing"):
            print(f"[event_worker] prose {p['ticker']} {p['form']} "
                  f"{p['accession'] or '?'}: {status} {detail}", flush=True)

    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Event extraction worker (v3.0)")
    p.add_argument("--once", action="store_true", help="single batch then exit")
    p.add_argument("--sleep", type=int, default=30, help="seconds between batches in loop mode")
    p.add_argument("--batch", type=int, default=5, help="rows per batch")
    args = p.parse_args(argv)

    if args.once:
        s = process_batch(args.batch)
        print(f"[event_worker] {s}")
        return 0

    while True:
        try:
            s = process_batch(args.batch)
            print(f"[event_worker] {s}", flush=True)
        except Exception as e:
            print(f"[event_worker] error: {e}", file=sys.stderr, flush=True)
        time.sleep(args.sleep)


if __name__ == "__main__":
    sys.exit(main())
