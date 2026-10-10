"""The one reducer: every CLI, JSON, HTML and packet view of a brief derives from `brief_view()`.

For each statement it answers five questions separately and never merges them into a score:
  byte_integrity       — do the span bytes still hash to the recorded digest in the exact text view?
  recorded_origin      — how was this text produced (template / import / edit / translation), with what known settings, and
                         what is explicitly unknown? which generation receipts bind to these bytes?
  issuer_trust         — for signed receipts/reports on these bytes: signature validity, issuer trust under this receiver's
                         policy, revocation, payload binding (four answers, never one)
  substantive_support  — SUPPORTED / ATTRIBUTED / UNRESOLVED / CONTRADICTED / NOT_ASSESSED / INVALIDATED, with the method,
                         the assessor and the limits
  time_scope           — the snapshot tip the statement was composed against, whether later v8 information exists, and the
                         review items on its recorded dependencies
and, separately again, the detector reports covering the statement's bytes (execution / signal / calibration applicability).
A positive signal or a valid signature never changes substantive_support. A correct calculation never authenticates a
provider. Coverage is reported over a defined denominator (identified statements) with extraction completeness unestablished.
"""
from __future__ import annotations

from v8.workbench.store import Workspace
from v9.brief import compose, contracts, finance, reports, snapshot
from v9.brief.i18n import t
from v9.brief.sidecar import Sidecar

REDUCER = "v9.brief.reducer/1"
NEVER = ("never.not_detected", "never.percentage", "never.identity", "never.timestamp")


def _integrity(data: bytes, sp: dict) -> dict:
    problems = contracts.span_problems(data, sp["start"], sp["end"])
    if problems:
        return {"status": "FAILED", "reason": "; ".join(problems)}
    actual = contracts.span_digest(data, sp["start"], sp["end"])
    return {"status": "VERIFIED" if actual == sp["span_sha256"] else "FAILED", "recorded": sp["span_sha256"], "observed": actual}


def _dependencies(sp: dict) -> set:
    deps = set()
    if sp.get("claim"):
        deps.add(f"claim:{sp['claim']['claim_id']}")
    for e in sp.get("evidence", []):
        if e["kind"] == "source_excerpt":
            deps.add(f"source:{e['ref']}")
        elif e["kind"] in ("claim_version", "outcome"):
            deps.add(f"claim:{e['ref'].split('#')[0]}")
    return deps


def _detector_label(rep: dict, lang: str) -> str:
    ex = rep["execution"]
    if ex == "COMPLETED":
        return t("label.watermark.completed", lang)
    if ex == "NOT_REQUESTED":
        return t("label.watermark.not_requested", lang)
    return t("label.watermark.unavailable", lang)


def brief_view(ws: Workspace, sc: Sidecar, brief_id: str, version_id: str | None = None, lang: str = "en") -> dict:
    """The complete derived view of one brief version. Never writes."""
    lang = "fr" if lang == "fr" else "en"
    recs = sc.load()["records"]
    vrec = compose.version(sc, brief_id, version_id, recs); p = vrec["payload"]
    all_versions = compose.versions_of(sc, brief_id, recs)
    missing = sc.missing_objects(vrec)
    view = {"reducer": REDUCER, "brief_id": brief_id, "version_id": p["version_id"], "parent_version": p["parent_version"], "language": p["language"], "title": p["title"],
            "claim_ids": p["claim_ids"], "recorded_at": vrec["time"]["recorded_at"], "actor": vrec["actor"], "v8_tip_at_write": vrec["v8_tip"], "snapshot_digest": p["snapshot_digest"],
            "v8_tip_at_snapshot": p["v8_tip_at_snapshot"], "text_view": p["text_view"], "complete": not missing, "missing_objects": missing,
            "versions": [{"version_id": r["payload"]["version_id"], "parent_version": r["payload"]["parent_version"], "language": r["payload"]["language"], "recorded_at": r["time"]["recorded_at"],
                          "transform": r["payload"]["transform"]["kind"], "view_sha256": r["payload"]["text_view"]["view_sha256"], "complete": not sc.missing_objects(r)} for r in all_versions],
            "mission": "Make financial AI accountable to evidence.", "vision": "Become the Science Trust Layer for Financial AI.", "not_advice": t("brief.not_advice", lang),
            "dimension_note": t("dim.note", lang), "never_claims": [t(k, lang) for k in NEVER]}
    if missing:
        view.update(status="INCOMPLETE", status_label=t("label.incomplete", lang), text=None, statements=[], coverage=None, review_items=[], receipts=[], reports=[])
        return view
    data = sc.get_bytes(p["text_view"]["view_sha256"]); view["text"] = data.decode("utf-8")
    snap = sc.get_object(p["snapshot_object"])
    live_findings = snapshot.dependency_review(ws, snap)
    resolved = {r["payload"]["item_id"]: r["payload"] for r in sc.records("REVIEW_ITEM_RESOLVED", brief_id, recs)}
    transform_findings = [dict(f, dependency=None, version_id=p["version_id"]) for f in p["transform"].get("review_findings", [])]
    items = []
    for f in live_findings + transform_findings:
        iid = compose.review_item_id(f)
        items.append({"item_id": iid, "reason": f["reason"], "dependency": f.get("dependency"), "detail": f["detail"], "span": f.get("span"), "resolved": resolved.get(iid)})
    open_items = [i for i in items if not i["resolved"]]
    roots = reports.trust_roots(sc, recs); cals = reports.calibrations(sc, recs)
    bound = reports.records_for_view(sc, p["text_view"]["view_sha256"], recs)
    receipts = []
    for r in [{"payload": {"record": p["receipt"], "origin_label": "recorded with the version"}}] + bound["receipts"]:
        rec = r["payload"]["record"]; sig = reports.evaluate_signature("receipt", rec, roots)                 # under the receiver's CURRENT roots (a revocation shows at once); the import-time evaluation stays in the record
        receipts.append({"record_id": rec["record_id"], "origin": rec["origin"], "recording_method": rec["recording_method"], "template": rec.get("template"), "provider": rec.get("provider"), "model": rec.get("model"),
                         "settings": rec.get("settings"), "unknown": rec.get("unknown"), "request_id": rec.get("request_id"), "issued_at": rec.get("issued_at"), "observed_at": rec["observed_at"],
                         "raw_output_sha256": rec.get("raw_output_sha256"), "assembled_output_sha256": rec["assembled_output_sha256"], "same_bytes": rec.get("raw_output_sha256") == rec["assembled_output_sha256"],
                         "signature": sig, "label": t("label.generation_record", lang), "note": rec.get("provenance_note") or r["payload"].get("origin_label", "")})
    reps = []
    for r in bound["reports"]:
        rec = r["payload"]["record"]; sig = reports.evaluate_signature("report", rec, roots)
        cal_rec = cals.get(rec.get("calibration_ref"))
        cal_sig = reports.evaluate_signature("calibration", cal_rec["payload"]["record"], roots) if cal_rec is not None else None
        app = reports.calibration_applicability(rec, cal_rec, p["language"], cal_sig)
        reps.append({"record_id": rec["record_id"], "detector": rec["detector"], "detector_version": rec.get("detector_version"), "configuration": rec.get("configuration"), "key_scope": rec.get("key_scope"),
                     "execution": rec["execution"], "signal": rec.get("signal"), "calibration_claimed": rec["calibration"], "calibration": app, "failure_reason": rec.get("failure_reason"),
                     "diagnostics": rec.get("diagnostics"), "unknown": rec.get("unknown"), "origin": rec["origin"], "cache_reuse": rec.get("cache_reuse"), "span": rec["span"], "observed_at": rec["observed_at"],
                     "signature": sig, "label": _detector_label(rec, lang), "provider_reported": t("label.provider_reported", lang) if rec["execution"] == "COMPLETED" else None,
                     "scope_note": "this report covers exactly the tested span of this text view; it does not apply to other bytes, versions or languages"})
    spans = compose.effective_spans(sc, vrec, recs)
    statements = []
    for i, sp in enumerate(spans, 1):
        integ = _integrity(data, sp)
        deps = _dependencies(sp)
        mine = [it for it in open_items if (it["dependency"] in deps) or (it["span"] == sp["record_id"])]
        support = sp["support"]
        if integ["status"] != "VERIFIED":
            support = "INVALIDATED"
        covering = [rp for rp in reps if rp["span"]["start"] <= sp["start"] and rp["span"]["end"] >= sp["end"]]
        calc_check = None
        if sp.get("calculation"):
            c = sp["calculation"]
            if c.get("kind") == "containment_pair":
                o1, d1 = finance.recompute(c["original"]); o2, d2 = finance.recompute(c["revised"]); calc_check = {"outcome": o1 if o1 == o2 else "FAILED", "detail": d1 or d2}
            elif c.get("kind") == "pending":
                calc_check = {"outcome": "NOT_APPLICABLE", "detail": "no arithmetic: PENDING_OUTCOME"}
            else:
                o, d = finance.recompute(c); calc_check = {"outcome": o, "detail": d}
            if calc_check["outcome"] == "FAILED" and support == "SUPPORTED":
                support = "CONTRADICTED"
        statements.append({"n": i, "record_id": sp["record_id"], "start": sp["start"], "end": sp["end"], "text": data[sp["start"]:sp["end"]].decode("utf-8"), "role": sp["role"], "role_label": t(f"role.{sp['role']}", lang),
                           "byte_integrity": integ,
                           "recorded_origin": {"transform": p["transform"]["kind"], "implementation": p["transform"]["implementation"], "renderer": (p.get("production") or {}).get("renderer"),
                                               "template": (p.get("production") or {}).get("template"), "deterministic": bool((p.get("production") or {}).get("deterministic")), "assessor": sp["assessor"],
                                               "receipts": [r["record_id"] for r in receipts], "unknown": receipts[0]["unknown"] if receipts else {}},
                           "issuer_trust": {"receipts": [{"record_id": r["record_id"], "signature": r["signature"]} for r in receipts if r["signature"]["signature"] != "NONE"],
                                            "reports": [{"record_id": r["record_id"], "signature": r["signature"]} for r in covering if r["signature"]["signature"] != "NONE"],
                                            "note": "trust concerns who signed a record about these bytes; it says nothing about the statement's truth"},
                           "substantive_support": {"status": support, "label": t(f"support.{support}", lang), "method": sp["method"], "assessor": sp["assessor"], "limits": sp["limits"],
                                                   "claim": sp.get("claim"), "evidence": sp.get("evidence", []), "calculation": sp.get("calculation"), "calculation_check": calc_check, "protected": sp.get("protected", [])},
                           "time_scope": {"snapshot_digest": p["snapshot_digest"], "v8_tip_at_snapshot": p["v8_tip_at_snapshot"], "later_information": bool(mine), "review_items": [it["item_id"] for it in mine],
                                          "label": t("label.later_information", lang) if mine else t("label.snapshot_current", lang)},
                           "detector": {"reports": [{k: r[k] for k in ("record_id", "detector", "execution", "signal", "calibration", "label", "provider_reported", "origin")} for r in covering],
                                        "label": covering[0]["label"] if covering else t("label.watermark.not_requested", lang)}})
    mapped = sum(1 for s in statements if s["substantive_support"]["status"] in ("SUPPORTED", "ATTRIBUTED", "CONTRADICTED", "UNRESOLVED") and (s["substantive_support"]["claim"] or s["substantive_support"]["evidence"] or s["role"] == "unresolved_claim"))
    view.update(status="COMPLETE", statements=statements, receipts=receipts, reports=reps, review_items=items, open_review_items=len(open_items),
                coverage={"mapped": mapped, "identified": len(statements), "sentence": t("coverage", lang, mapped=mapped, total=len(statements)), "extraction_scope": p.get("extraction_scope"), "completeness": "NOT_ESTABLISHED"},
                support_counts={k: sum(1 for s in statements if s["substantive_support"]["status"] == k) for k in contracts.SUPPORT},
                trust_roots={k: {"label": r["label"], "revoked": r["revoked"], "issuer": r.get("issuer")} for k, r in roots.items()},
                snapshot_summary={cid: {"current_version": c["current_version"], "result": c["results"]["result"], "versions": [v["version_id"] for v in c["versions"]], "sources": list(c["sources"])} for cid, c in snap["claims"].items()},
                evidence_label=t("label.evidence.complete", lang) if not open_items and all(s["byte_integrity"]["status"] == "VERIFIED" for s in statements) else t("label.evidence.incomplete", lang))
    return view


def list_briefs(ws: Workspace, sc: Sidecar) -> list[dict]:
    recs = sc.load()["records"]; out = {}
    for r in compose.versions_of(sc, None, recs) if False else [x for x in recs if x["kind"] == "BRIEF_VERSION_RECORDED"]:
        p = r["payload"]; b = out.setdefault(r["brief_id"], {"brief_id": r["brief_id"], "title": p["title"], "claim_ids": p["claim_ids"], "versions": [], "languages": set()})
        b["versions"].append(p["version_id"]); b["languages"].add(p["language"]); b["title"] = p["title"]; b["latest"] = p["version_id"]; b["recorded_at"] = r["time"]["recorded_at"]
        b["complete"] = not sc.missing_objects(r)
    return [dict(b, languages=sorted(b["languages"])) for b in out.values()]


def statement_text(view: dict, n: int) -> dict:
    s = next((x for x in view["statements"] if x["n"] == n), None)
    if s is None:
        raise KeyError(n)
    return s
