"""Deterministic comparator and calculator — pure functions over validated claim versions and outcomes.

Nothing here reads a file, a clock or the network. Every result carries its inputs, the formula applied and
every reason for an unresolved state, so a reviewer can recompute it by hand. Two evaluations (original range
and revised range) are always reported separately: agreement between them is not evidence of improved accuracy.
"""
from __future__ import annotations

from v8.workbench import money
from v8.workbench.schema import RESOLUTION_RULES, parse_ts

CALCULATOR = "v8.workbench.calc/1"
RESULTS = ("IN_RANGE", "OUT_OF_RANGE", "PENDING_OUTCOME", "WITHDRAWN_BEFORE_OUTCOME", "INCOMPATIBLE_BASIS", "UNIT_MISMATCH",
           "PERIOD_MISMATCH", "METRIC_MISMATCH", "NOT_COMPARABLE_DECLARED", "UNSUPPORTED_RULE")
UNRESOLVED = RESULTS[2:]
FORMULA = "contains = low <= actual <= high; midpoint = (low + high) / 2 (exact); delta_vs_midpoint = actual - midpoint; distance_outside = actual - violated bound (0 inside)"
NO_INFERENCE = "the original-range and revised-range evaluations are reported separately; both being IN_RANGE (or agreeing in any way) is not evidence of improved accuracy, forecasting skill or causation"


def _period_eq(a: dict, b: dict) -> tuple[bool, str | None]:
    if a["label"] != b["label"]:
        return False, f"fiscal period label {a['label']!r} vs {b['label']!r}"
    if a.get("type") != b.get("type"):
        return False, f"fiscal period type {a.get('type')!r} vs {b.get('type')!r}"
    if (a["start"], a["end"]) != (b["start"], b["end"]):
        return False, f"fiscal period dates {a['start']}..{a['end']} vs {b['start']}..{b['end']}"
    return True, None


def compatibility(version: dict, outcome: dict) -> list[dict]:
    """Every mismatch between a claim version and an outcome, in resolution order. Empty list = comparable."""
    reasons = []
    if version["basis"] != outcome["basis"]:
        reasons.append({"code": "INCOMPATIBLE_BASIS", "reason": f"accounting basis {version['basis']!r} (claim) vs {outcome['basis']!r} (outcome)"})
    if version["unit"] != outcome["unit"] or version["currency"] != outcome["currency"]:
        reasons.append({"code": "UNIT_MISMATCH", "reason": f"unit/currency {version['unit']}/{version['currency']} (claim) vs {outcome['unit']}/{outcome['currency']} (outcome)"})
    same, why = _period_eq(version["fiscal_period"], outcome["fiscal_period"])
    if not same:
        reasons.append({"code": "PERIOD_MISMATCH", "reason": why})
    if version["metric"] != outcome["metric"]:
        reasons.append({"code": "METRIC_MISMATCH", "reason": f"metric {version['metric']!r} vs {outcome['metric']!r}"})
    if not reasons and outcome.get("comparable") is False:
        reasons.append({"code": "NOT_COMPARABLE_DECLARED", "reason": "the recorder declared the outcome not comparable; no field mismatch was found, so the declaration itself blocks resolution until explained"})
    return reasons


def evaluate_version(version: dict, outcome: dict | None, *, label: str) -> dict:
    """One range against one outcome. Never raises for a mismatch; returns the reasons instead."""
    low, high = money.parse_amount(version["range"]["low"]), money.parse_amount(version["range"]["high"])
    base = {"label": label, "version_digest": version.get("_digest"), "rule": version["resolution_rule"], "formula": FORMULA,
            "inputs": {"low": money.to_json(low), "high": money.to_json(high), "unit": version["unit"], "currency": version["currency"], "basis": version["basis"],
                       "fiscal_period": version["fiscal_period"], "metric": version["metric"], "scale_as_stated": version["scale_as_stated"],
                       "actual": None if outcome is None else outcome["actual"]},
            "source_links": {"claim_source": version["source"]["accession"], "outcome_source": None if outcome is None else outcome["source"]["accession"]}}
    if version["resolution_rule"] not in RESOLUTION_RULES:
        return dict(base, result="UNSUPPORTED_RULE", contains=None, midpoint=None, delta_vs_midpoint=None, distance_outside=None, reasons=[{"code": "UNSUPPORTED_RULE", "reason": version["resolution_rule"]}])
    if outcome is None:
        return dict(base, result="PENDING_OUTCOME", contains=None, midpoint=money.to_json(money.midpoint(low, high)), delta_vs_midpoint=None, distance_outside=None,
                    reasons=[{"code": "PENDING_OUTCOME", "reason": "no comparable outcome has been recorded; the claim stays unresolved"}])
    mism = compatibility(version, outcome)
    if mism:
        return dict(base, result=mism[0]["code"], contains=None, midpoint=money.to_json(money.midpoint(low, high)), delta_vs_midpoint=None, distance_outside=None, reasons=mism)
    actual = money.parse_amount(outcome["actual"])
    mid = money.midpoint(low, high)
    inside = money.contains(low, high, actual)
    return dict(base, result="IN_RANGE" if inside else "OUT_OF_RANGE", contains=inside, midpoint=money.to_json(mid),
                delta_vs_midpoint=money.to_json(money.delta(actual, mid)), delta_vs_low=money.to_json(money.delta(actual, low)), delta_vs_high=money.to_json(money.delta(actual, high)),
                distance_outside=money.to_json(money.distance_outside(low, high, actual)), reasons=[])


def compare_versions(a: dict, b: dict, *, a_label="original", b_label="revised") -> dict:
    """Side-by-side comparison of two claim versions. Comparable only when metric, currency, unit, basis and
    fiscal period are identical; otherwise INCOMPARABLE with every reason. Notes are the reviewer's, never proof."""
    reasons = []
    for f in ("metric", "currency", "unit", "basis"):
        if a[f] != b[f]:
            reasons.append({"field": f, "reason": f"{f} {a[f]!r} vs {b[f]!r}"})
    same, why = _period_eq(a["fiscal_period"], b["fiscal_period"])
    if not same:
        reasons.append({"field": "fiscal_period", "reason": why})
    al, ah = money.parse_amount(a["range"]["low"]), money.parse_amount(a["range"]["high"])
    bl, bh = money.parse_amount(b["range"]["low"]), money.parse_amount(b["range"]["high"])
    out = {"a": {"label": a_label, "range": a["range"], "digest": a.get("_digest")}, "b": {"label": b_label, "range": b["range"], "digest": b.get("_digest")},
           "comparable": not reasons, "result": "COMPARABLE" if not reasons else "INCOMPARABLE", "reasons": reasons}
    if reasons:
        return out
    lo_d, hi_d = money.delta(bl, al), money.delta(bh, ah)
    mid_d = money.delta(money.midpoint(bl, bh), money.midpoint(al, ah))
    w_a, w_b = money.width(al, ah), money.width(bl, bh)
    ov_lo, ov_hi = max(al, bl), min(ah, bh)
    if lo_d == 0 and hi_d == 0:
        direction = "UNCHANGED"
    elif lo_d <= 0 and hi_d <= 0:
        direction = "LOWERED"
    elif lo_d >= 0 and hi_d >= 0:
        direction = "RAISED"
    elif lo_d > 0 and hi_d < 0:
        direction = "NARROWED"
    elif lo_d < 0 and hi_d > 0:
        direction = "WIDENED"
    else:
        direction = "SHIFTED"
    out.update(low_delta=money.to_json(lo_d), high_delta=money.to_json(hi_d), midpoint_delta=money.to_json(mid_d), width_a=money.to_json(w_a), width_b=money.to_json(w_b),
               width_delta=money.to_json(money.delta(w_b, w_a)), overlap=None if ov_lo > ov_hi else {"low": money.to_json(ov_lo), "high": money.to_json(ov_hi)},
               direction=direction, unit=a["unit"], note="a structural comparison of two stated ranges; explanatory notes attached by a reviewer are not causal proof")
    return out


def adjudicate(state: dict) -> dict:
    """Deterministic resolution of a claim state:
      state = {"versions": [{"version_id","type","claim",...}], "withdrawn": {...}|None, "outcome": {...}|None}
    Returns the overall result plus the SEPARATE original-range and revised-range evaluations."""
    versions = state["versions"]
    if not versions:
        raise ValueError("no frozen version")
    original = versions[0]
    corrections = [v for v in versions if v["type"] == "CORRECTED_SOURCE"]
    original_eff = corrections[-1] if corrections else original
    revised = [v for v in versions if v["type"] == "REVISED"]
    current = revised[-1] if revised else original_eff
    outcome = state.get("outcome")
    withdrawn = state.get("withdrawn")
    res = {"calculator": CALCULATOR, "rule": current["claim"]["resolution_rule"], "rule_text": RESOLUTION_RULES.get(current["claim"]["resolution_rule"]),
           "original_version": original_eff["version_id"], "uses_corrected_range": bool(corrections), "current_version": current["version_id"],
           "revision_count": len(revised), "no_inference": NO_INFERENCE}
    if withdrawn is not None and (outcome is None or parse_ts(withdrawn["source"]["available_as_of"]) <= parse_ts(outcome["source"]["available_as_of"])):
        res.update(result="WITHDRAWN_BEFORE_OUTCOME", comparison_permitted=False, reasons=[{"code": "WITHDRAWN_BEFORE_OUTCOME", "reason": "the commitment was withdrawn before any comparable outcome was available; a withdrawal is not a miss"}],
                   original=evaluate_version(original_eff["claim"], None, label="original range"), revised=evaluate_version(current["claim"], None, label="revised range") if revised else None)
        return res
    if outcome is None:
        res.update(result="PENDING_OUTCOME", comparison_permitted=False, reasons=[{"code": "PENDING_OUTCOME", "reason": "no outcome recorded; unresolved"}],
                   original=evaluate_version(original_eff["claim"], None, label="original range"), revised=evaluate_version(current["claim"], None, label="revised range") if revised else None)
        return res
    o_eval = evaluate_version(original_eff["claim"], outcome, label="original range")
    r_eval = evaluate_version(current["claim"], outcome, label="revised range") if revised else None
    cur_eval = r_eval or o_eval
    if cur_eval["result"] in UNRESOLVED:
        res.update(result=cur_eval["result"], comparison_permitted=False, reasons=cur_eval["reasons"], original=o_eval, revised=r_eval)
        return res
    res.update(result=cur_eval["result"], comparison_permitted=True, reasons=[], original=o_eval, revised=r_eval,
               original_contains_actual=o_eval["contains"], revised_contains_actual=None if r_eval is None else r_eval["contains"],
               delta_vs_original_midpoint=o_eval["delta_vs_midpoint"], delta_vs_revised_midpoint=None if r_eval is None else r_eval["delta_vs_midpoint"])
    if withdrawn is not None:
        res["reasons"].append({"code": "WITHDRAWN_AFTER_OUTCOME", "reason": "a withdrawal was recorded after the outcome became available; shown, not applied"})
    return res


def state_from_fixture_records(rec: dict) -> dict:
    """Build a calc state from schema.from_fixture output (no store involved)."""
    from v8.workbench.schema import claim_digest
    versions = [{"version_id": "V1", "type": "FROZEN", "claim": dict(rec["claim"], _digest=claim_digest(rec["claim"]))}]
    withdrawn = None
    for r in rec["revisions"]:
        if r["type"] == "WITHDRAWN":
            withdrawn = {"revision_id": r["revision_id"], "source": r["source"], "reason": r["reason"]}
        else:
            versions.append({"version_id": r["revision_id"], "type": r["type"], "claim": dict(r["claim"], _digest=claim_digest(r["claim"]))})
    return {"versions": versions, "withdrawn": withdrawn, "outcome": rec["outcome"]}
