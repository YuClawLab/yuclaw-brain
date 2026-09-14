"""Contribution anatomy reader/validator (v7 P2). Descriptive arithmetic only: for one why-JSON
(`components` = per-component scores, `score` = published composite rounded to 4 dp) and a supplied anatomy
input (`weights`, `confidence`, `gates`), contribution_i = score_i × confidence_i × weight_i (rounded to 6 dp);
a gated component is listed with contribution 0 and its gate reason; Σ contribution must reconcile with the
published composite up to the schema's rounding (4 dp). Negative values are allowed. Mismatches are reported per
component and for the total. No causal language, no new all-universe result, no scientific read."""
from __future__ import annotations

import math

PARTS_DP = 6
COMPOSITE_DP = 4


class AnatomyError(ValueError):
    pass


def _num(v, field):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, float) and not math.isfinite(v)):
        raise AnatomyError(f"{field}: finite number required")
    return float(v)


def decompose(why: dict, anatomy_input: dict) -> dict:
    """Build the per-component contribution table from a why-JSON and the supplied weights/confidence/gates."""
    if not isinstance(why, dict) or not isinstance(why.get("components"), dict) or "score" not in why:
        raise AnatomyError("why-JSON: {components: {id: score}, score} required")
    comps = why["components"]; composite = _num(why["score"], "score")
    w = anatomy_input.get("weights", {}); c = anatomy_input.get("confidence", {}); g = anatomy_input.get("gates", {})
    if set(w) != set(comps) or set(c) != set(comps):
        raise AnatomyError("weights and confidence must cover exactly the why-JSON components")
    rows = []
    for cid in sorted(comps):
        s = _num(comps[cid], f"components.{cid}"); wi = _num(w[cid], f"weights.{cid}"); ci = _num(c[cid], f"confidence.{cid}")
        if not (0.0 <= ci <= 1.0):
            raise AnatomyError(f"confidence.{cid}: 0..1 required")
        gate = g.get(cid)
        if gate is not None and (not isinstance(gate, str) or not gate.strip()):
            raise AnatomyError(f"gates.{cid}: reason text required")
        gated = gate is not None or wi == 0.0
        contribution = 0.0 if gated else round(s * ci * wi, PARTS_DP)
        rows.append({"component": cid, "score": s, "confidence": ci, "weight": wi, "gated": gated, "gate_reason": gate if gate is not None else ("zero weight" if wi == 0.0 else None), "contribution": contribution})
    total = round(sum(r["contribution"] for r in rows), PARTS_DP)
    return {"schema": "ContributionAnatomy.v1-candidate", "composite_published": composite, "contributions": rows, "sum_of_contributions": total,
            "meaning": "arithmetic share of a classification score; not an attribution of any market outcome"}


def reconcile(anatomy: dict, tolerance: float | None = None) -> dict:
    """Rounding reconciliation: |Σ contributions − composite| must be within half a unit of the composite's last
    published digit plus accumulated part rounding. Reports mismatches per component when the anatomy carries
    `expected_contributions` (e.g. a previously published table)."""
    n = len(anatomy["contributions"]); tol = tolerance if tolerance is not None else (0.5 * 10 ** -COMPOSITE_DP + n * 0.5 * 10 ** -PARTS_DP)
    diff = anatomy["sum_of_contributions"] - anatomy["composite_published"]
    mismatches = []
    for r in anatomy["contributions"]:
        if r["gated"] and r["contribution"] != 0.0:
            mismatches.append({"component": r["component"], "kind": "gated-nonzero", "contribution": r["contribution"]})
    exp = anatomy.get("expected_contributions") or {}
    for cid, v in exp.items():
        got = next((r["contribution"] for r in anatomy["contributions"] if r["component"] == cid), None)
        if got is None:
            mismatches.append({"component": cid, "kind": "unknown-component"})
        elif abs(got - float(v)) > 0.5 * 10 ** -PARTS_DP:
            mismatches.append({"component": cid, "kind": "contribution-mismatch", "expected": float(v), "computed": got})
    ok = abs(diff) <= tol and not mismatches
    return {"reconciled": ok, "difference": round(diff, PARTS_DP), "tolerance": tol, "mismatches": mismatches,
            "verdict": "RECONCILED" if ok else ("TOTAL_MISMATCH" if abs(diff) > tol else "COMPONENT_MISMATCH")}
