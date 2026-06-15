"""YUCLAW v5 Layer 1 — swarm orchestrator.

dispatch(filing) drives one filing through the swarm using the Layer 0
``EvidenceJobQueue`` (reused, never reimplemented):

  1. read the filing body from public.events_raw (READ-ONLY) if not supplied;
  2. enqueue 3 ``swarm_agent`` jobs (Bull/Bear/Skeptic), idempotent on
     accession + agent_role + prompt_version;
  3. run them CONCURRENTLY via the queue's multi-worker SKIP-LOCKED claim path
     (3 threads → 3 parallel Ollama 8B calls);
  4. enqueue + run one ``swarm_synthesis`` job (70B) over the three outputs;
  5. persist to yuclaw_v5.swarm_outputs and return the assembled result.

Writes only to schema yuclaw_v5 (queue + swarm_outputs). public.events_raw is
read in an explicitly READ-ONLY transaction.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from yuclaw.v5.queue.core import DEFAULT_DSN, EvidenceJobQueue, new_token_id
from yuclaw.v5.swarm.agents import (
    AGENT_MODEL, AGENT_REGISTRY, PROMPT_VERSION, SYNTH_MODEL, SynthesisAgent,
)

AGENT_JOB_TYPE = "swarm_agent"
SYNTH_JOB_TYPE = "swarm_synthesis"
ROLES = ("bull", "bear", "skeptic")


class SwarmDispatchError(RuntimeError):
    """Hard-gate failure: any stage timeout / error / empty output."""


class SwarmOrchestrator:
    def __init__(self, queue: Optional[EvidenceJobQueue] = None, dsn: str = DEFAULT_DSN,
                 agent_model: str = AGENT_MODEL, synth_model: str = SYNTH_MODEL):
        self.dsn = dsn
        self.queue = queue or EvidenceJobQueue(dsn=dsn)
        self.agent_model = agent_model
        self.synth_model = synth_model
        self.synth = SynthesisAgent(model=synth_model)

    # -- READ-ONLY filing fetch ------------------------------------------
    def _fetch_filing_text(self, accession: str) -> Optional[str]:
        cn = psycopg2.connect(self.dsn)
        try:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute("SELECT raw_text FROM public.events_raw "
                            "WHERE accession_number = %s LIMIT 1", (accession,))
                row = cur.fetchone()
        finally:
            cn.close()
        return row[0] if row else None

    # -- one concurrent agent worker -------------------------------------
    def _agent_worker(self, worker_id: str, text: str, trace_id: str) -> dict:
        """Claim ONE swarm_agent job (mine, by trace_id), run its role agent,
        complete it through the queue. Returns the agent output dict."""
        deadline = time.time() + 60
        while time.time() < deadline:
            jobs = self.queue.claim_next(worker_id, job_types=[AGENT_JOB_TYPE], batch_size=1)
            if not jobs:
                time.sleep(0.15)
                continue
            job = jobs[0]
            job_id = str(job["job_id"])
            payload = job["payload"] or {}
            if payload.get("trace_id") != trace_id:
                # Not from this dispatch. Day-1 assumes an idle, single-dispatch
                # queue, so this only happens when a PRIOR dispatch left a job
                # pending (e.g. a retry after a failure). RELEASE it intact for
                # its rightful claimant — never mark_failed, which would charge
                # that job an attempt and wrongly drive a neighbour toward
                # dead_letter. We still fail loudly here: robustly draining a
                # contended/leftover queue is later-day Layer-1 work.
                self.queue.release(job_id, worker_id)
                raise SwarmDispatchError(f"claimed foreign swarm_agent job {job_id}")
            role = payload["agent_role"]
            self.queue.mark_running(job_id, worker_id)
            try:
                agent = AGENT_REGISTRY[role](model=self.agent_model)
                result = agent.run(text)
            except Exception as e:  # route failure through the queue
                self.queue.mark_failed(job_id, f"{type(e).__name__}: {e}"[:2000])
                raise SwarmDispatchError(f"agent {role} failed: {e}") from e
            self.queue.mark_succeeded(job_id, result_token_id=new_token_id())
            result["job_id"] = job_id
            return result
        raise SwarmDispatchError(f"worker {worker_id} timed out claiming a job")

    # -- dispatch --------------------------------------------------------
    def dispatch(self, accession: str, raw_text: Optional[str] = None,
                 persist: bool = True, synthesize: bool = True) -> dict:
        """Run the swarm on one filing.

        synthesize=False runs ONLY the 3 grounded agents (+ grading) and returns
        — no 70B synthesis, no persist. Used by the Day-2 prompt-iteration loop,
        where the target metric is per-agent grounding and synthesis is wasted cost.
        """
        t_start = time.perf_counter()
        text = raw_text or self._fetch_filing_text(accession)
        if not text:
            raise SwarmDispatchError(f"no filing text for accession={accession!r}")
        trace_id = f"swarm-{accession}-{PROMPT_VERSION}-{new_token_id()[:8]}"

        # 1. enqueue 3 agent jobs (idempotent on accession+role+version)
        agent_job_ids = {}
        for role in ROLES:
            jid = self.queue.enqueue(
                AGENT_JOB_TYPE,
                {"accession_number": accession, "agent_role": role,
                 "prompt_version": PROMPT_VERSION, "trace_id": trace_id,
                 "raw_text": text},
                idempotency_key=f"swarm:{accession}:{role}:{PROMPT_VERSION}",
                trace_id=trace_id, priority=120)
            agent_job_ids[role] = jid

        # 2. run the 3 concurrently (multi-worker SKIP-LOCKED claim)
        t_conc0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(self._agent_worker, f"swarm-w{i}", text, trace_id)
                       for i in range(3)]
            results = [f.result() for f in futures]
        concurrent_wall = time.perf_counter() - t_conc0

        by_role = {r["agent_role"]: r for r in results}
        if set(by_role) != set(ROLES):
            raise SwarmDispatchError(f"expected roles {ROLES}, got {sorted(by_role)}")

        grounding_summary = self._grounding_summary(by_role)

        # Agent-only path (prompt iteration): stop here, no synthesis / persist.
        if not synthesize:
            return {
                "accession_number": accession, "prompt_version": PROMPT_VERSION,
                "trace_id": trace_id, "filing_len": len(text),
                "agents": by_role, "synthesis": None,
                "agent_job_ids": agent_job_ids, "synth_job_id": None,
                "grounding_summary": grounding_summary,
                "citation_ledger": self._build_ledger(accession, by_role, None),
                "timings": {
                    "concurrent_agent_wall_secs": round(concurrent_wall, 2),
                    "agent_secs": {r: by_role[r]["llama_secs"] for r in ROLES},
                    "total_swarm_secs": round(time.perf_counter() - t_start, 2),
                    "synthesis_secs": None,
                },
                "model_tags": {"agents": self.agent_model, "synthesis": None,
                               "prompt_version": PROMPT_VERSION},
            }

        # 3. synthesis (70B) via the queue — receives ONLY grounded claims.
        synth_job_id = self.queue.enqueue(
            SYNTH_JOB_TYPE,
            {"accession_number": accession, "prompt_version": PROMPT_VERSION,
             "trace_id": trace_id},
            idempotency_key=f"swarm-synth:{accession}:{PROMPT_VERSION}",
            trace_id=trace_id, priority=130)
        claimed = self.queue.claim_next("swarm-synth", job_types=[SYNTH_JOB_TYPE], batch_size=1)
        # claim the one we just enqueued (idle queue → it's ours)
        sjob = next((j for j in claimed if str(j["job_id"]) == synth_job_id), claimed[0] if claimed else None)
        if sjob is None:
            raise SwarmDispatchError("could not claim synthesis job")
        synth_job_id = str(sjob["job_id"])
        self.queue.mark_running(synth_job_id, "swarm-synth")
        try:
            synth = self.synth.run(text, by_role)
        except Exception as e:
            self.queue.mark_failed(synth_job_id, f"{type(e).__name__}: {e}"[:2000])
            raise SwarmDispatchError(f"synthesis failed: {e}") from e
        self.queue.mark_succeeded(synth_job_id, result_token_id=new_token_id())

        ledger = self._build_ledger(accession, by_role, synth)
        grounding_summary["synthesis_citations_total"] = \
            synth["synth_citation_grounding"]["citations_total"]
        grounding_summary["synthesis_citations_verified"] = \
            synth["synth_citation_grounding"]["citations_verified"]
        grounding_summary["ledger_span_count"] = len(ledger["spans"])

        total = time.perf_counter() - t_start
        timings = {
            "total_swarm_secs": round(total, 2),
            "concurrent_agent_wall_secs": round(concurrent_wall, 2),
            "agent_secs": {r: by_role[r]["llama_secs"] for r in ROLES},
            "synthesis_secs": synth["llama_secs"],
        }
        model_tags = {"agents": self.agent_model, "synthesis": self.synth_model,
                      "prompt_version": PROMPT_VERSION}
        assembled = {
            "accession_number": accession, "prompt_version": PROMPT_VERSION,
            "trace_id": trace_id, "filing_len": len(text),
            "agents": by_role, "synthesis": synth,
            "agent_job_ids": agent_job_ids, "synth_job_id": synth_job_id,
            "grounding_summary": grounding_summary, "citation_ledger": ledger,
            "timings": timings, "model_tags": model_tags,
        }
        if persist:
            self._persist(assembled)
        return assembled

    # -- grounding aggregation -------------------------------------------
    @staticmethod
    def _grounding_summary(by_role: dict) -> dict:
        keys = ("grounding_rate", "points_grounded", "points_total",
                "points_discarded", "citations_total", "citations_verified")
        return {"per_agent": {
            r: {k: by_role[r]["grounding"][k] for k in keys} for r in ROLES}}

    @staticmethod
    def _build_ledger(accession: str, by_role: dict, synth: Optional[dict]) -> dict:
        """Proto evidence token: accession + the union of verified spans, deduped
        by (start, end), tagged with their source agent."""
        spans, seen = [], set()

        def add(source: str, led: list) -> None:
            for e in led:
                key = (e["start"], e["end"])
                if key in seen:
                    continue
                seen.add(key)
                spans.append({"source": source, "quote": e["quote"],
                              "start": e["start"], "end": e["end"],
                              "match_type": e["match_type"]})

        for role in ROLES:
            add(role, by_role[role]["grounding"]["ledger"])
        if synth:
            add("synthesis", synth["synth_citation_grounding"]["ledger"])
        return {"accession_number": accession, "prompt_version": PROMPT_VERSION,
                "spans": spans}

    # -- persistence (yuclaw_v5 only) ------------------------------------
    def _persist(self, a: dict) -> None:
        cn = psycopg2.connect(self.dsn)
        try:
            with cn, cn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO yuclaw_v5.swarm_outputs
                        (accession_number, prompt_version, bull_output, bear_output,
                         skeptic_output, synthesis_output, timings, model_tags,
                         agent_job_ids, synth_job_id, grounding_summary, citation_ledger)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::uuid,%s,%s)
                    ON CONFLICT (accession_number, prompt_version) DO UPDATE SET
                        bull_output=EXCLUDED.bull_output, bear_output=EXCLUDED.bear_output,
                        skeptic_output=EXCLUDED.skeptic_output,
                        synthesis_output=EXCLUDED.synthesis_output,
                        timings=EXCLUDED.timings, model_tags=EXCLUDED.model_tags,
                        agent_job_ids=EXCLUDED.agent_job_ids, synth_job_id=EXCLUDED.synth_job_id,
                        grounding_summary=EXCLUDED.grounding_summary,
                        citation_ledger=EXCLUDED.citation_ledger,
                        created_at=now()
                    """,
                    (a["accession_number"], a["prompt_version"],
                     psycopg2.extras.Json(a["agents"]["bull"]),
                     psycopg2.extras.Json(a["agents"]["bear"]),
                     psycopg2.extras.Json(a["agents"]["skeptic"]),
                     psycopg2.extras.Json(a["synthesis"]),
                     psycopg2.extras.Json(a["timings"]),
                     psycopg2.extras.Json(a["model_tags"]),
                     psycopg2.extras.Json(a["agent_job_ids"]), a["synth_job_id"],
                     psycopg2.extras.Json(a["grounding_summary"]),
                     psycopg2.extras.Json(a["citation_ledger"])))
        finally:
            cn.close()
