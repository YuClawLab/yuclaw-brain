#!/usr/bin/env python3
"""
ANYTIME EVIDENCE RECORD v1 — Science Trust addendum (registered method
spec). Adjudication UNCOMPUTED · enrollment machinery ACTIVE with ZERO
enrollments (order of 2026-08-11, executed 2026-08-10 UTC). PROSPECTIVE
ONLY.
===========================================================================
Second registered addendum under SCIENCE TRUST PROTOCOL v1 (protocol
be8b34040c2e), which named the Anytime Evidence Record as a future
component, UNCOMPUTED / METHOD NOT REGISTERED until its own addendum.
This module IS that addendum: the complete method text below is in-hash.
The METHOD (a test-martingale / e-process family) is locked here, once;
each enrolled instrument registers its own enrollment line BEFORE its own
observation starts (the A-1 pattern applied to instances). Historical
starts are structurally REFUSED. Zero enrollments exist at registration —
honest-empty, like the leaderboard. registry/anytime_record.json is
DERIVED — never hand-maintained; the chain gate rebuilds it from the
canonical chain and fails on any divergence.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
CHAIN = _REPO / "registry" / "protocols.jsonl"
RECORD_PATH = _REPO / "registry" / "anytime_record.json"

UMBRELLA_PROTOCOL_ID = "be8b34040c2e"
ENROLLMENT_KIND = "anytime_enrollment"

# State vocabulary (research-state axis; S6-covered; never signal labels).
ANYTIME_STATES = {
    "REGISTERED", "ACCUMULATING", "WEAK", "SUPPORTED",
    "SUPPORTED_NOT_MATURE", "MATURE", "INCONCLUSIVE", "NOT_IDENTIFIABLE",
}

# Locked e-process constants (in-hash below).
ALPHA = 0.05
THETA_SUPPORTED = 20.0    # = 1/ALPHA
THETA_WEAK = 5.0
GRID_K = 20

# Required fields of every enrollment line — absence is REFUSED, at
# enroll() time and forever after by the chain gate.
ENROLLMENT_REQUIRED = (
    "enrollment_id", "instrument", "registered_null", "parameters",
    "enrolled_at", "start_time", "observation_cadence", "stopping_policy",
    "dependency_assumptions", "invalidation_conditions", "maturity",
    "evidence_family",
)

METHOD_SPEC = """
ANYTIME EVIDENCE RECORD v1 (Science Trust addendum, locked 2026-08-10)

STATUS
Adjudication UNCOMPUTED. Enrollment machinery ACTIVE with ZERO
enrollments (honest-empty). PROSPECTIVE ONLY. Registered as an addendum
under SCIENCE TRUST PROTOCOL v1 (protocol be8b34040c2e), which named the
Anytime Evidence Record as a future component admissible only through
its own registered addendum with full method text. This is that
addendum; the full method is this text.

PURPOSE
Repeated observation of a registered hypothesis without peeking penalty:
evidence accumulates as an e-process whose validity holds at every
observation time simultaneously, so looking early, often, or
continuously never inflates error. No enrollment is ever retrofitted;
the record begins empty and grows only forward in time.

E-PROCESS METHOD (complete, deterministic, locked once for the family)
Each enrolled instrument declares at enrollment a bounded observation
transform mapping its raw observable into X_i in [0, 1] (fixed at
enrollment, never changed), a null mean m0 in (0, 1), and a direction
d in {greater, less}. The registered null is
  H0: E[X_i | F_{i-1}] <= m0        (direction greater), or
  H0: E[X_i | F_{i-1}] >= m0        (direction less),
where F_{i-1} is the natural filtration of the instrument's observation
sequence. Direction less is reduced to direction greater by the exact
substitution X_i -> 1 - X_i, m0 -> 1 - m0; everything below is stated
for direction greater.

Betting grid (fixed): K = 20 bets,
  lambda_k = k / ((K + 1) * m0),   k = 1..K,
so every lambda_k lies strictly inside [0, 1/m0) and each per-bet payoff
1 + lambda_k * (X_i - m0) is strictly positive for X_i in [0, 1].

Per-bet wealth (test martingale under H0, W_0 = 1):
  W_t(lambda_k) = product over i = 1..t of (1 + lambda_k * (X_i - m0)).

E-value (mixture e-process, E_0 = 1):
  E_t = (1/K) * sum over k = 1..K of W_t(lambda_k).
Under H0 each W(lambda_k) is a nonnegative supermartingale with initial
value 1, hence so is the mixture; by Ville's inequality
  P_H0( exists t : E_t >= 1/alpha ) <= alpha.
The update is exact, deterministic, and closed-form; observation at
every cadence tick carries ZERO peeking penalty. alpha = 0.05, locked.

STATE THRESHOLDS (locked)
  theta_supported = 1/alpha = 20;  theta_weak = 5.

STATE MACHINE (evaluated deterministically at each cadence tick, rules
in order, first match wins)
  REGISTERED            — before the enrollment's start_time.
  terminal-invalidation — if any declared invalidation condition has
      fired: the state is the condition's declared mapping, exactly one
      of INCONCLUSIVE (a dependency assumption failed during
      observation, data on record) or NOT_IDENTIFIABLE (the condition
      shows the registered null/parameters were never observable or
      identifiable as registered). The mapping of every invalidation
      condition to one of these two states is declared AT ENROLLMENT;
      assumption failure therefore maps deterministically. Terminal.
  MATURE                — the declared maturity condition is met AND the
      declared stopping/decision policy triggers its terminal read: the
      terminal e-value is frozen and the instrument's matured PRIMARY
      endpoint is handed to its declared discovery family for
      family-level adjudication under Discovery Ledger v1 (BH within
      family at the family's declared q). Terminal.
  SUPPORTED             — E_t >= theta_supported and maturity met.
  SUPPORTED_NOT_MATURE  — E_t >= theta_supported and maturity not met.
  WEAK                  — theta_weak <= E_t < theta_supported.
  ACCUMULATING          — E_t < theta_weak.
WEAK and SUPPORTED are reversible into each other (current-wealth
semantics); the running maximum e-value and the first tick crossing
theta_supported are recorded in the instrument's lineage and never
erased. Progression REGISTERED -> ACCUMULATING -> WEAK <-> SUPPORTED ->
SUPPORTED_NOT_MATURE -> MATURE; INCONCLUSIVE / NOT_IDENTIFIABLE reachable
from any observing state by invalidation. All states are research-state
axis ONLY (schema-gate S6, both directions): never signal labels, score
labels, trading classifications, buy/sell fields, or portfolio actions.

ENROLLMENT RULE (the A-1 pattern applied to instances)
The METHOD is locked here, once. No instrument observes under it until
that instrument's own enrollment line is registered in the canonical
chain (kind = anytime_enrollment), BEFORE its own observation starts,
carrying ALL of: enrollment_id; instrument; registered_null (with m0
and direction); parameters (including the bounded observation
transform); enrolled_at (UTC, stamped at registration); start_time
(UTC); observation_cadence; stopping_policy (stopping/decision policy);
dependency_assumptions; invalidation_conditions (each with its declared
INCONCLUSIVE / NOT_IDENTIFIABLE mapping); maturity (condition);
evidence_family (its discovery family, declared at enrollment per
Discovery Ledger v1). A missing required field is REFUSED.

PROSPECTIVE-ONLY GUARD (in-hash, enforced twice)
  1. At enrollment: start_time must be >= enrolled_at, and enrolled_at
     is stamped by the registrar at call time — any historical start is
     REFUSED at the call.
  2. Forever after: the chain gate re-verifies start_time >= enrolled_at
     on every enrollment line and refuses the chain otherwise.
Nothing is ever retrofitted. The Sept 1 reversal read and all existing
registered reads stay untouched by this component: no existing
protocol, run, verdict, or read is enrolled, re-scored, or re-described
by this registration.

DERIVED ARTIFACT
registry/anytime_record.json — derived deterministically from the
canonical chain (enrollment lines only; ZERO at registration); NEVER
hand-maintained; no wall-clock timestamp; derivation anchor = chain tip
hash, so the same chain always yields byte-identical output.

GATES (active from registration; chain-gate exit 46)
ANYTIME-PROSPECTIVE — any enrollment line (or on-disk record entry)
  with start_time earlier than enrolled_at fails the chain.
ANYTIME-SCHEMA — any enrollment line (or on-disk record entry) missing
  a required field fails the chain.
ANYTIME-RECONCILIATION — the on-disk artifact must equal the
  chain-derived rebuild byte-for-byte.
All fail closed: a missing artifact, an unregistered spec, or an
unparseable chain is a failure, not a skip.

COMPUTE DISCIPLINE
Registered with zero research computation, zero enrollments, zero
observations, zero e-values on real data, zero signal/score/N_eff
changes, zero public page changes, zero version bump. The e-process
update may be exercised only on synthetic self-test data until an
enrolled instrument's own observation window opens. Any edit to this
spec changes its hash and therefore requires supersession in the
registry — never amendment.
"""

PARAMS = {
    "alpha": ALPHA,
    "theta_supported": THETA_SUPPORTED,
    "theta_weak": THETA_WEAK,
    "grid_K": GRID_K,
    "states": 8,
    "enrollment_required_fields": len(ENROLLMENT_REQUIRED),
}
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]


def _registry(path: Path = CHAIN):
    import sys
    if str(_REPO / "tools") not in sys.path:
        sys.path.insert(0, str(_REPO / "tools"))
    from yuclaw_protocol_registry import Registry
    return Registry(str(path))


# ------------------------------------------------------------- e-process
def e_update(e_wealth: list, x: float, m0: float) -> tuple:
    """One exact e-process update (direction greater; pure function).
    e_wealth: per-bet wealth list of length GRID_K (all 1.0 at t=0).
    Returns (new_wealth_list, mixture_e_value)."""
    if not (0.0 <= x <= 1.0):
        raise ValueError(f"observation {x} outside [0,1] — the bounded "
                         f"transform is part of the enrollment")
    if not (0.0 < m0 < 1.0):
        raise ValueError(f"m0 {m0} outside (0,1)")
    new = [w * (1.0 + (k / ((GRID_K + 1) * m0)) * (x - m0))
           for k, w in zip(range(1, GRID_K + 1), e_wealth)]
    return new, sum(new) / GRID_K


def state_of(e_value: float, maturity_met: bool,
             invalidated: str | None = None,
             stopped: bool = False, started: bool = True) -> str:
    """Deterministic state from the locked thresholds (rules in order)."""
    if not started:
        return "REGISTERED"
    if invalidated is not None:
        if invalidated not in ("INCONCLUSIVE", "NOT_IDENTIFIABLE"):
            raise ValueError(f"invalidation maps only to INCONCLUSIVE or "
                             f"NOT_IDENTIFIABLE, got {invalidated!r}")
        return invalidated
    if maturity_met and stopped:
        return "MATURE"
    if e_value >= THETA_SUPPORTED:
        return "SUPPORTED" if maturity_met else "SUPPORTED_NOT_MATURE"
    if e_value >= THETA_WEAK:
        return "WEAK"
    return "ACCUMULATING"


# ------------------------------------------------------------ enrollment
def _check_enrollment_payload(p: dict) -> list:
    """Deterministic payload checks shared by enroll() and the gate."""
    problems = []
    for f in ENROLLMENT_REQUIRED:
        if f not in p or p[f] in (None, "", [], {}):
            problems.append(f"missing required field '{f}'")
    if "enrolled_at" in p and "start_time" in p:
        try:
            t0 = datetime.fromisoformat(str(p["enrolled_at"]))
            t1 = datetime.fromisoformat(str(p["start_time"]))
            if t1 < t0:
                problems.append(
                    f"start_time {p['start_time']} earlier than "
                    f"enrolled_at {p['enrolled_at']} — historical starts "
                    f"are refused (prospective-only)")
        except ValueError as exc:
            problems.append(f"unparseable enrollment time ({exc})")
    for c in (p.get("invalidation_conditions") or []):
        if not isinstance(c, dict) or c.get("maps_to") not in (
                "INCONCLUSIVE", "NOT_IDENTIFIABLE"):
            problems.append(
                "every invalidation condition must declare maps_to in "
                "{INCONCLUSIVE, NOT_IDENTIFIABLE}")
    return problems


def enroll(payload: dict, chain_path: Path = CHAIN) -> str:
    """Register one enrollment line — PROSPECTIVE ONLY, fail closed.
    Stamps enrolled_at at call time; refuses any historical start."""
    reg = _registry(chain_path)
    reg.assert_registered(PROTOCOL_ID)
    p = dict(payload)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    p["enrolled_at"] = now.isoformat()
    if not p.get("start_time"):
        # C-1 (order 2026-08-11): start_time = the actual registration
        # timestamp; first eligible observation is strictly after it.
        p["start_time"] = p["enrolled_at"]
    if "enrollment_id" not in p:
        p["enrollment_id"] = hashlib.sha256(
            f"{p.get('instrument')}|{p.get('registered_null')}|"
            f"{p['enrolled_at']}".encode()).hexdigest()[:12]
    try:
        start = datetime.fromisoformat(str(p.get("start_time")))
    except (TypeError, ValueError):
        raise ValueError("REFUSED: unparseable or missing start_time")
    if start < now:
        raise ValueError(
            f"REFUSED (prospective-only): start_time {p['start_time']} is "
            f"earlier than enrollment registration time "
            f"{p['enrolled_at']} — historical starts are never enrolled; "
            f"nothing is retrofitted")
    problems = _check_enrollment_payload(p)
    if problems:
        raise ValueError("REFUSED: " + "; ".join(problems))
    line_hash = reg._append(ENROLLMENT_KIND, p)
    write_record(chain_path)
    return line_hash


# ---------------------------------------------------------------- record
def build_record(chain_path: Path = CHAIN) -> dict:
    """Derive the record from the canonical chain. Counting only."""
    reg = _registry(chain_path)          # verifies the chain on load
    reg.assert_registered(PROTOCOL_ID)   # fail closed
    enrollments = [dict(l["payload"], chain_line=i)
                   for i, l in enumerate(reg._lines, start=1)
                   if l["kind"] == ENROLLMENT_KIND]
    return {
        "spec": {
            "name": "Anytime Evidence Record v1 (Science Trust addendum)",
            "protocol_id": PROTOCOL_ID,
            "method_hash": METHOD_HASH,
            "umbrella_protocol_id": UMBRELLA_PROTOCOL_ID,
            "adjudication_state": "UNCOMPUTED",
            "enrollment_machinery": "ACTIVE",
            "prospective_only": True,
            "derivation_anchor_chain_tip": reg._tip(),
            "chain_lines": len(reg._lines),
        },
        "thresholds": {"alpha": ALPHA, "theta_supported": THETA_SUPPORTED,
                       "theta_weak": THETA_WEAK, "grid_K": GRID_K},
        "enrollment_count": len(enrollments),
        "enrollments": enrollments,
        "note": ("zero enrollments at registration — honest-empty, like "
                 "the leaderboard; every future instrument enrolls its "
                 "own line BEFORE its observation starts; historical "
                 "starts are refused"),
    }


def write_record(chain_path: Path = CHAIN,
                 out_path: Path = RECORD_PATH) -> dict:
    rec = build_record(chain_path)
    out_path.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    return rec


def adjudicate(*_a, **_k):
    """Terminal adjudication is UNCOMPUTED — a MATURE instrument hands
    its frozen e-value to its discovery family's registered read."""
    raise NotImplementedError(
        f"Anytime Evidence Record v1 adjudication is UNCOMPUTED "
        f"(protocol {PROTOCOL_ID}, method {METHOD_HASH}). Terminal "
        f"reads happen only through each instrument's declared stopping "
        f"policy and its family's registered read; enrollment is the "
        f"only active surface, and the record currently holds zero "
        f"enrollments.")


def _selftest():
    """Synthetic-only method check; touches no real data."""
    w = [1.0] * GRID_K
    e = 1.0
    for x in (0.9, 0.8, 1.0, 0.7, 0.95, 0.85, 1.0, 0.9):
        w, e = e_update(w, x, 0.5)
    assert e > THETA_SUPPORTED, f"synthetic high-signal e-value {e}"
    assert state_of(e, maturity_met=False) == "SUPPORTED_NOT_MATURE"
    assert state_of(e, maturity_met=True) == "SUPPORTED"
    w2, e2 = [1.0] * GRID_K, 1.0
    for x in (0.5, 0.4, 0.6, 0.5, 0.45, 0.55):
        w2, e2 = e_update(w2, x, 0.5)
    assert e2 < THETA_WEAK, f"synthetic null e-value {e2}"
    assert state_of(e2, maturity_met=False) == "ACCUMULATING"
    assert state_of(1.0, False, invalidated="NOT_IDENTIFIABLE") == \
        "NOT_IDENTIFIABLE"
    assert state_of(25.0, True, stopped=True) == "MATURE"
    assert state_of(0.0, False, started=False) == "REGISTERED"
    bad = _check_enrollment_payload({"enrolled_at": "2026-08-10T00:00:00",
                                     "start_time": "2026-08-01T00:00:00"})
    assert any("historical starts are refused" in b for b in bad)
    return e, e2


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        rec = write_record()
        print(f"[anytime-record] wrote {RECORD_PATH} — "
              f"{rec['enrollment_count']} enrollments (honest-empty at "
              f"registration)")
    elif "--selftest" in sys.argv:
        e_hi, e_lo = _selftest()
        print(f"[anytime-record] selftest OK (synthetic only): "
              f"high-signal e={e_hi:.1f} > {THETA_SUPPORTED}, "
              f"null e={e_lo:.2f} < {THETA_WEAK}, state machine + "
              f"prospective refusal verified")
    else:
        print(f"[anytime-record] METHOD_HASH={METHOD_HASH} · "
              f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · "
              f"adjudication UNCOMPUTED · enrollment ACTIVE · "
              f"0 enrollments (honest-empty) · PROSPECTIVE ONLY")
