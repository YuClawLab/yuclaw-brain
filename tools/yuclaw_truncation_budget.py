#!/usr/bin/env python3
"""
Truncation & Error Budget Spec — pre-registered protocol (v1).
LOCKED WITHOUT COMPUTING (sleeping registration, order of 2026-08-06 P0-B).
===========================================================================
Platform-discipline spec: every truncation, filter, or cap on any surface
must be enumerated in one ledger with a fixed schema, and the chain gate
(tools/check_truncation_ledger.py, active immediately) fails on any new
truncation-shaped code without a ledger entry.

This module locks the discipline; the ledger itself lives at
registry/truncation_ledger.json. Zero research runs, zero result cells,
zero statistical estimation at registration — ledger population is
bookkeeping only (counting/summing over already-committed artifacts);
anything needing estimation prints PENDING with its rerun threshold
(amendment A-2).
"""
from __future__ import annotations

import hashlib
import json

METHOD_SPEC = """
TRUNCATION & ERROR BUDGET SPEC (v1, locked 2026-08-07)

SCOPE
All surfaces: U350, Ground Truth, EvidenceBench, evidence lenses (SMH /
XLK / Canada Resources), BYOS, robustness grids, and every public page
that prints a pooled or per-name statistic.

PRINCIPLE
No unit of evidence leaves a denominator silently. Every truncation,
filter, cap, structural inactivation, or exclusion is a LEDGER ENTRY;
readers see the budget, not just the survivors.

LEDGER (registry/truncation_ledger.json; version-numbered)
Fields per entry, all required:
  reason                — what is dropped/capped and why (mechanism, not
                          judgment);
  count                 — units affected; populated only by counting or
                          summing over already-committed artifacts, with
                          the source artifact named; otherwise PENDING;
  retained_mass         — share of pre-truncation mass kept, same
                          population rule as count; PENDING is legal;
  interpretation_change — yes | no | unknown (unknown is a legal answer);
  rerun_threshold       — the condition under which the entry's numbers
                          must be re-derived and the affected surfaces
                          re-read.
Entries also carry code anchors (file path + sha256 at registration) so
drift in truncation-bearing code is detectable.

ENUMERATED EXISTING SITES (registered now; anchors + populated fields in
the ledger artifact):
  1. cascade decay — depth-1 carries 0.20, depth-2 carries 0.04, depth-3+
     dropped (v3/signal/cascade_engine.py).
  2. snapshot per-name cap — 100 evidence objects per name
     (v3/evidence/snapshot.py PER_NAME_CAP).
  3. U350 drain cap + shadow-starves-first — DRAIN_CAP filings per drain
     run; shadow work yields to ALL U79 work (v3/u350/shadow_ops.py).
  4. C7 STRUCTURALLY_INACTIVE — the peer-correlation component is
     structurally inactive; disclosed wherever C7 status appears
     (v3/signal/components/c7_peer_correlation.py).
  5. open-window closure — forward windows enter matured panels only on
     closure; open windows are excluded, never padded
     (v3/track/outcome_updater.py).
  6. corporate-action exclusions — membership changes must invoke the
     corporate-action policy; affected spans are excluded, never
     silently spliced (tools/check_universe_integrity.py + the
     corporate_action_lineage record).
  7. evidence-tier boundary — evidence-tier names are never scored;
     positive gating plus a standing negative check
     (v3/universe_tiers.py).
  8. LLM failure families — extraction failures drop filings from the
     event stream by family (parse failure, refusal, timeout/retry
     exhaustion) (v3/extract/event_worker.py, v3/sources/edgar_poll_v2.py).
  9. delisting staleness — scoring-universe names with stale latest
     prices are flagged by the delisting watch and excluded from fresh
     panels until resolved (tools/check_universe_integrity.py).

DISCLOSURE
One derived ledger artifact is the single source; page footnotes DERIVE
from it (no hand-typed budget numbers anywhere). Footnote rollout is a
follow-on display change under its own order — this registration changes
no public copy.

GATE (active immediately)
tools/check_truncation_ledger.py runs in the daily chain and fails when:
  (a) any ledger entry is missing a required field or carries an illegal
      flag value;
  (b) any anchored file's hash drifts from the ledger (truncation-bearing
      code changed without a same-commit ledger update);
  (c) the detector finds a truncation-shaped constant (cap/limit/max
      assignment) or exclusion enum not covered by the ledger's versioned
      allowlist.
Detector posture (amendment A-3): conservative first — full
enumerated-site inventory plus new-cap-constant and exclusion-enum
detection; broader branch-level detection only as it can run quietly. A
gate that fires falsely gets ignored, so the detector prefers
narrow-and-trusted and widens by versioned allowlist review only.

SUPERSESSION
Any change to this spec's text requires registry supersession, never
amendment. Ledger CONTENT updates (new entries, PENDING -> populated,
allowlist review) are ordinary versioned commits and do not touch the
spec hash; removing or weakening an entry requires a supersession note.
"""

METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PARAMS = {"ledger_version": 1, "enumerated_sites": 9}
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]


def _registry_guard(pid: str) -> None:
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))
    from yuclaw_protocol_registry import Registry
    Registry(str(root / "registry" / "protocols.jsonl")).assert_registered(pid)


def run():
    """The derived public ledger artifact + footnote rollout enter HERE
    under their own order. Guarded first; intentionally unimplemented."""
    _registry_guard(PROTOCOL_ID)
    raise NotImplementedError(
        f"Truncation & Error Budget v1 is a sleeping registration "
        f"(protocol {PROTOCOL_ID}, method {METHOD_HASH}). The gate is "
        f"active (tools/check_truncation_ledger.py); the derived public "
        f"artifact ships under its own order.")


if __name__ == "__main__":
    print(f"[truncation-budget] METHOD_HASH={METHOD_HASH} · "
          f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · LOCKED, "
          f"gate active, not computed")
