"""Phase 6 · A2 estimand requirements — typed requirements/validation INTERFACE (v7).

What is validated: the designation of S (the pooled statistic), the event set, units, weights, the horizon, the
variance basis, the rule-4 disposition and incident dependencies. What is NOT done: no numeric N_eff, no
formula labelled "derived", no inference from edges/components alone. A requirement that source metadata cannot
supply is labelled UNRESOLVED for that specific input; the interface reports which inputs block a designation."""
from __future__ import annotations

import math

UNITS = ("bps", "pct", "log-return", "count")
VARIANCE_BASES = ("cluster-robust", "hac", "iid", "block-bootstrap")
RULE4 = ("APPLIED", "NOT_APPLIED", "UNRESOLVED")
HORIZON_UNITS = ("sessions", "calendar-days")


class A2Error(ValueError):
    pass


def validate_requirements(req: dict) -> dict:
    """Returns {'status': 'DESIGNATED'|'UNRESOLVED', 'unresolved': [...], 'requirements': {...normalized...}}. Raises A2Error
    only for incompatible or malformed inputs (unit mismatch, unsupported variance basis, non-positive horizon)."""
    if not isinstance(req, dict):
        raise A2Error("requirements: object required")
    unresolved = []
    S = req.get("S")
    if not isinstance(S, dict) or not S.get("id") or not S.get("definition"):
        unresolved.append("S (pooled statistic) not designated")
    ev = req.get("event_set")
    if isinstance(ev, dict) and isinstance(ev.get("count"), bool):
        raise A2Error("event_set.count: integer required (booleans rejected)")
    if not isinstance(ev, dict) or not ev.get("id") or not isinstance(ev.get("count"), int) or ev["count"] < 0:
        unresolved.append("event_set undefined or count not an integer")
    unit = req.get("units")
    if unit is not None and unit not in UNITS:
        raise A2Error(f"units: {unit!r} not supported ({list(UNITS)})")
    if unit is None:
        unresolved.append("units unresolved")
    w = req.get("weights")
    if w is not None:
        if not isinstance(w, dict) or w.get("scheme") not in ("equal", "inverse-variance", "explicit"):
            raise A2Error("weights: {scheme: equal|inverse-variance|explicit, ...} required")
        if w["scheme"] == "explicit":
            vals = w.get("values")
            if not isinstance(vals, list) or not vals or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in vals):
                raise A2Error("weights.values: finite non-negative numbers required for an explicit scheme (NaN/inf/bool rejected)")
            if isinstance(ev, dict) and isinstance(ev.get("count"), int) and not isinstance(ev.get("count"), bool) and len(vals) != ev["count"]:
                raise A2Error("weights.values: cardinality must equal event_set.count")
        if w["scheme"] == "explicit" and S and isinstance(S, dict) and S.get("unit") and unit and S["unit"] != unit:
            raise A2Error("weights/units: S unit incompatible with the declared units")
    else:
        unresolved.append("weights unresolved")
    h = req.get("horizon")
    if h is not None:
        if not isinstance(h, dict) or h.get("unit") not in HORIZON_UNITS or isinstance(h.get("length"), bool) or not isinstance(h.get("length"), int) or h["length"] <= 0:
            raise A2Error("horizon: {length: positive int, unit: sessions|calendar-days} required")
    else:
        unresolved.append("horizon unresolved")
    vb = req.get("variance_basis")
    if vb is not None and vb not in VARIANCE_BASES:
        raise A2Error(f"variance_basis: {vb!r} unsupported ({list(VARIANCE_BASES)})")
    if vb is None:
        unresolved.append("variance basis unresolved")
    r4 = req.get("rule4_disposition", "UNRESOLVED")
    if r4 not in RULE4:
        raise A2Error("rule4_disposition: APPLIED|NOT_APPLIED|UNRESOLVED")
    if r4 == "UNRESOLVED":
        unresolved.append("rule-4 disposition unresolved")
    inc = req.get("incident_dependencies", [])
    if not isinstance(inc, list) or any(not isinstance(i, dict) or not i.get("id") or i.get("disposition") not in ("CLOSED", "OPEN") for i in inc):
        raise A2Error("incident_dependencies: list of {id, disposition: CLOSED|OPEN}")
    if any(i["disposition"] == "OPEN" for i in inc):
        unresolved.append("open incident dependency: " + ", ".join(i["id"] for i in inc if i["disposition"] == "OPEN"))
    if isinstance(S, dict) and S.get("unit") and unit and S["unit"] != unit:
        raise A2Error("S.unit incompatible with the declared units")
    reg = req.get("registration")
    registered = isinstance(reg, dict) and bool(reg.get("registered_at")) and bool(reg.get("record_id")) and bool(reg.get("registered_by"))
    status = "CANDIDATE_COMPLETE" if not unresolved else "UNRESOLVED"
    return {"status": status, "registered_designation": "REGISTERED" if (registered and not unresolved) else "NOT_REGISTERED", "unresolved": unresolved,
            "n_eff": "NOT_COMPUTED (a designated S is a prerequisite; edges/components alone never determine N_eff)",
            "note": "CANDIDATE_COMPLETE = supplied facts are complete and consistent; a registered designation needs a registration record (registered_at, registered_by, record_id) — the software never invents one",
            "requirements": {"S": S, "event_set": ev, "units": unit, "weights": w, "horizon": h, "variance_basis": vb, "rule4_disposition": r4, "incident_dependencies": inc, "registration": reg}}


def from_source_metadata(meta: dict) -> dict:
    """Map what source metadata CAN supply (event set id/count, horizon, units when recorded) into a requirements
    record; everything else stays absent → UNRESOLVED per input."""
    req = {}
    if meta.get("event_set_id") is not None and isinstance(meta.get("eligible_events"), int):
        req["event_set"] = {"id": meta["event_set_id"], "count": meta["eligible_events"]}
    if isinstance(meta.get("horizon_sessions"), int):
        req["horizon"] = {"length": meta["horizon_sessions"], "unit": "sessions"}
    if meta.get("units") in UNITS:
        req["units"] = meta["units"]
    req["incident_dependencies"] = [{"id": i, "disposition": "OPEN"} for i in meta.get("open_incidents", [])]
    return req
