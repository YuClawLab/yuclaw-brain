"""Universe ladder — parameterized membership/admission VALIDATION on fixtures (v7 P1; no live admission).

Each rung (U150, U250, U350, U550) is validated on ITS OWN candidate set with the six constitution gates
parameterized by the rung (identity integrity, price availability ≥ 252 sessions, liquidity thresholds, evidence
substrate, shadow-run requirement before Phase B, cross-sectional fit disclosure). A rung never inherits a
smaller rung's green state. Exclusion reasons are explicit per name. Capacity and shadow-run inputs are
supplied records (a missing record is UNKNOWN, never inferred). Nothing here reads research rows, writes the
canonical or shadow schema, or promotes anything."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

RUNGS = (150, 250, 350, 550)
GATES = ("G1_IDENTITY", "G2_PRICE", "G3_LIQUIDITY", "G4_SUBSTRATE", "G5_SHADOW_RUN", "G6_CROSS_SECTIONAL_FIT")
MIN_SESSIONS = 252
# Vocabulary of per-name NON-ADMISSION outcomes for FIXTURE validation. This module never filters real data: real
# admission exclusions are governed by the registered admission protocol and the truncation ledger's allowlist
# (tools/yuclaw_u350_admission.py); nothing here is a data cap or a live filter.
NON_ADMISSION_REASONS = ("DUPLICATE_TICKER", "MISSING_CIK", "PRICE_HISTORY_SHORT", "LIQUIDITY_BELOW_THRESHOLD", "NO_SUBSTRATE_PATH", "EVIDENCE_TIER_STOP", "CANONICAL_OVERLAP")


@dataclass
class RungParams:
    target: int
    min_adv_usd: float                    # liquidity threshold (rung-specific; supplied, never guessed)
    min_sessions: int = MIN_SESSIONS
    families_required: tuple = ("filings",)


@dataclass
class RungResult:
    target: int
    candidates: int
    admitted: int
    excluded: dict = field(default_factory=dict)          # ticker → [reasons]
    gates: dict = field(default_factory=dict)             # gate → PASS/FAIL/DISCLOSED/MISSING
    shadow_run: dict = field(default_factory=dict)
    capacity: dict = field(default_factory=dict)
    fit: dict = field(default_factory=dict)
    ready: bool = False
    reasons_not_ready: list = field(default_factory=list)


def validate_candidates(cands: list[dict], p: RungParams, *, canonical: set[str], evidence_only: set[str]) -> tuple[list[str], dict]:
    """Per-name admission under the parameterized gates; returns (admitted tickers, exclusions)."""
    excluded: dict[str, list[str]] = {}
    seen = {}
    for c in cands:
        t = c.get("ticker"); r = []
        if not isinstance(t, str) or not t or t in seen:
            r.append("DUPLICATE_TICKER")
        seen[t] = True
        if not c.get("cik"):
            r.append("MISSING_CIK")
        if int(c.get("price_sessions", 0)) < p.min_sessions:
            r.append("PRICE_HISTORY_SHORT")
        if float(c.get("adv_usd", 0.0)) < p.min_adv_usd:
            r.append("LIQUIDITY_BELOW_THRESHOLD")
        fams = set(c.get("substrate_families", []))
        if not set(p.families_required) <= fams:
            r.append("NO_SUBSTRATE_PATH")
        if t in evidence_only:
            r.append("EVIDENCE_TIER_STOP")                # scoring an evidence-only name is a STOP condition
        if t in canonical:
            r.append("CANONICAL_OVERLAP")                 # canonical names are not shadow additions
        if r:
            excluded[t] = r
    admitted = [c["ticker"] for c in cands if c.get("ticker") not in excluded]
    return admitted, excluded


def validate_rung(p: RungParams, cands: list[dict], *, canonical: set[str], evidence_only: set[str], shadow_run: dict | None, capacity: dict | None, fit: dict | None,
                  registered_window: dict | None, promotion_record: dict | None, phase_c_protocol_id: str | None) -> RungResult:
    admitted, excluded = validate_candidates(cands, p, canonical=canonical, evidence_only=evidence_only)
    res = RungResult(target=p.target, candidates=len(cands), admitted=len(admitted), excluded=excluded)
    res.gates = {"G1_IDENTITY": "PASS" if not any("DUPLICATE_TICKER" in r or "MISSING_CIK" in r for r in excluded.values()) else "FAIL_FOR_EXCLUDED",
                 "G2_PRICE": "PASS" if not any("PRICE_HISTORY_SHORT" in r for r in excluded.values()) else "FAIL_FOR_EXCLUDED",
                 "G3_LIQUIDITY": "PASS" if not any("LIQUIDITY_BELOW_THRESHOLD" in r for r in excluded.values()) else "FAIL_FOR_EXCLUDED",
                 "G4_SUBSTRATE": "PASS" if not any("NO_SUBSTRATE_PATH" in r for r in excluded.values()) else "FAIL_FOR_EXCLUDED"}
    # G5: a shadow run for THIS rung (target-specific record); never inherited
    if shadow_run and shadow_run.get("target") == p.target and shadow_run.get("days_observed", 0) > 0:
        res.shadow_run = {"status": "OBSERVED", **shadow_run}; res.gates["G5_SHADOW_RUN"] = "PASS" if shadow_run.get("anomaly_days", 0) == 0 else "OBSERVED_WITH_ANOMALIES"
    else:
        res.shadow_run = {"status": "MISSING", "note": f"no shadow run recorded for target {p.target}"}; res.gates["G5_SHADOW_RUN"] = "MISSING"
    # G6: disclosure-triggering, never exclusion
    res.fit = {"status": "DISCLOSED" if fit and fit.get("target") == p.target else "NOT_ASSESSED", **({k: v for k, v in (fit or {}).items()} if fit and fit.get("target") == p.target else {})}
    res.gates["G6_CROSS_SECTIONAL_FIT"] = "DISCLOSED" if res.fit["status"] == "DISCLOSED" else "MISSING"
    # capacity: supplied audit record for THIS rung, else UNKNOWN
    if capacity and capacity.get("target") == p.target and isinstance(capacity.get("gpu_h_per_day"), (int, float)):
        res.capacity = {"status": "MEASURED" if capacity.get("measured") else "INFERRED", "gpu_h_per_day": capacity["gpu_h_per_day"], "ceiling_gpu_h": capacity.get("ceiling_gpu_h")}
        if capacity.get("ceiling_gpu_h") is not None:
            res.capacity["within_ceiling"] = capacity["gpu_h_per_day"] <= capacity["ceiling_gpu_h"]
    else:
        res.capacity = {"status": "UNKNOWN", "note": f"no capacity record for target {p.target}"}
    short = max(0, p.target - len(canonical) - len(admitted))
    if short > 0: res.reasons_not_ready.append(f"admitted names short of target by {short}")
    if res.gates["G5_SHADOW_RUN"] != "PASS": res.reasons_not_ready.append("shadow run for this rung missing or anomalous")
    if res.capacity.get("within_ceiling") is not True: res.reasons_not_ready.append("capacity not measured within ceiling for this rung")
    if not registered_window: res.reasons_not_ready.append("no registered observation window")
    if not promotion_record: res.reasons_not_ready.append("no promotion decision")
    if not phase_c_protocol_id: res.reasons_not_ready.append("no registered Phase-C protocol")
    res.ready = not res.reasons_not_ready
    return res


def validate_ladder(fixture: dict) -> dict:
    """Exercise the FULL ladder on a fixture: {'canonical': [...], 'evidence_only': [...], 'rungs': {'150': {'params': {...}, 'candidates': [...], 'shadow_run': {...}|None,
    'capacity': {...}|None, 'fit': {...}|None, 'registered_window': ..., 'promotion_record': ..., 'phase_c_protocol_id': ...}, ...}}"""
    canonical = set(fixture.get("canonical", [])); evidence_only = set(fixture.get("evidence_only", []))
    out = {}
    for target in RUNGS:
        r = fixture.get("rungs", {}).get(str(target))
        if r is None:
            out[str(target)] = {"target": target, "status": "NO_FIXTURE", "note": "this rung has no candidate set; nothing is inherited from a smaller rung"}; continue
        params = RungParams(target=target, **{k: v for k, v in r.get("params", {}).items() if k in ("min_adv_usd", "min_sessions", "families_required")})
        res = validate_rung(params, r.get("candidates", []), canonical=canonical, evidence_only=evidence_only, shadow_run=r.get("shadow_run"), capacity=r.get("capacity"), fit=r.get("fit"),
                            registered_window=r.get("registered_window"), promotion_record=r.get("promotion_record"), phase_c_protocol_id=r.get("phase_c_protocol_id"))
        out[str(target)] = {"status": "VALIDATED", **asdict(res)}
    return {"ladder": out, "note": "fixture validation only: no live admission, promotion, threshold change or research read; each rung carries its own evidence"}
