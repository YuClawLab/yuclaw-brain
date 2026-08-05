#!/usr/bin/env python3
"""
Evidence Coverage v1 — descriptive/coverage-class statistic, registered
in the canonical chain BEFORE computation (registry-first). Answers one
question per name: how much evidence currently stands under this
classification. It is coverage, not prediction — the spec says so
explicitly and the rendered caption repeats it.

Registers the protocol if absent, computes for U79, writes
output/oie/evidence_coverage.json, records the run (ledger-counted).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

SPEC = """
EVIDENCE COVERAGE v1 (descriptive/coverage class; locked 2026-08-04)
Per-name Evidence Coverage Score (ECS) on 0-100, computed as-of a date T
over the trailing 90 calendar days, from four inputs measured on the
canonical U79 record only:

  E  = count of accepted events for the name (events.event_status =
       'accepted', available_as_of in (T-90d, T])
  R  = days from the latest such accepted event to T (undefined if E=0)
  D  = count of distinct event_type values among those events
  S  = 1 if at least one raw filing for the name was ingested in the
       window (events_raw row fetched in (T-90d, T]), else 0
       (filing-substrate completeness: the mapped substrate path is
       actually producing documents)

  ECS = round( 25 * min(E, 8) / 8
             + (25 * exp(-R / 30) if E > 0 else 0)
             + 25 * min(D, 4) / 4
             + 25 * S )

Constants (8-event saturation, 30-day recency decay, 4-type saturation,
equal 25-point blocks) are fixed by this spec; changes require
supersession. ECS is EXPLICITLY NOT A RETURN PREDICTOR: it measures how
much evidence stands under a name's classification, carries no
directional content, and must never be rendered, ranked, or marketed as
an expected-return, quality, or attractiveness measure. Rendered caption
(locked): "how much evidence stands under this classification —
coverage, not prediction." Names with no evidence substrate (index/macro
instruments) print their low ECS as measured — absence of evidence is
disclosed, never imputed.
"""

CAPTION = ("how much evidence stands under this classification — "
           "coverage, not prediction")
OUT = _REPO / "output" / "oie" / "evidence_coverage.json"


def register():
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(SPEC, {"class": "descriptive_coverage", "version": 1})
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name="Evidence Coverage v1",
            method_hash=hashlib.sha256(SPEC.encode()).hexdigest()[:16],
            spec_summary="Per-name ECS 0-100 from accepted-event count, "
                         "recency, type diversity, substrate activity "
                         "(90d window; exact formula in spec); "
                         "descriptive/coverage class — explicitly not a "
                         "return predictor.",
            primary_endpoint="ECS per U79 name as-of the run date "
                             "(descriptive; no inferential endpoint)",
            secondary_endpoints=[],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"LOCKED Evidence Coverage v1 {pid}")
    return reg, pid


def compute() -> dict:
    from v3.universe_tiers import scoring_universe
    names = sorted(scoring_universe())
    out = {}
    with psycopg2.connect("dbname=yuclaw_events") as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            for tk in names:
                cur.execute("""SELECT count(*),
                        max(available_as_of),
                        count(DISTINCT event_type)
                    FROM events WHERE ticker=%s AND event_status='accepted'
                      AND available_as_of > now() - interval '90 days'""",
                            (tk,))
                e, latest, d = cur.fetchone()
                cur.execute("""SELECT count(*) FROM events_raw
                    WHERE ticker=%s
                      AND fetched_at > now() - interval '90 days'""", (tk,))
                s = 1 if cur.fetchone()[0] else 0
                if e:
                    r_days = (datetime.now(timezone.utc) - latest
                              ).total_seconds() / 86400
                    rec = 25 * math.exp(-r_days / 30)
                else:
                    r_days, rec = None, 0.0
                ecs = round(25 * min(e, 8) / 8 + rec + 25 * min(d, 4) / 4
                            + 25 * s)
                out[tk] = {"ecs": ecs, "events_90d": e,
                           "recency_days": (round(r_days, 1)
                                            if r_days is not None else None),
                           "type_diversity": d, "substrate_active": s}
    return out


def main() -> int:
    reg, pid = register()
    scores = compute()
    artifact = {"protocol_id": pid,
                "method_hash": hashlib.sha256(SPEC.encode()).hexdigest()[:16],
                "as_of": datetime.now(timezone.utc).isoformat(),
                "caption": CAPTION, "scores": scores}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=1))
    rh = hashlib.sha256(json.dumps(scores, sort_keys=True).encode()
                        ).hexdigest()[:16]
    from yuclaw_protocol_registry import Run
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window="trailing 90d, canonical U79 record",
        n_primary_cells=len(scores), n_secondary_cells=0,
        result_hash=rh,
        note="descriptive coverage run; no inferential content"))
    vals = sorted(s["ecs"] for s in scores.values())
    print(f"[ecs] {len(scores)} names · median {vals[len(vals)//2]} · "
          f"min {vals[0]} · max {vals[-1]} · run recorded ({rh})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
