#!/usr/bin/env python3
"""
Cross-lens reversal coherence v1 — REGISTERED TODAY, COMPUTED NO EARLIER THAN
2026-09-01. This module deliberately contains NO analysis code; the guard in
run() is the only executable behavior until the compute date. The registry's
second deliberately-waiting protocol (pattern: C6 Risk Gate, 0df6fc002d79).

WHY THIS EXISTS. The 2026-07-27 momentum-conditioning run (protocol
dfee13621c33) found, in EXPLORATORY secondary cells, that the W=60
winners-minus-losers aligned-CAR difference was negative in all five targets
(SMH-E4, XEG, ZEO, GDX, URNM), with conservative envelopes excluding zero in
three. Re-testing that pattern on the same data would be confirmation
laundering. Hypothesis from exploration; confirmation only on data that does
not exist yet.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

METHOD_SPEC = """
CROSS-LENS REVERSAL COHERENCE — pre-committed specification (v1)
Hypothesis (from exploration, dfee13621c33 secondary cells, 2026-07-27):
prior-60-trading-day issuer-vs-peer winners deliver LOWER direction-aligned
peer-model CAR at tau=+20 than prior losers, coherently across unrelated
lenses.
Data: ONLY events whose day0 falls on/after 2026-07-27 (forward accrual;
none of it exists at registration). Targets: SMH-E4 (capped-ETF weights,
covered sleeve), XEG, ZEO, GDX, URNM (pooled event-weighted). Estimand and
momentum machinery identical to protocols 15052741ba2a / dfee13621c33:
direction-aligned peer-model CAR at +20; relative momentum = compounded
issuer minus EW-peer return over [day0-60, day0-1], >=40 usable paired days;
median split within each target's accrued set.
MINIMUM WINDOW (pre-specified): compute no earlier than 2026-09-01, AND a
target qualifies only with >=15 events that have complete +20 windows and
momentum data. If fewer than 3 targets qualify: verdict INSUFFICIENT —
report accrual counts, no coherence claim, wait.
PRIMARY (single): sign-coherence = number of qualifying targets with a
NEGATIVE winners-minus-losers difference. Verdict labels (locked):
  COHERENT      — all qualifying targets negative AND >=4 qualify
  LEANING       — >=75% of qualifying targets negative (>=3 qualify)
  NOT_COHERENT  — otherwise
  INSUFFICIENT  — <3 qualifying targets
One-sided sign-test p (H0: P(negative)=0.5, independence across targets
stated as an approximation) reported beside the verdict, never replacing it.
SECONDARY (ledger-counted): per-target differences with issuer+date cluster
envelopes (machinery of dfee13621c33); per-target ns; W=20 variant
(disclosed, no verdict weight). B=4000, seed 20260901. No interim peeks:
the first computation IS the verdict computation.
Edits to this spec => supersession, never amendment.
"""
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
COMPUTE_NOT_BEFORE = date(2026, 9, 1)
ACCRUAL_START = date(2026, 7, 27)

PROTOCOL_NAME = "Cross-lens reversal coherence v1"
PROTOCOL_PARAMS = {
    "targets": ["SMH-E4", "XEG", "ZEO", "GDX", "URNM"],
    "accrual_start": "2026-07-27", "compute_not_before": "2026-09-01",
    "momentum_window": 60, "min_events_per_target": 15,
    "min_qualifying_targets": 3, "horizon_tau": 20,
    "B": 4000, "seed": 20260901,
}


def register() -> str:
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if reg.get_protocol(pid):
        print(f"[registry] protocol {pid} already LOCKED")
        return pid
    reg.register(Protocol(
        protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
        spec_summary=("Forward-accrual confirmation of the exploratory W=60 "
                      "cross-lens reversal pattern: sign-coherence of "
                      "winners-minus-losers aligned-CAR differences across "
                      "five targets, events from 2026-07-27 only, computed "
                      "no earlier than 2026-09-01, >=15 events/target, "
                      "verdict labels locked."),
        primary_endpoint=("sign-coherence count of negative W=60 "
                          "winners-minus-losers differences across "
                          "qualifying targets (verdict per locked labels)"),
        secondary_endpoints=[
            "per-target differences with issuer+date cluster envelopes",
            "per-target accrual counts",
            "W=20 variant (disclosed, no verdict weight)",
        ],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ))
    reg.verify_chain()
    print(f"[registry] LOCKED protocol {pid} ({PROTOCOL_NAME}) "
          f"method_hash={METHOD_HASH} — ZERO runs until >= {COMPUTE_NOT_BEFORE}")
    return pid


def run():
    """The 2026-09-01+ computation enters HERE and nowhere else."""
    today = datetime.now(timezone.utc).date()
    if today < COMPUTE_NOT_BEFORE:
        raise RuntimeError(
            f"Cross-lens reversal coherence is guarded: computation is "
            f"scheduled no earlier than {COMPUTE_NOT_BEFORE} on forward "
            f"accrual from {ACCRUAL_START}. Today is {today}. No interim "
            f"peeks — the first computation is the verdict computation.")
    raise NotImplementedError(
        "Analysis code is intentionally absent until the compute date; "
        "implement against METHOD_SPEC verbatim, then record the run.")


if __name__ == "__main__":
    register()
    try:
        run()
    except RuntimeError as e:
        print(f"[guard] {e}")
