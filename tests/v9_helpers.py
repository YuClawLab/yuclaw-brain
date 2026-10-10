"""Shared helpers of the v9 brief-engine test suite (tests/test_v9_brief_engine.py).

Everything here is local and deterministic: a fixture loader that mirrors `v8.workbench.server.load_fixture` (same op_ids,
so the resulting workspace is byte-for-byte the same journal), builders for well-formed DetectionReport/1 and
CalibrationRecord/1 records (unsigned, or signed by an issuer key through the v8 envelope), and a zip re-packer for
tamper tests. No network, no production paths.
"""
from __future__ import annotations

import io
import json
import pathlib
import re
import zipfile

from v8.workbench import schema
from v8.workbench.modules import envelope
from v9.brief import contracts, reports

REPO = pathlib.Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO / "tests" / "fixtures" / "v8" / "commitments"
FIXTURE_CLAIM_ID = "ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base"
_FIXTURE_ID = re.compile(r"^[0-9]{3}_[a-z0-9_]+$")


def _load_fixture_local(ws, fid: str) -> str:
    """The same writes, in the same order, under the same op_ids as server.load_fixture (kept in step with it on purpose)."""
    p = FIXTURES_DIR / f"{fid}.json"
    if not _FIXTURE_ID.match(fid) or not p.is_file():
        raise ValueError(f"unknown fixture {fid!r}")
    fx = json.loads(p.read_text()); rec = schema.from_fixture(fx)
    cid = f"{rec['claim']['claim_id']}--{fx['fixture_id']}"
    rec["claim"] = dict(rec["claim"], claim_id=cid)
    for r in rec["revisions"]:
        if r.get("claim"):
            r["claim"] = dict(r["claim"], claim_id=cid)
    tag = f"fx:{fx['fixture_id']}"
    ws.register_source(rec["claim"]["source"], op_id=f"{tag}:src:{rec['claim']['source']['accession']}", observed_at=rec["claim"]["source"]["available_as_of"])
    ws.freeze_claim(rec["claim"], op_id=f"{tag}:freeze", observed_at=rec["claim"]["source"]["available_as_of"])
    for r in rec["revisions"]:
        ws.register_source(r["source"], op_id=f"{tag}:src:{r['source']['accession']}", observed_at=r["source"]["available_as_of"])
        if r["type"] == "WITHDRAWN":
            ws.amend_claim(cid, "WITHDRAWN", changes=None, reason=r["reason"] or "withdrawn per fixture", source=r["source"], op_id=f"{tag}:{r['revision_id']}", observed_at=r["source"]["available_as_of"])
        else:
            c = r["claim"]
            ws.amend_claim(cid, r["type"], changes={"range": c["range"], "basis": c["basis"], "unit": c["unit"], "currency": c["currency"], "statement": c["statement"], "fiscal_period": c["fiscal_period"], "metric": c["metric"]},
                           reason=r["reason"] or f"{r['type']} per fixture", source=r["source"], op_id=f"{tag}:{r['revision_id']}", observed_at=r["source"]["available_as_of"])
    if rec["outcome"]:
        ws.register_source(rec["outcome"]["source"], op_id=f"{tag}:src:{rec['outcome']['source']['accession']}", observed_at=rec["outcome"]["source"]["available_as_of"])
        ws.record_outcome(cid, rec["outcome"], op_id=f"{tag}:outcome", observed_at=rec["outcome"]["source"]["available_as_of"])
    return cid


def load_fixture(ws, fid: str = "001_base") -> str:
    """Prefer the product's own loader; fall back to the local mirror when the workbench server module cannot be imported
    (its UI modules may be mid-edit in this worktree; the engine under test does not depend on them)."""
    try:
        from v8.workbench import server
        return server.load_fixture(ws, fid)
    except (ImportError, SyntaxError):
        return _load_fixture_local(ws, fid)


# ------------------------------------------------------------------ provenance records
DIAGS = {"threshold": "0.5", "p_value": "0.01", "scored_context_count": "120", "key_epoch": "7"}


def report_raw(view_sha256: str, data: bytes, start: int, end: int, *, execution="COMPLETED", signal="DETECTED", calibration="NOT_ESTABLISHED", calibration_ref=None,
               detector="wm-detector", detector_version="1.0", key_scope=None, failure_reason=None, diagnostics=None, configuration=None, span_sha256=None, disclosure="withheld") -> dict:
    """An unsigned (operator_assertion) DetectionReport/1 over the exact span start..end of `data`."""
    return {"schema": contracts.DETECTION_REPORT, "view_sha256": view_sha256,
            "span": {"start": start, "end": end, "span_sha256": span_sha256 or contracts.span_digest(data, start, end)},
            "detector": detector, "detector_version": detector_version, "configuration": configuration or {}, "key_scope": key_scope,
            "execution": execution, "signal": signal, "calibration": calibration, "failure_reason": failure_reason,
            "diagnostics": dict(DIAGS) if diagnostics is None else diagnostics, "origin": "operator_assertion",
            "observed_at": "2026-10-01T00:00:00Z", "disclosure": disclosure, "calibration_ref": calibration_ref}


def calibration_raw(*, detector="wm-detector", detector_version="1.0", languages=("en",), key_scope=None, configuration=None) -> dict:
    return {"schema": contracts.CALIBRATION_RECORD, "detector": detector, "detector_version": detector_version, "configuration": configuration or {}, "key_scope": key_scope,
            "corpus": "fictional calibration corpus", "label_provenance": "synthetic labels (fictional)", "languages": list(languages), "domains": ["finance"],
            "length_strata": ["100-500 bytes"], "test_unit": "sentence", "selection_rule": "every sentence", "split": "held-out", "error_rate_plan": "FPR <= 1%",
            "confusion": {"tp": 90, "fp": 1, "tn": 99, "fn": 10}, "interval_method": "Clopper-Pearson", "missing_strata": [], "origin": "operator_assertion",
            "observed_at": "2026-10-01T00:00:00Z"}


def issuer_sign(kind: str, raw: dict, private_pem: bytes) -> dict:
    """Normalize through the contract, sign the normalized body (origin issuer_signed) and attach the envelope — the way an
    issuer would produce a record this receiver can bind."""
    norm, reasons = reports.CHECKS[kind](raw)
    if reasons:
        raise AssertionError(f"test record is not well formed: {reasons}")
    body = reports.signed_body(norm); body["origin"] = "issuer_signed"
    env = envelope.sign(reports.RECORD_TYPES[kind], body, private_pem)
    return dict(body, signature_envelope=env)


def jbytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


# ------------------------------------------------------------------ zips
def zip_members(path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i) for i in z.infolist()}


def rezip(members: dict[str, bytes], out_path) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    pathlib.Path(out_path).write_bytes(buf.getvalue())
    return str(out_path)
