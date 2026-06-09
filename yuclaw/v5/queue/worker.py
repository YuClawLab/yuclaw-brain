"""YUCLAW v5 Layer 0 Day 2 — Evidence extraction worker.

Claims `extract_filing` jobs from the Day-1 Evidence Job Queue, reads the real
filing body from `public.events_raw` (READ-ONLY), runs a minimal extraction
through the local Llama 70B via Ollama, and completes the job through the
queue's state machine.

This is scaffold proof-of-pipeline, NOT the full v5 extraction.

Day-2 placeholders (to be replaced as later layers land):
  * ``result_token_id`` is a fresh uuid4 — Layer 2 evidence tokens don't exist
    yet, so there is no tokens table to FK to. Replace when Layer 2 lands.
  * ``EXTRACTION_PROMPT`` is a minimal, bounded scaffold prompt. The real
    multi-specialist extraction is Layer 1 (swarm) work.

Invariants honoured:
  * Queue logic is reused from core.EvidenceJobQueue (never reimplemented).
  * Writes only to schema yuclaw_v5 (via the queue). public.events_raw is read
    in an explicitly READ-ONLY transaction.
  * No daemon: `run()` polls a bounded number of times on an empty queue, then
    exits cleanly. Meant for a foreground/tmux session, not a persistent cron.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import requests

from yuclaw.v5.queue.core import DEFAULT_DSN, EvidenceJobQueue

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

OLLAMA_URL = os.environ.get("YUCLAW_V5_OLLAMA_URL", "http://localhost:11434")
# NOTE: the live 70B on this box is tagged yuclaw-llm-70b:latest (the renamed
# compliance tag from v3.0), NOT "llama3.1:70b". Override via env if needed.
MODEL = os.environ.get("YUCLAW_V5_MODEL", "yuclaw-llm-70b:latest")
DEFAULT_LLAMA_TIMEOUT = float(os.environ.get("YUCLAW_V5_LLAMA_TIMEOUT", "300"))
JOB_TYPE = "extract_filing"
MAX_FILING_CHARS = 6000  # real EDGAR bodies are ~4000; cap defensively

# --------------------------------------------------------------------------
# Logging -> ~/.yuclaw/v5/worker.log
# --------------------------------------------------------------------------

_LOG_DIR = Path(os.path.expanduser("~/.yuclaw/v5"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_PATH = _LOG_DIR / "worker.log"

logger = logging.getLogger("yuclaw.v5.worker")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _h = logging.FileHandler(_LOG_PATH)
    _h.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.addHandler(_h)
    logger.propagate = False

# Minimal, bounded Day-2 extraction prompt (scaffold — Layer 1 will replace).
EXTRACTION_PROMPT = (
    "You extract ONE structured event from an SEC filing excerpt. "
    "Return ONLY a JSON object with exactly these keys:\n"
    '  "event_type"       — a short category, e.g. "earnings", "guidance", '
    '"M&A", "leadership_change", "debt", "dividend", "other"\n'
    '  "summary"          — one sentence, <= 200 characters\n'
    '  "affected_ticker"  — the primary ticker symbol as a string, or null if unknown\n'
    "Do not output anything except the JSON object.\n\n"
    "FILING EXCERPT:\n{text}\n\nJSON:"
)


class WorkerError(RuntimeError):
    """Raised for recoverable per-job failures (routed to mark_failed)."""


class Worker:
    """Claims and runs `extract_filing` jobs through the Evidence Job Queue."""

    def __init__(
        self,
        worker_id: str,
        queue: Optional[EvidenceJobQueue] = None,
        dsn: str = DEFAULT_DSN,
        model: str = MODEL,
        ollama_url: str = OLLAMA_URL,
        llama_timeout: float = DEFAULT_LLAMA_TIMEOUT,
    ) -> None:
        self.worker_id = worker_id
        self.dsn = dsn
        self.queue = queue or EvidenceJobQueue(dsn=dsn)
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.llama_timeout = llama_timeout
        logger.info(
            "Worker init id=%s model=%s ollama=%s timeout=%ss",
            worker_id, model, self.ollama_url, llama_timeout,
        )

    # -- data access (READ-ONLY on public.*) ------------------------------

    def _fetch_filing_text(self, accession_number: str) -> Optional[str]:
        """READ-ONLY fetch of a filing body from public.events_raw.

        Wrapped in an explicit read-only transaction as defence-in-depth: this
        worker must never write v4's public schema.
        """
        cn = psycopg2.connect(self.dsn)
        try:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute(
                    "SELECT raw_text FROM public.events_raw "
                    "WHERE accession_number = %s LIMIT 1",
                    (accession_number,),
                )
                row = cur.fetchone()
        finally:
            cn.close()
        return row[0] if row else None

    # -- extraction --------------------------------------------------------

    def _extract_with_llama(self, filing_text: str) -> tuple[dict, float, Any]:
        """Run the minimal extraction. Returns (parsed_dict, seconds, eval_count)."""
        prompt = EXTRACTION_PROMPT.format(text=filing_text[:MAX_FILING_CHARS])
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # Ollama constrains output to valid JSON
            "options": {"temperature": 0, "num_predict": 256},
        }
        t0 = time.perf_counter()
        resp = requests.post(
            f"{self.ollama_url}/api/generate", json=body, timeout=self.llama_timeout
        )
        elapsed = time.perf_counter() - t0
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("response") or "").strip()
        if not text:
            raise WorkerError("Llama returned an empty response")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise WorkerError(f"Llama output was not valid JSON: {e}: {text[:200]!r}")
        if not isinstance(parsed, dict) or not parsed:
            raise WorkerError(f"Llama output was empty/non-object: {text[:200]!r}")
        return parsed, elapsed, data.get("eval_count")

    # -- single job --------------------------------------------------------

    def process_job(self, job: dict) -> dict:
        """Run one claimed job end-to-end. Raises on failure (caller marks failed)."""
        job_id = str(job["job_id"])
        payload = job.get("payload") or {}
        accession = payload.get("accession_number")
        logger.info("job=%s claimed accession=%s", job_id, accession)

        self.queue.mark_running(job_id, self.worker_id)

        # Prefer an explicitly-provided body; otherwise fetch read-only by accession.
        text = payload.get("raw_text") or (
            self._fetch_filing_text(accession) if accession else None
        )
        if not text:
            raise WorkerError(f"no filing text for accession={accession!r}")

        logger.info("job=%s extracting (len=%d chars)", job_id, len(text))
        extraction, llama_secs, eval_count = self._extract_with_llama(text)
        logger.info(
            "job=%s extraction done llama=%.2fs eval=%s keys=%s",
            job_id, llama_secs, eval_count, sorted(extraction.keys()),
        )

        # Day-2 placeholder: real Layer-2 evidence token id will replace this uuid4.
        token_id = str(uuid.uuid4())
        self.queue.mark_succeeded(job_id, result_token_id=token_id)
        logger.info("job=%s SUCCEEDED token=%s", job_id, token_id)

        return {
            "job_id": job_id,
            "accession_number": accession,
            "result_token_id": token_id,
            "llama_secs": llama_secs,
            "eval_count": eval_count,
            "extraction": extraction,
        }

    # -- loops -------------------------------------------------------------

    def run_once(self, batch_size: int = 1) -> tuple[list, list]:
        """Claim and process up to batch_size jobs. Returns (claimed, results)."""
        jobs = self.queue.claim_next(
            self.worker_id, job_types=[JOB_TYPE], batch_size=batch_size
        )
        results = []
        for job in jobs:
            job_id = str(job["job_id"])
            try:
                results.append(self.process_job(job))
            except Exception as e:  # noqa: BLE001 — route every failure to the queue
                err = f"{type(e).__name__}: {e}"
                logger.exception("job=%s FAILED: %s", job_id, err)
                self.queue.mark_failed(job_id, err[:2000])
                results.append({"job_id": job_id, "error": err})
        return jobs, results

    def run(
        self,
        max_empty_polls: int = 3,
        poll_interval: float = 2.0,
        batch_size: int = 1,
        max_jobs: Optional[int] = None,
    ) -> dict:
        """Poll-and-process until the queue is empty (bounded) then exit.

        Not a daemon: after `max_empty_polls` consecutive empty claims it stops.
        `max_jobs` optionally caps total jobs (used to run exactly N this session).
        """
        processed = 0
        succeeded = 0
        failed = 0
        empty = 0
        while empty < max_empty_polls:
            if max_jobs is not None and processed >= max_jobs:
                break
            bs = batch_size
            if max_jobs is not None:
                bs = min(batch_size, max_jobs - processed)
            jobs, results = self.run_once(batch_size=bs)
            if not jobs:
                empty += 1
                logger.info("empty claim (%d/%d)", empty, max_empty_polls)
                time.sleep(poll_interval)
                continue
            empty = 0
            processed += len(jobs)
            succeeded += sum(1 for r in results if "error" not in r)
            failed += sum(1 for r in results if "error" in r)
        logger.info(
            "worker %s exiting: processed=%d succeeded=%d failed=%d",
            self.worker_id, processed, succeeded, failed,
        )
        return {"processed": processed, "succeeded": succeeded, "failed": failed}


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="YUCLAW v5 Layer 0 extraction worker")
    p.add_argument("--worker-id", default=f"worker-{uuid.uuid4().hex[:8]}")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--max-empty-polls", type=int, default=3)
    p.add_argument("--poll-interval", type=float, default=2.0)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--max-jobs", type=int, default=None)
    args = p.parse_args(argv)

    w = Worker(worker_id=args.worker_id, model=args.model)
    summary = w.run(
        max_empty_polls=args.max_empty_polls,
        poll_interval=args.poll_interval,
        batch_size=args.batch_size,
        max_jobs=args.max_jobs,
    )
    print(f"[worker {args.worker_id}] {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
