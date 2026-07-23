#!/usr/bin/env python3
"""
C6 Risk Gate Lab — pre-registered protocol (v1). LOCKED WITHOUT COMPUTING.
==========================================================================
This module exists to LOCK the specification before any computation against
the live accrual. It deliberately contains NO analysis code. The 2026-07-30
reading must be implemented behind run() below, which refuses to execute
unless this exact spec (by hash) is LOCKED in registry/protocols.jsonl.

Registered: registry/protocols.jsonl (first native pre-registration — the
protocol entry predates any run entry for it, by construction).
"""
from __future__ import annotations

import hashlib
import json

METHOD_SPEC = """
C6 RISK GATE LAB — pre-committed specification (v1, locked 2026-07-23)

QUESTION
Does the C6 risk channel's elevated state mark issuer-days with higher
subsequent realized risk, out-of-sample, on the live accrual?

POPULATION
Issuer-days = (issuer, event date) pairs of Layer-1-processed filings from
the live C6 accrual beginning 2026-07-16 (live Form-4 ingestion enable),
through the freshest completed forward window at compute time. Arm
assignment: the risk-channel flag (elevated | normal) recorded point-in-time
in the persisted risk-channel artifacts for that issuer-day — never
recomputed retroactively. Exclusions: issuer-days with no recorded flag;
forward windows truncated by the data edge are excluded from any horizon k
they cannot complete (never padded, never shrunk).

PRIMARY ENDPOINT (exactly one)
Forward realized volatility ratio, elevated/normal, at k=10:
  RV(i,d,k) = stdev of close-to-close daily returns of issuer i over the k
  trading days after day d (raw daily stdev, no annualization).
  Statistic: ratio of arm means, RV_elevated(k=10) / RV_normal(k=10).

SECONDARY ENDPOINTS (exploratory; every cell counted in the test ledger)
S1. Max drawdown within k in {5, 10, 20}: maximum peak-to-trough decline of
    the close path over the forward window, per arm; reported as the
    elevated-minus-normal difference per k.
S2. Tail-event frequency: share of issuer-days whose forward 10-day window
    contains >=1 daily |return| > 2 sigma, where sigma = that issuer's
    daily-return stdev over the 60 trading days ENDING at day d
    (point-in-time; no forward information); elevated-minus-normal
    difference.
S3. Sign endpoint (REFERENCE ONLY): the elevated > normal mean-forward-vol
    sign check is governed by the existing pre-committed OOS clause
    (docs/v5/layer1/risk_oos_check.md @ 130579a5; re-run
    docs/v5/layer1/risk_oos_rerun.md @ aba72e89). This protocol REFERENCES
    that endpoint and does not replace, re-specify, or re-test it.

ANALYSIS PLAN
Cluster-robust comparison reusing the registered ClusteredCAR machinery
(protocol df86dfa7d709, method b717068e17e3f09a): cluster unit = issuer;
issuer-cluster bootstrap (B=4000, seed 20260717) resampling issuers with
replacement within each arm; percentile 2.5/97.5 CI on the primary ratio and
on each secondary difference. Naive CI reported beside, labeled naive.
Effective cluster count G reported per arm.

MINIMUM ARM SIZE: n >= 10 issuer-days per arm (mirrors the original
pre-commitment's "real normal arm (n_norm >= ~10)").

BADGE RULES (locked vocabulary, mirroring the registered canvas rules):
UNDERPOWERED if either arm has G < 8 issuers or n < 10 issuer-days; else
DESCRIPTIVE if the primary CI includes 1.0 (for secondary differences: 0.0);
else PRELIMINARY. No stronger label exists in this protocol.

THIN-ARM CLAUSE (mirrored verbatim from the pre-committed 2026 clause,
130579a5): "INCONCLUSIVE required the held-out batch to be the wrong shape
for the arms to mean anything." Applied here: if either arm fails the
minimum arm size, the read is INCONCLUSIVE — reported, not decorated; the
gate stays open; the result is never forced to PASS or FAIL.

REPORTING
All endpoints reported regardless of direction. Secondary cells counted in
the registry test ledger. No re-weighting, no threshold change, and no
scoring-path change follows from any outcome of this protocol alone.

COMPUTE DISCIPLINE
Registered BEFORE any computation against accrual data; first computation
scheduled 2026-07-30 under this locked text. Any edit to this spec changes
its hash and therefore requires supersession in the registry — never
amendment.
"""

METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PARAMS = {"k_primary": 10}
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]


def _registry_guard(pid: str) -> None:
    """REGISTRY-FIRST: refuse to compute unless the protocol is LOCKED in
    registry/protocols.jsonl (chain-verified on load). Fails closed when the
    registry file is absent."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))
    from yuclaw_protocol_registry import Registry
    Registry(str(root / "registry" / "protocols.jsonl")).assert_registered(pid)


def run():
    """The 2026-07-30 reading enters HERE and nowhere else. Guarded first;
    intentionally unimplemented until that order."""
    _registry_guard(PROTOCOL_ID)
    raise NotImplementedError(
        "C6 Risk Gate computation is scheduled for 2026-07-30 under the "
        f"locked spec (protocol {PROTOCOL_ID}, method {METHOD_HASH}). "
        "This module locks the plan; it does not compute.")


if __name__ == "__main__":
    print(f"[c6-risk-gate] METHOD_HASH={METHOD_HASH} · PROTOCOL_ID={PROTOCOL_ID} "
          f"· params={PARAMS} · LOCKED, not computed")
