"""Importing provenance records: generation receipts, detector reports and calibration records; the receiver's trust policy.

Three origins are kept apart on every record: an operator-entered or imported assertion, a response observed by a
configured connector (none is configured in 9.0; the kind exists so a staged connector result can be imported later
without a schema change), and a cryptographically authenticated statement by an issuer. A filename, a screenshot, a
request id or a signature made by this workspace's own keys is not a provider signature. Signed records are verified
with the v8 envelope primitive (Ed25519, domain-separated, record type inside the signed bytes) against the trust roots
THIS workspace's administrator enrolled; the four answers — signature integrity, issuer trust, revocation, payload
binding — are reported separately and never merged. A valid signature from an unknown issuer is not a malformed
signature; a trusted signer may still make an unsupported financial claim; nothing here upgrades substantive support.

Every imported record must bind to an exact text view that exists in this workspace (view digest) and, for a report, to
the exact tested span (offsets + span digest recomputed from the bytes). An unbound report is rejected with the reason.
Raw response bytes are retained privately in the vault only when the import says disclosure permits it, and the
record keeps their digest either way. Bounded parsing (`core.strict_json`) refuses duplicate keys, floats, depth and size.
"""
from __future__ import annotations

from v3.receipts.contracts import ContractError, canonical_json
from v8.workbench.modules import envelope
from v8.workbench.modules.core import ModuleError, strict_json
from v8.workbench.store import Workspace
from v9.brief import compose, contracts
from v9.brief.sidecar import Sidecar, now_ts

MAX_IMPORT_BYTES = 1 << 20
RECORD_TYPES = {"receipt": "brief.generation_receipt", "report": "brief.detection_report", "calibration": "brief.calibration_record"}
CHECKS = {"receipt": contracts.check_generation_receipt, "report": contracts.check_detection_report, "calibration": contracts.check_calibration}
KINDS = {"receipt": "RECEIPT_IMPORTED", "report": "REPORT_IMPORTED", "calibration": "CALIBRATION_IMPORTED"}


def parse_import(data: bytes) -> dict:
    try:
        obj = strict_json(data, max_bytes=MAX_IMPORT_BYTES, code="IMPORT")
    except ModuleError as exc:
        raise ContractError(f"import refused: {exc.code} (duplicate keys, floats, non-finite numbers, excessive depth or size are refused before any field is read)") from None
    if not isinstance(obj, dict):
        raise ContractError("import refused: a JSON object is required")
    return obj


# ------------------------------------------------------------------ trust roots (the receiver's explicit policy)
def trust_roots(sc: Sidecar, recs: list | None = None) -> dict:
    roots = {}
    for r in sc.records(("TRUST_ROOT_ENROLLED", "TRUST_ROOT_REVOKED"), None, recs):
        p = r["payload"]
        if r["kind"] == "TRUST_ROOT_ENROLLED":
            roots[p["key_id"]] = {"public_key": p["public_key"], "label": p["label"], "revoked": False, "enrolled_at": r["time"]["recorded_at"], "issuer": p.get("issuer", "")}
        elif p["key_id"] in roots:
            roots[p["key_id"]]["revoked"] = True; roots[p["key_id"]]["revoked_reason"] = p.get("reason", "")
    return roots


def enroll_root(ws: Workspace, sc: Sidecar, *, public_key: str, label: str, issuer: str, actor: str, op_id: str) -> tuple[dict, bool]:
    import base64
    try:
        raw = base64.b64decode(public_key, validate=True)
    except (ValueError, TypeError):
        raise ContractError("public_key must be the base64 of a raw 32-byte Ed25519 key") from None
    if len(raw) != 32:
        raise ContractError("public_key must be a raw 32-byte Ed25519 key")
    kid = envelope.key_id(raw)
    if not label or len(label) > contracts.SHORT_MAX:
        raise ContractError("a label is required")
    with ws._locked():
        if kid in trust_roots(sc):
            raise ContractError(f"key {kid} is already enrolled (a revoked root is never revived; enroll a new key)")
        return sc._append_unlocked("TRUST_ROOT_ENROLLED", None, {"key_id": kid, "public_key": public_key, "label": label, "issuer": issuer or "", "algorithm": "Ed25519",
                                                                 "meaning": "this workspace's administrator chose to trust statements signed by this key; trust on first use never happens", "objects": []}, op_id=op_id, actor=actor)


def revoke_root(ws: Workspace, sc: Sidecar, *, key_id: str, reason: str, actor: str, op_id: str) -> tuple[dict, bool]:
    with ws._locked():
        roots = trust_roots(sc)
        if key_id not in roots:
            raise ContractError(f"key {key_id} is not enrolled")
        if roots[key_id]["revoked"]:
            raise ContractError(f"key {key_id} is already revoked")
        return sc._append_unlocked("TRUST_ROOT_REVOKED", None, {"key_id": key_id, "reason": reason or "revoked by the administrator", "objects": []}, op_id=op_id, actor=actor)


def signed_body(rec: dict) -> dict:
    """What an issuer signs: the record without its envelope and without its own identity."""
    return {k: v for k, v in rec.items() if k not in ("signature_envelope", "record_id", "provenance_note")}


def evaluate_signature(kind: str, rec: dict, roots: dict) -> dict:
    """{'signature': NONE|VALID|INVALID|UNVERIFIABLE, 'trust': NOT_EVALUATED|TRUSTED|UNKNOWN_SIGNER|REVOKED_ROOT, 'binding': NOT_APPLICABLE|BOUND|MISMATCH, 'key_id', 'reason'}"""
    env = rec.get("signature_envelope")
    if env is None:
        return {"signature": "NONE", "trust": "NOT_EVALUATED", "binding": "NOT_APPLICABLE", "key_id": None, "reason": "no signature envelope on this record"}
    v = envelope.verify(env, RECORD_TYPES[kind], {k: {"public_key": r["public_key"], "revoked": r["revoked"]} for k, r in roots.items()})
    out = {"signature": v["integrity"], "trust": v["trust"], "key_id": v["key_id"], "reason": v["reason"], "binding": "NOT_APPLICABLE"}
    if v["integrity"] == "VALID":
        body_ok = canonical_json(env.get("body")) == canonical_json(signed_body(rec))
        out["binding"] = "BOUND" if body_ok else "MISMATCH"
        if not body_ok:
            out["reason"] = "the signature verifies for the body inside the envelope, but that body differs from the record presented with it (payload mismatch: a valid signature on different bytes)"
    return out


# ------------------------------------------------------------------ binding to text views and spans
def _views(sc: Sidecar, recs: list | None = None) -> dict:
    out = {}
    for r in sc.records("BRIEF_VERSION_RECORDED", None, recs):
        out[r["payload"]["text_view"]["view_sha256"]] = r
    return out


def bind_report(sc: Sidecar, rep: dict) -> dict:
    views = _views(sc)
    r = views.get(rep["view_sha256"])
    if r is None:
        raise ContractError(f"report refused: view {rep['view_sha256'][:16]}… is not a text view of any brief version in this workspace (the report is unbound)")
    data = sc.get_bytes(rep["view_sha256"])
    sp = rep["span"]; problems = contracts.span_problems(data, sp["start"], sp["end"])
    if problems:
        raise ContractError("report refused: tested span invalid for that view: " + "; ".join(problems))
    actual = contracts.span_digest(data, sp["start"], sp["end"])
    if actual != sp["span_sha256"]:
        raise ContractError(f"report refused: span digest {sp['span_sha256'][:16]}… does not match the bytes {sp['start']}..{sp['end']} of the view ({actual[:16]}…)")
    return {"brief_id": r["brief_id"], "version_id": r["payload"]["version_id"], "language": r["payload"]["language"]}


def bind_receipt(sc: Sidecar, rec: dict) -> dict:
    views = _views(sc)
    r = views.get(rec["assembled_output_sha256"])
    if r is None:
        raise ContractError(f"receipt refused: assembled_output_sha256 {rec['assembled_output_sha256'][:16]}… is not a text view of any brief version here; a receipt binds to the exact assembled bytes")
    return {"brief_id": r["brief_id"], "version_id": r["payload"]["version_id"], "language": r["payload"]["language"]}


# ------------------------------------------------------------------ the import itself
def import_record(ws: Workspace, sc: Sidecar, *, kind: str, data: bytes, actor: str, op_id: str, raw_response: bytes | None = None, origin_label: str = "") -> tuple[dict, bool]:
    if kind not in CHECKS:
        raise ContractError("kind must be receipt, report or calibration")
    obj = parse_import(data)
    rec = contracts.validate(CHECKS[kind], obj, {"receipt": "generation receipt", "report": "detection report", "calibration": "calibration record"}[kind])
    with ws._locked():
        prior = sc.prior(op_id)
        bound = {}
        if kind == "report":
            bound = bind_report(sc, rec)
        elif kind == "receipt":
            bound = bind_receipt(sc, rec)
        if prior is None:
            dup = next((r for r in sc.records(KINDS[kind]) if r["payload"]["record"]["record_id"] == rec["record_id"]), None)
            if dup is not None:
                raise ContractError(f"{kind} refused: this exact record ({rec['record_id'][:16]}…) was already imported as sidecar record {dup['seq']} under op_id {dup['op_id']!r}; importing it again adds no observation (a retry repeats the same op_id)")
        roots = trust_roots(sc)
        sig = evaluate_signature(kind, rec, roots)
        if rec["origin"] == "issuer_signed" and sig["signature"] != "VALID":
            raise ContractError(f"{kind} refused: origin issuer_signed but the signature is {sig['signature']} ({sig['reason']}); an unsigned or mis-signed statement cannot be recorded as issuer-signed")
        if rec["origin"] == "issuer_signed" and sig["binding"] == "MISMATCH":
            raise ContractError(f"{kind} refused: {sig['reason']}")
        objects = [sc.put_bytes(data)]
        raw_obj = None
        if raw_response is not None:
            if rec.get("disclosure", rec.get("prompt_disclosure", "unknown")) == "permitted" or kind == "report" and rec.get("disclosure") == "permitted":
                raw_obj = sc.put_bytes(raw_response); objects.append(raw_obj)
            if rec.get("response_sha256") and contracts.sha256_hex(raw_response) != rec["response_sha256"]:
                raise ContractError("report refused: response_sha256 does not match the raw response bytes supplied")
        payload = {"kind": kind, "record": rec, "signature": sig, "bound_to": bound, "import_object": objects[0], "raw_response_object": raw_obj, "origin_label": origin_label or "",
                   "imported_at": (prior["payload"].get("imported_at") if prior else None) or now_ts(), "objects": objects}
        return sc._append_unlocked(KINDS[kind], bound.get("brief_id"), payload, op_id=op_id, actor=actor)


# ------------------------------------------------------------------ reading
def records_for_view(sc: Sidecar, view_sha256: str, recs: list | None = None) -> dict:
    out = {"receipts": [], "reports": []}
    for r in sc.records("RECEIPT_IMPORTED", None, recs):
        if r["payload"]["record"]["assembled_output_sha256"] == view_sha256:
            out["receipts"].append(r)
    for r in sc.records("REPORT_IMPORTED", None, recs):
        if r["payload"]["record"]["view_sha256"] == view_sha256:
            out["reports"].append(r)
    return out


def calibrations(sc: Sidecar, recs: list | None = None) -> dict:
    return {r["payload"]["record"]["record_id"]: r for r in sc.records("CALIBRATION_IMPORTED", None, recs)}


def calibration_applicability(report: dict, cal_rec: dict | None, language: str | None, cal_sig: dict | None = None) -> dict:
    """APPLICABLE only when the report says so AND a calibration record it names is present, in scope for this detector/
    configuration/key/language AND independently authenticated (issuer-signed and trusted by this receiver). An operator's
    imported calibration assertion stays NOT_ESTABLISHED: it does not masquerade as measured calibration."""
    claimed = report["calibration"]
    if report["execution"] != "COMPLETED":
        return {"applicability": "NOT_ESTABLISHED", "claimed": claimed, "reason": "no completed detector execution to calibrate"}
    if claimed != "APPLICABLE":
        return {"applicability": claimed, "claimed": claimed, "reason": "as stated by the report"}
    if cal_rec is None:
        return {"applicability": "NOT_ESTABLISHED", "claimed": claimed, "reason": f"calibration_ref {report.get('calibration_ref')} is not an enrolled calibration record here"}
    cal = cal_rec["payload"]["record"]; sig = cal_sig or cal_rec["payload"]["signature"]      # cal_sig: the evaluation under the receiver's CURRENT roots
    ok, why = contracts.calibration_scope_matches(report, cal, language)
    if not ok:
        return {"applicability": "OUT_OF_SCOPE", "claimed": claimed, "reason": "; ".join(why), "calibration_record": cal["record_id"]}
    if cal["origin"] != "issuer_signed" or sig["signature"] != "VALID" or sig["trust"] != "TRUSTED" or sig["binding"] != "BOUND":
        return {"applicability": "NOT_ESTABLISHED", "claimed": claimed, "calibration_record": cal["record_id"],
                "reason": f"the calibration record is {cal['origin']} (signature {sig['signature']}, trust {sig['trust']}); an imported assertion is not independently measured calibration"}
    return {"applicability": "APPLICABLE", "claimed": claimed, "calibration_record": cal["record_id"], "reason": "in scope and authenticated by a signer this workspace trusts; applicability is the record's, not a YUCLAW measurement",
            "confusion": cal["confusion"], "error_rate_plan": cal["error_rate_plan"], "interval_method": cal["interval_method"], "missing_strata": cal["missing_strata"]}
