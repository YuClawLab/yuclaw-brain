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

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "v1.txt"
PROMPT_VERSION = "v1"
RAW_TEXT_MAX_CHARS = 4000

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
        timeout=180.0,
    )
    resp.raise_for_status()
    text = (resp.json().get("response") or "").strip()
    text = _FENCE_OPEN.sub("", text)
    text = _FENCE_CLOSE.sub("", text)
    # The model may emit a JSON object plus stray prose; find the first {...} block
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


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
        "errors": 0,
    }

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT raw_id, ticker, source_type, source_url,
                          raw_text, source_publish_time
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

                # 1. LLM call
                try:
                    llm_json = _ollama_extract(
                        ticker, row["source_type"], row["raw_text"]
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

                # 3. SourceLock Guard
                ok, reason = validate(llm_json, row["raw_text"], ticker)
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

            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

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
