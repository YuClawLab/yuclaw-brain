"""Registered arithmetic for brief statements, on top of v8's exact Decimal money module.

v8 refuses every inexact result. A relative change is inexact by nature (−5 / 115 × 100 = −4.347826…), so it is the one
place where rounding exists in the product, and it is therefore EXPLICIT: the record carries the exact ratio as a fraction
of integers, the rounding rule and the number of decimals, and the verifier recomputes it from the typed inputs. Every
calculation record also carries the financial scope (currency, unit, scale, basis, fiscal period, metric) its inputs
belong to; a change of any of them makes the record inapplicable — it is never silently re-used across scopes.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from v3.receipts.contracts import ContractError, digest
from v8.workbench import calc, money

CALCULATOR = "v9.brief.finance/1 over v8.workbench.calc/1"
ROUNDING = {"rule": "ROUND_HALF_EVEN", "decimals": 2, "applies_to": "relative change in percent only; every amount, midpoint and difference is exact"}
SCOPE_FIELDS = ("metric", "currency", "unit", "scale_as_stated", "basis", "fiscal_period")
SCALE_WORD = {"en": {"units": "", "thousands": "thousand", "millions": "million", "billions": "billion"},
              "fr": {"units": "", "thousands": "milliers", "millions": "millions", "billions": "milliards"}}


def scope_of(claim: dict) -> dict:
    return {k: claim[k] for k in SCOPE_FIELDS}


def scope_digest(claim: dict) -> str:
    return digest(scope_of(claim))


def same_scope(a: dict, b: dict) -> tuple[bool, list[str]]:
    reasons = [f"{k}: {a.get(k)!r} vs {b.get(k)!r}" for k in SCOPE_FIELDS if a.get(k) != b.get(k)]
    return (not reasons), reasons


def in_scale(amount: Decimal, scale: str) -> str:
    """Exact rendering of an amount in its stated scale (refuses an inexact division): 110000000, millions → '110'."""
    q = money.exact(lambda: amount / money.SCALE_FACTOR[scale])
    return format(q.normalize(), "f") if q != 0 else "0"


def relative_change(old: Decimal, new: Decimal) -> dict:
    """(new − old) / old × 100 with the explicit rounding rule; the exact ratio travels as integers."""
    if old == 0:
        raise ContractError("relative change undefined for a zero base")
    delta = money.delta(new, old)
    with localcontext() as ctx:
        ctx.prec = 40
        exact_pct = (delta / old) * Decimal(100)
        rounded = exact_pct.quantize(Decimal(1).scaleb(-ROUNDING["decimals"]), rounding=ROUND_HALF_EVEN)
    return {"numerator": money.to_json(delta), "denominator": money.to_json(old), "formula": "(new - old) / old * 100",
            "value_percent": format(rounded, "f"), "approximate": format(rounded, "f") != format(exact_pct.normalize(), "f"), "rounding": dict(ROUNDING)}


def guidance_change_record(original: dict, revised: dict) -> dict:
    """The registered calculation behind a guidance-change statement: midpoints, absolute and relative change, in one scope."""
    ok, why = same_scope(original, revised)
    if not ok:
        raise ContractError("guidance change not computable across scopes: " + "; ".join(why))
    lo1, hi1 = money.parse_amount(original["range"]["low"]), money.parse_amount(original["range"]["high"])
    lo2, hi2 = money.parse_amount(revised["range"]["low"]), money.parse_amount(revised["range"]["high"])
    m1, m2 = money.midpoint(lo1, hi1), money.midpoint(lo2, hi2)
    rec = {"calculator": CALCULATOR, "kind": "guidance_change", "scope": scope_of(original),
           "inputs": {"original_low": money.to_json(lo1), "original_high": money.to_json(hi1), "revised_low": money.to_json(lo2), "revised_high": money.to_json(hi2)},
           "formula": "midpoint = (low + high) / 2 (exact); absolute_change = midpoint_revised - midpoint_original (exact); relative_change = absolute_change / midpoint_original * 100 (rounded as stated)",
           "midpoint_original": money.to_json(m1), "midpoint_revised": money.to_json(m2), "absolute_change": money.to_json(money.delta(m2, m1)),
           "relative_change": relative_change(m1, m2), "no_inference": calc.NO_INFERENCE}
    rec["record_id"] = digest(rec)
    return rec


def containment_record(version: dict, outcome: dict, *, label: str) -> dict:
    """One range against the disclosed actual, through v8's evaluator (the same result the claim page shows)."""
    ev = calc.evaluate_version(version, outcome, label=label)
    rec = {"calculator": CALCULATOR, "kind": "containment", "label": label, "scope": scope_of(version), "v8_evaluation": ev,
           "inputs": {"low": ev["inputs"]["low"], "high": ev["inputs"]["high"], "actual": ev["inputs"]["actual"]},
           "formula": calc.FORMULA, "result": ev["result"], "contains": ev["contains"], "no_inference": calc.NO_INFERENCE}
    rec["record_id"] = digest(rec)
    return rec


def comparison_record(original: dict, revised: dict) -> dict:
    cmp = calc.compare_versions(original, revised)
    rec = {"calculator": CALCULATOR, "kind": "range_comparison", "scope": scope_of(original), "v8_comparison": cmp,
           "inputs": {"original": original["range"], "revised": revised["range"]}, "formula": "low_delta = low_b - low_a; high_delta = high_b - high_a; width = high - low; overlap = [max(lows), min(highs)] when non-empty",
           "result": cmp["result"], "no_inference": calc.NO_INFERENCE}
    rec["record_id"] = digest(rec)
    return rec


def recompute(rec: dict) -> tuple[str, str | None]:
    """Re-derive a calculation record from its typed inputs. Returns (outcome, detail): VERIFIED when the recomputation
    reproduces the record's values, FAILED when it does not, NOT_RECOMPUTABLE when inputs were withheld, UNSUPPORTED for an
    unknown kind."""
    try:
        kind = rec.get("kind"); inp = rec.get("inputs") or {}
        if any(v is None for v in inp.values()):
            return "NOT_RECOMPUTABLE", "a required input was withheld from this record"
        if kind == "guidance_change":
            lo1, hi1, lo2, hi2 = (money.parse_amount(inp[k]) for k in ("original_low", "original_high", "revised_low", "revised_high"))
            m1, m2 = money.midpoint(lo1, hi1), money.midpoint(lo2, hi2)
            rc = relative_change(m1, m2)
            same = (money.to_json(m1) == rec.get("midpoint_original") and money.to_json(m2) == rec.get("midpoint_revised")
                    and money.to_json(money.delta(m2, m1)) == rec.get("absolute_change") and rc["value_percent"] == (rec.get("relative_change") or {}).get("value_percent")
                    and rc["numerator"] == (rec.get("relative_change") or {}).get("numerator") and rc["denominator"] == (rec.get("relative_change") or {}).get("denominator"))
            return ("VERIFIED", None) if same else ("FAILED", "recomputed midpoints or relative change differ from the record")
        if kind == "containment":
            lo, hi, actual = money.parse_amount(inp["low"]), money.parse_amount(inp["high"]), money.parse_amount(inp["actual"])
            inside = money.contains(lo, hi, actual)
            return ("VERIFIED", None) if inside == rec.get("contains") and rec.get("result") == ("IN_RANGE" if inside else "OUT_OF_RANGE") else ("FAILED", "recomputed containment differs from the record")
        if kind == "range_comparison":
            a, b = inp["original"], inp["revised"]
            al, ah, bl, bh = (money.parse_amount(x) for x in (a["low"], a["high"], b["low"], b["high"]))
            cmp = rec.get("v8_comparison") or {}
            same = (money.to_json(money.delta(bl, al)) == cmp.get("low_delta") and money.to_json(money.delta(bh, ah)) == cmp.get("high_delta")
                    and money.to_json(money.width(al, ah)) == cmp.get("width_a") and money.to_json(money.width(bl, bh)) == cmp.get("width_b"))
            return ("VERIFIED", None) if same else ("FAILED", "recomputed deltas or widths differ from the record")
        return "UNSUPPORTED", f"calculation kind {kind!r} is not known to this verifier"
    except (ContractError, KeyError, TypeError, ValueError) as exc:
        return "FAILED", f"recomputation raised {exc.__class__.__name__}: {exc}"
