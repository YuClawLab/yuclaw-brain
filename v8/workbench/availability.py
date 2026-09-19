"""Source-availability corrections (TIM-08): a linked, append-only correction of WHEN a registered source became public.

A correction is one SOURCE_AVAILABILITY_CORRECTED event. It names the registered source (source id, accession, passage
digest), the registration event it refers to, the value it replaces and the event that carried that value, the corrected
value, the reason, an evidence reference and an actor label. It never edits the registration, the passage bytes, a digest,
an observation time, a frozen claim version, an outcome or an adjudication: those records stay exactly as written.

Three kinds of time stay apart:
  * asserted availability — when the source became public, as asserted at registration and as corrected later;
  * observation           — when this workspace first saw the passage (the registration's observed_at; never corrected);
  * correction recording  — the server's local action time of the correction event (never supplied by the user).

Historical-view rule (EFFECTIVE_FROM_RECORDED_AT/1). A correction carries no source availability of its own, so it is placed
by its recording time. A view whose cutoff is at or after that time uses the corrected value for every event citing the
source. A view at an earlier cutoff keeps the value the record held then and lists the correction as a LATER correction,
together with what it would change: later knowledge is shown as later knowledge, never as something known at the cutoff,
and no historical view is revised silently.

Recomputation sits beside the record, never over it. The as-recorded results, dataset row and adjudications are unchanged;
the corrected view (result, withdrawal-before-outcome ordering, retrospective status) is computed from the corrected values
and every difference is listed for review. A correction can make a record retrospective; it can never make a retrospective
record contemporaneous — that difference is reported and the recorded status is retained.
Pure functions: nothing here reads a file, a clock or the network. Research and education only. Not investment advice.
"""
from __future__ import annotations

from v3.receipts.contracts import ContractError
from v8.workbench import calc, schema

KIND = "SOURCE_AVAILABILITY_CORRECTED"
BLOCK_SCHEMA = "yuclaw-source-availability/1"
EFFECT_RULE = "EFFECTIVE_FROM_RECORDED_AT/1"
ATTRIBUTION = "an actor label is attribution; it is not authenticated identity and does not establish independent human review"
PAYLOAD_KEYS = ("correction_id", "source_id", "accession", "source_hash", "registration_event", "registered_available_as_of", "prior_available_as_of", "prior_event",
                "corrected_available_as_of", "direction", "reason", "evidence_ref", "actor", "actor_kind", "attribution", "effect_rule", "changes_source", "changes_claim")
SEMANTICS = [
    "asserted availability (when the source became public) is kept apart from observation (when this workspace first saw the passage) and from correction recording (the server's local action time of the correction)",
    "a correction is a new event linked to the registration and to the value it replaces; the registration, the passage bytes, every digest, the observation time, frozen claim versions, outcomes and adjudications are unchanged",
    "EFFECTIVE_FROM_RECORDED_AT/1: a view whose cutoff is at or after the correction's recorded time uses the corrected availability; a view at an earlier cutoff keeps the value the record held then and lists the correction as a later correction",
    "a later correction is later knowledge: it is never presented as known at an earlier cutoff, and no historical view is revised silently",
    "the as-recorded results and dataset row are unchanged; the corrected view is recomputed beside them and every difference is listed for review",
    "a correction can make a record retrospective; it never makes a retrospective record contemporaneous (that difference is reported and the recorded status is retained)",
]


def source_id(src: dict) -> str:
    return f"{src['accession']}:{src['source_hash'][:16]}"


def event_source(ev: dict) -> dict | None:
    """The source a source-bearing event cites (None for events that carry no source availability)."""
    p = ev.get("payload") or {}; k = ev.get("kind")
    if k in ("SOURCE_REGISTERED", "CLAIM_WITHDRAWN"):
        s = p.get("source")
    elif k in ("CLAIM_FROZEN", "CLAIM_REVISED", "SOURCE_CORRECTED"):
        s = (p.get("claim") or {}).get("source")
    elif k == "OUTCOME_RECORDED":
        s = (p.get("outcome") or {}).get("source")
    else:
        s = None
    return s if isinstance(s, dict) and s.get("accession") and s.get("source_hash") else None


def index(events: list[dict], as_of: str | None = None) -> dict:
    """{source_id: {"registration", "registered", "applied": [...], "later": [...], "effective"}} for every registered source.
    `applied` is the prefix of the source's correction chain recorded at or before the cutoff (the whole chain without one)."""
    cut = schema.parse_ts(as_of) if as_of is not None else None
    idx: dict = {}
    for e in events:
        if e.get("kind") == "SOURCE_REGISTERED":
            sid = e["payload"]["source_id"]
            idx.setdefault(sid, {"source_id": sid, "registration": e, "registered": e["payload"]["source"]["available_as_of"], "applied": [], "later": []})   # the first registration stands
        elif e.get("kind") == KIND:
            ent = idx.get(e["payload"]["source_id"])
            if ent is None:
                continue
            late = bool(ent["later"]) or (cut is not None and schema.parse_ts(e["time"]["recorded_at"]) > cut)
            ent["later" if late else "applied"].append(e)
    for ent in idx.values():
        ent["effective"] = ent["applied"][-1]["payload"]["corrected_available_as_of"] if ent["applied"] else ent["registered"]
    return idx


def effective_stamp(ev: dict, idx: dict | None) -> str | None:
    """The availability an as-of view cuts this event by: the corrected value once a correction applies at the view's cutoff."""
    stamp = ev["time"].get("source_available_as_of")
    src = event_source(ev) if stamp is not None and idx else None
    ent = idx.get(source_id(src)) if src is not None else None
    return ent["effective"] if ent and ent["applied"] else stamp


def _cited(state: dict) -> list[dict]:
    srcs = [v["claim"]["source"] for v in state["versions"]]
    if state.get("withdrawn"):
        srcs.append(state["withdrawn"]["source"])
    if state.get("outcome"):
        srcs.append(state["outcome"]["source"])
    return srcs


def attach(state: dict, idx: dict) -> dict:
    """Give a claim state the correction chains of the sources it cites (empty when none was ever corrected)."""
    sids = {source_id(s) for s in _cited(state)}
    state["availability"] = {sid: ent for sid, ent in idx.items() if sid in sids and (ent["applied"] or ent["later"])}
    return state


def event_hashes(state: dict) -> set:
    """Correction events a note or an adjudication on this claim may cite as evidence."""
    return {e["event_hash"] for ent in (state.get("availability") or {}).values() for e in ent["applied"] + ent["later"]}


def effective_for(state: dict, src: dict) -> str:
    ent = (state.get("availability") or {}).get(source_id(src))
    return ent["effective"] if ent and ent["applied"] else src["available_as_of"]


def effective_state(state: dict) -> dict:
    """The same claim state with the corrected availabilities in the two places a computation reads them: the withdrawal /
    outcome ordering and the event times the retrospective test compares. Claim versions and their digests are untouched."""
    idx = state.get("availability") or {}
    eff = dict(state)
    if state.get("withdrawn"):
        w = state["withdrawn"]; eff["withdrawn"] = dict(w, source=dict(w["source"], available_as_of=effective_for(state, w["source"])))
    if state.get("outcome"):
        o = state["outcome"]; eff["outcome"] = dict(o, source=dict(o["source"], available_as_of=effective_for(state, o["source"])))
    eff["events"] = [dict(e, time=dict(e["time"], source_available_as_of=effective_stamp(e, idx))) for e in state["events"]]
    return eff


def _ref(e: dict) -> dict:
    p = e["payload"]
    return {"correction_id": p["correction_id"], "event_hash": e["event_hash"], "prior_available_as_of": p["prior_available_as_of"], "prior_event": p["prior_event"],
            "corrected_available_as_of": p["corrected_available_as_of"], "direction": p["direction"], "reason": p["reason"], "evidence_ref": p["evidence_ref"],
            "actor": p["actor"], "actor_kind": p["actor_kind"], "recorded_at": e["time"]["recorded_at"]}


def block(state: dict) -> dict | None:
    """The source-availability block of a claim's current view, or None when no cited source was ever corrected. Deterministic
    for a given state: the verifier re-derives it from the packed registration and correction events and compares."""
    av = state.get("availability") or {}
    if not av:
        return None
    from v8.workbench import dataset                                  # dataset imports this module; the retrospective test lives there
    sources, review = [], []
    for sid in sorted(av):
        ent = av[sid]; reg = ent["registration"]; chain = ent["applied"] + ent["later"]
        lo, hi = sorted((ent["registered"], chain[-1]["payload"]["corrected_available_as_of"]), key=schema.parse_ts)
        sources.append({"source_id": sid, "accession": reg["payload"]["source"]["accession"], "source_hash": reg["payload"]["source"]["source_hash"],
                        "registration": {"event_hash": reg["event_hash"], "available_as_of": ent["registered"], "observed_at": reg["time"]["observed_at"], "recorded_at": reg["time"]["recorded_at"]},
                        "corrections": [_ref(e) for e in ent["applied"]], "later_corrections": [_ref(e) for e in ent["later"]], "effective_available_as_of": ent["effective"],
                        "affected_cutoffs": {"from": lo, "until": hi, "note": "as-of views with a cutoff in this interval differ between the registered and the corrected availability; a cutoff before the correction was recorded keeps the registered value and lists the correction as later"}})
        if ent["applied"] and schema.parse_ts(ent["effective"]) > schema.parse_ts(reg["time"]["observed_at"]):
            review.append({"code": "AVAILABILITY_AFTER_OBSERVATION", "source_id": sid, "detail": f"the corrected availability {ent['effective']} is later than this workspace's recorded observation of the passage ({reg['time']['observed_at']}); the observation time or the correction needs review"})
    recorded, eff = calc.adjudicate(state), effective_state(state)
    corrected = calc.adjudicate(eff)
    r0, r1 = dataset.retrospective(state), dataset.retrospective(eff)
    if corrected["result"] != recorded["result"]:
        review.append({"code": "RESULT_CHANGES", "detail": f"the computed result is {recorded['result']} as recorded and {corrected['result']} under the corrected availability; both are shown and neither replaces the other"})
    if r0["retrospective"] and not r1["retrospective"]:
        review.append({"code": "RETROSPECTIVE_STATUS_RETAINED", "detail": "under the corrected availability the retrospective test no longer holds, but a correction recorded after the fact cannot establish contemporaneous knowledge: the record stays RETROSPECTIVE and needs review"})
    elif r1["retrospective"] and not r0["retrospective"]:
        review.append({"code": "RETROSPECTIVE_UNDER_CORRECTION", "detail": f"under the corrected availability this record is a retrospective reconstruction ({r1['reason']}); it is not prospective evidence"})
    last = max((schema.parse_ts(e["time"]["recorded_at"]) for ent in av.values() for e in ent["applied"]), default=None)
    for a in state.get("adjudications", []):
        if last is not None and schema.parse_ts(a["time"]["recorded_at"]) < last and a.get("computed_result") != corrected["result"]:
            review.append({"code": "ADJUDICATION_PREDATES_CORRECTION", "detail": f"the adjudication by {a['reviewer']} ({a['time']['recorded_at']}) was computed as {a.get('computed_result')} before the correction; the corrected view computes {corrected['result']}. It is retained unchanged; a further adjudication can be recorded"})
    view = {"basis": "every correction recorded to date applied (the current view)", "recorded_result": recorded["result"], "result": corrected["result"], "result_changes": corrected["result"] != recorded["result"],
            "reasons": corrected["reasons"], "comparison_permitted": corrected["comparison_permitted"], "recorded_retrospective": r0["retrospective"], "recomputed_retrospective": r1["retrospective"],
            "retrospective": r0["retrospective"] or r1["retrospective"], "retrospective_reason": r1["reason"],
            "withdrawal_available_as_of": eff["withdrawn"]["source"]["available_as_of"] if eff.get("withdrawn") else None, "outcome_available_as_of": eff["outcome"]["source"]["available_as_of"] if eff.get("outcome") else None}
    return {"schema": BLOCK_SCHEMA, "effect_rule": EFFECT_RULE, "semantics": SEMANTICS, "sources": sources, "corrected_view": view, "corrected_results": corrected, "review": review, "needs_review": bool(review)}


def row_block(state: dict) -> dict | None:
    """The part of the block a dataset row carries (the full corrected calculation stays in the claim export)."""
    b = block(state)
    return None if b is None else {k: b[k] for k in ("schema", "effect_rule", "sources", "corrected_view", "review", "needs_review")}


def chain_problem(events: list[dict]) -> str | None:
    """First defect in the packed correction chains, or None. A packed correction must link to a packed registration of the
    same source, replace exactly the value in force before it, carry no availability of its own and keep its recorded order."""
    regs: dict = {}; tip: dict = {}
    for e in events:
        if e.get("kind") == "SOURCE_REGISTERED":
            regs.setdefault(e["payload"]["source_id"], e)
    for e in events:
        if e.get("kind") != KIND:
            continue
        p = e.get("payload"); cid = p.get("correction_id") if isinstance(p, dict) else None
        if not isinstance(p, dict) or tuple(sorted(p)) != tuple(sorted(PAYLOAD_KEYS)):
            return f"availability correction {cid or e.get('seq')}: payload fields differ from the correction contract"
        reg = regs.get(p["source_id"])
        if reg is None or reg["event_hash"] != p["registration_event"]:
            return f"availability correction {cid}: the registration event it names is not the packed registration of {p['source_id']}"
        s = reg["payload"]["source"]
        if (p["accession"], p["source_hash"], p["registered_available_as_of"]) != (s["accession"], s["source_hash"], s["available_as_of"]) or source_id(s) != p["source_id"]:
            return f"availability correction {cid}: source identity or registered availability differs from the registration"
        prev = tip.get(p["source_id"])
        want = (prev["payload"]["corrected_available_as_of"], prev["event_hash"]) if prev else (s["available_as_of"], reg["event_hash"])
        if (p["prior_available_as_of"], p["prior_event"]) != want:
            return f"availability correction {cid}: it does not replace the value in force before it (chain broken or reordered)"
        try:
            new, old = schema.parse_ts(p["corrected_available_as_of"]), schema.parse_ts(p["prior_available_as_of"])
            if prev and schema.parse_ts(e["time"]["recorded_at"]) < schema.parse_ts(prev["time"]["recorded_at"]):
                return f"availability correction {cid}: recorded before the correction it replaces"
        except (ContractError, KeyError, TypeError):
            return f"availability correction {cid}: a timestamp is not RFC3339 UTC"
        if new == old or p["direction"] != ("EARLIER" if new < old else "LATER"):
            return f"availability correction {cid}: corrected value or direction inconsistent with the value it replaces"
        if new.date().isoformat() < s["filed_at"]:
            return f"availability correction {cid}: corrected availability precedes the source's filing date"
        if e["time"].get("source_available_as_of") is not None:
            return f"availability correction {cid}: a correction carries no source availability of its own (it is placed by its recorded time)"
        if p["effect_rule"] != EFFECT_RULE or p["changes_source"] is not False or p["changes_claim"] is not False:
            return f"availability correction {cid}: unsupported effect rule or a declared change to the source or claim"
        tip[p["source_id"]] = e
    return None


def later_at(state: dict, idx: dict, cut: str) -> list[dict]:
    """For an as-of view: the corrections on this claim's sources recorded AFTER the cutoff — never applied to that view —
    with whether the source counts as public at the cutoff as the record held it then and as the later correction asserts."""
    t = schema.parse_ts(cut); out = []
    for sid in sorted({source_id(s) for s in _cited(state)}):
        ent = idx.get(sid)
        for e in (ent["later"] if ent else []):
            p = e["payload"]
            out.append({"correction_id": p["correction_id"], "source_id": sid, "recorded_at": e["time"]["recorded_at"], "held_at_cutoff": ent["effective"], "corrected_available_as_of": p["corrected_available_as_of"],
                        "public_as_held": schema.parse_ts(ent["effective"]) <= t, "public_under_correction": schema.parse_ts(p["corrected_available_as_of"]) <= t, "event_hash": e["event_hash"]})
    return out
