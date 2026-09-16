"""Workbench adapter for the scientific kernel (V8-005): bounded strict input, real replay through the kernel, specific
eligibility reasons, link verification against the workspace's claim/version/source objects, honest replay status.

A journal input is DATA: a JSON event list in the kernel's own event format (sequence, kind, payload, recorded_at,
previous_hash, event_hash), optionally wrapped in an envelope {"events": [...], "expected_root": "<hex>", "links": {...},
"declared": {...}}. Nothing in it is executed, imported, opened as a file or fetched. Research and education only.
"""
from __future__ import annotations

import hashlib
import json

from v8.workbench.sci import SCHEMA_VERSION, kernel_identity
from v8.workbench.sci.contracts import canonical
from v8.workbench.sci.store import replay, report

MAX_INPUT_BYTES = 256 * 1024
MAX_EVENTS = 2000
MAX_DEPTH = 12
ENVELOPE_KEYS = ("events", "expected_root", "links", "declared", "label")
LINK_KEYS = ("claim_id", "version_digest", "source_hashes")
DECLARED_KEYS = ("retrospective", "note")
STATUSES = ("SUPPORTED_REPLAY", "EXPLORATORY_REPLAY", "INELIGIBLE")
STANDING = [
    "Computational verification: the kernel re-derived every event hash and recomputed every statistic from the packed events. It does not establish source truth, independent human review or externally authenticated timestamps.",
    "Imported timestamps do not establish that a prediction was actually committed before its outcome was known; the anchor status of every replay is LOCAL_ONLY_EXTERNAL_TIMESTAMP_NOT_VERIFIED.",
    "An imported actor label is attribution, not verified human identity; a matching adjudication hash names bytes, not an adjudicator.",
    "Monetary amounts and ranges are not probabilities; a financial commitment's IN_RANGE / OUT_OF_RANGE results are not units of a paired-Brier study and no scientific improvement is derived from them.",
    "A scientific result grants no trade, training, model change, deployment, publication or other external action. Human benefit stays PENDING.",
]
MONEY_KEYS = ("range", "low", "high", "currency", "amount", "actual", "unit", "scale_as_stated")


class InputError(ValueError):
    pass


def _reject_duplicates(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise InputError(f"duplicate JSON field {k!r}")
        d[k] = v
    return d


def _reject_constant(c):
    raise InputError(f"non-finite number {c} is not allowed")


def _depth(x, d=0):
    if d > MAX_DEPTH:
        raise InputError(f"nesting deeper than {MAX_DEPTH}")
    if isinstance(x, dict):
        for v in x.values():
            _depth(v, d + 1)
    elif isinstance(x, list):
        for v in x:
            _depth(v, d + 1)


def parse_input(raw: str | bytes) -> dict:
    """Strict parse of a bounded journal input → normalized envelope. Raises InputError with the reason."""
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > MAX_INPUT_BYTES:
        raise InputError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    if not data.strip():
        raise InputError("empty input")
    try:
        doc = json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)
    except UnicodeDecodeError:
        raise InputError("input is not UTF-8") from None
    except ValueError as exc:
        raise InputError(f"input is not valid JSON: {str(exc)[:120]}") from None
    _depth(doc)
    if isinstance(doc, list):
        env = {"events": doc}
    elif isinstance(doc, dict):
        unknown = sorted(set(doc) - set(ENVELOPE_KEYS))
        if unknown:
            raise InputError(f"unsupported envelope fields {unknown}; supported: {list(ENVELOPE_KEYS)}")
        env = dict(doc)
    else:
        raise InputError("input must be a JSON event list or an envelope object")
    ev = env.get("events")
    if not isinstance(ev, list) or not ev:
        raise InputError("events: a non-empty list of journal events is required")
    if len(ev) > MAX_EVENTS:
        raise InputError(f"events: more than {MAX_EVENTS} events")
    if any(not isinstance(e, dict) for e in ev):
        raise InputError("events: every event must be an object")
    er = env.get("expected_root")
    if er is not None and (not isinstance(er, str) or len(er) != 64 or any(c not in "0123456789abcdef" for c in er)):
        raise InputError("expected_root: a lowercase 64-hex sha256 or omitted")
    links = env.get("links")
    if links is not None:
        if not isinstance(links, dict) or set(links) - set(LINK_KEYS):
            raise InputError(f"links: an object with only {list(LINK_KEYS)}")
        if "claim_id" in links and not isinstance(links["claim_id"], str):
            raise InputError("links.claim_id: string")
        if "version_digest" in links and not (isinstance(links["version_digest"], str) and len(links["version_digest"]) == 64):
            raise InputError("links.version_digest: 64-hex sha256")
        if "source_hashes" in links and (not isinstance(links["source_hashes"], list) or len(links["source_hashes"]) > 100 or any(not isinstance(h, str) or len(h) != 64 for h in links["source_hashes"])):
            raise InputError("links.source_hashes: a list of up to 100 64-hex sha256 values")
    dec = env.get("declared")
    if dec is not None and (not isinstance(dec, dict) or set(dec) - set(DECLARED_KEYS) or ("retrospective" in dec and not isinstance(dec["retrospective"], bool)) or ("note" in dec and (not isinstance(dec["note"], str) or len(dec["note"]) > 2000))):
        raise InputError(f"declared: an object with only {list(DECLARED_KEYS)} (retrospective: boolean; note: text up to 2000 characters)")
    lab = env.get("label")
    if lab is not None and (not isinstance(lab, str) or len(lab) > 200):
        raise InputError("label: text up to 200 characters")
    return {"events": ev, "expected_root": er, "links": links, "declared": dec, "label": lab}


def input_identity(env: dict) -> dict:
    b = canonical(env).encode("utf-8")
    return {"input_sha256": hashlib.sha256(b).hexdigest(), "input_bytes": len(b), "events": len(env["events"]), "schema": SCHEMA_VERSION}


def _prescan(env: dict) -> list[dict]:
    """Structural reasons visible before the kernel runs: monetary fields offered as probabilities; adjudication claims."""
    reasons = []
    for e in env["events"]:
        p = e.get("payload")
        if isinstance(p, dict):
            if e.get("kind") == "predict" and any(k in p for k in MONEY_KEYS):
                reasons.append({"code": "MONETARY_RANGE_SUPPLIED", "reason": f"event {e.get('sequence')}: a prediction carries monetary fields {sorted(k for k in MONEY_KEYS if k in p)}; a revenue range or amount is not a probability and cannot be scored by paired Brier improvement"}); break
    for e in env["events"]:
        p = e.get("payload")
        if isinstance(p, dict) and any(k in p for k in ("reviewer", "independent_review", "human_reviewed", "adjudicator")):
            reasons.append({"code": "UNSUPPORTED_ADJUDICATION_CLAIM", "reason": f"event {e.get('sequence')}: the kernel records an adjudication hash only; it does not verify who adjudicated or whether the review was independent, so reviewer/independence fields are not supported"}); break
    return reasons


def _map_kernel_error(msg: str, env: dict) -> dict:
    m = msg
    if "outside permitted finite range" in m and "probability" in m:
        return {"code": "MONETARY_OR_OUT_OF_RANGE_PROBABILITY", "reason": f"{m}: a value outside [0, 1] was supplied as a probability — monetary amounts or ranges are not probabilities"}
    if "expected exactly these fields" in m and "candidate_probability" in m:
        return {"code": "MISSING_PREDICTION_PAIR", "reason": f"{m}: a prediction must carry both baseline_probability and candidate_probability (paired design); nothing else"}
    if "expected exactly these fields" in m:
        return {"code": "UNSUPPORTED_FIELDS", "reason": m}
    if "paired_brier_improvement only" in m:
        return {"code": "UNSUPPORTED_METRIC", "reason": m}
    if "unsupported schema or mode" in m:
        return {"code": "UNSUPPORTED_SCHEMA", "reason": f"{m} (supported: schema {SCHEMA_VERSION}, mode prospective or exploratory)"}
    if "unknown claim_id" in m or "family already registered" in m:
        return {"code": "CHANGED_TARGET", "reason": f"{m}: the event set does not match the frozen family registration (target definition changed, unregistered or re-registered)"}
    if "journal integrity failure" in m:
        return {"code": "INTEGRITY_FAILURE", "reason": f"{m}: the event chain does not verify (tampered, reordered or rebuilt journal)"}
    if "journal root differs" in m:
        return {"code": "CHECKPOINT_MISMATCH", "reason": m}
    if "not matured" in m or "strictly after" in m or "moved backwards" in m:
        return {"code": "TIMING_RULE", "reason": m}
    if "reused source" in m:
        return {"code": "REUSED_SOURCE", "reason": m}
    if "empty journal" in m:
        return {"code": "EMPTY_JOURNAL", "reason": m}
    if "invalidated" in m:
        return {"code": "INVALIDATED_CLAIM", "reason": m}
    if "pending unit" in m:
        return {"code": "PENDING_UNIT_SKIPPED", "reason": m}
    if "budget exhausted" in m or "duplicate unit" in m:
        return {"code": "BUDGET_OR_DUPLICATE_UNIT", "reason": m}
    return {"code": "KERNEL_REFUSED", "reason": m}


def kernel_run(env: dict) -> dict:
    """The kernel part only (no workspace): replay + report or the specific refusal. Deterministic; used by the verifier."""
    reasons = _prescan(env)
    rep = None; root = None
    try:
        state, root = replay(env["events"], env["expected_root"])
        rep = report(env["events"], env["expected_root"])
    except ValueError as exc:
        reasons.append(_map_kernel_error(str(exc), env))
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:                       # malformed structure: refused, never a traceback
        reasons.append({"code": "MALFORMED_EVENT", "reason": f"malformed event structure ({exc.__class__.__name__}: {str(exc)[:120]})"})
    if reasons:
        return {"status": "INELIGIBLE", "reasons": reasons, "report": None, "root_hash": root}
    mode = rep["mode"]
    return {"status": "EXPLORATORY_REPLAY" if mode == "exploratory" else "SUPPORTED_REPLAY", "reasons": [], "report": rep, "root_hash": root}


def verify_links(env: dict, ws) -> dict:
    """Links to the workspace's financial objects: a matching digest links to those bytes, nothing more."""
    links = env.get("links") or {}
    out = {"declared": links or None, "claim": None, "version": None, "sources": [], "notes": []}
    if not links:
        return out
    cid = links.get("claim_id"); st = ws.claim_state(cid) if cid else None
    if cid:
        out["claim"] = {"claim_id": cid, "result": "VERIFIED_EXISTS" if st else "NOT_FOUND"}
        if st:
            from v8.workbench import dataset
            retro = dataset.retrospective(st)
            out["claim"]["retrospective"] = retro["retrospective"]; out["claim"]["fictional"] = bool(st["versions"][0]["claim"]["fictional"]); out["claim"]["current_version"] = st["current"]["version_id"]
            out["notes"].append("the linked commitment's IN_RANGE / OUT_OF_RANGE results are not units of this study; no Brier improvement is derived from them")
            if retro["retrospective"]:
                out["notes"].append("RETROSPECTIVE link: the linked financial record was observed after its outcome was public; this study cannot be prospective evidence about it")
    vd = links.get("version_digest")
    if vd:
        if st:
            match = next((v for v in st["versions"] if v["claim"]["_digest"] == vd), None)
            if match is None:
                out["version"] = {"version_digest": vd, "result": "NOT_FOUND"}
            elif match is st["current"]:
                out["version"] = {"version_digest": vd, "result": "VERIFIED_BYTES", "version_id": match["version_id"], "current": True}
            else:
                out["version"] = {"version_digest": vd, "result": "TARGET_CHANGED", "version_id": match["version_id"], "current": False, "note": f"the linked version {match['version_id']} has been superseded by {st['current']['version_id']}: the study's target definition is not the commitment's current one"}
        else:
            out["version"] = {"version_digest": vd, "result": "NOT_FOUND"}
    if links.get("source_hashes"):
        known = {e["payload"]["source"]["source_hash"] for e in ws.events() if e["kind"] == "SOURCE_REGISTERED"}
        out["sources"] = [{"source_hash": h, "result": "VERIFIED_BYTES" if h in known else "NOT_FOUND"} for h in links["source_hashes"]]
    out["notes"].append("a matching digest links to those bytes; it does not establish source authenticity, authenticated identity, independent review or external timestamping")
    return out


def classify(env: dict, ws) -> dict:
    """Kernel result + link verification + honest replay status for the workbench."""
    k = kernel_run(env); links = verify_links(env, ws)
    dec = env.get("declared") or {}
    retro_link = bool(links.get("claim") and links["claim"].get("retrospective"))
    if k["status"] == "INELIGIBLE":
        replay_status = "INELIGIBLE"
    elif dec.get("retrospective") or retro_link:
        replay_status = "RETROSPECTIVE_REPLAY"
    elif k["status"] == "EXPLORATORY_REPLAY":
        replay_status = "EXPLORATORY_REPLAY"
    else:
        replay_status = "PROSPECTIVE_CLAIMED_NOT_VERIFIED"
    warnings = []
    if replay_status == "RETROSPECTIVE_REPLAY":
        warnings.append("retrospective record: outcomes were public before this replay; the report is a reconstruction under the kernel's rules, not prospective evidence")
    if replay_status == "PROSPECTIVE_CLAIMED_NOT_VERIFIED":
        warnings.append("the input declares prospective mode; the workbench cannot verify that predictions were committed before outcomes were known (imported timestamps, local anchor only)")
    if links.get("version") and links["version"]["result"] == "TARGET_CHANGED":
        warnings.append(links["version"]["note"])
    return {"status": k["status"], "replay_status": replay_status, "reasons": k["reasons"], "report": k["report"], "root_hash": k["root_hash"], "report_digest": hashlib.sha256(canonical(k["report"]).encode()).hexdigest() if k["report"] else None,
            "links": links, "warnings": warnings, "kernel": kernel_identity(), "standing": STANDING}
