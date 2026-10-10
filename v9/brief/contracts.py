"""Versioned record contracts of the v9 brief layer (the names the order calls ArtifactRecord/1 … BriefPacket/1).

Every validator returns (normalized record, []) or (None, [every blocking reason]) in the style of v8.workbench.schema,
and never coerces: a float, a character offset, an offset inside a multi-byte sequence, an unknown status word or a
status combination the contract forbids is a reason, not a guess. Bytes are the unit of binding: a TextView is an
exact UTF-8 byte string with a digest; a ClaimSpan addresses it by half-open UTF-8 BYTE offsets (never a UI's
character offsets) and carries the digest of exactly those bytes. Normalization creates a NAMED view with its own
digest; it never rewrites an original.

Record identities are content digests (sha256 of the canonical JSON of the record without its own identity field),
so the same record has one identity everywhere and a self-referential hash is never inside its own signed body.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from v3.receipts.contracts import ContractError, canonical_json, digest
from v8.workbench import money
from v8.workbench.schema import _PRINTABLE, parse_ts

# ------------------------------------------------------------------ schema names (versioned; unknown versions are refused, never reinterpreted)
ARTIFACT = "yuclaw.artifact-record/1"
TEXT_VIEW = "yuclaw.text-view/1"
CLAIM_SPAN = "yuclaw.claim-span/1"
GENERATION_RECEIPT = "yuclaw.generation-receipt/1"
DETECTION_REPORT = "yuclaw.detection-report/1"
TRANSFORM_RECORD = "yuclaw.transform-record/1"
CALIBRATION_RECORD = "yuclaw.calibration-record/1"
BRIEF_PACKET = "yuclaw.brief-packet/1"
EVIDENCE_SNAPSHOT = "yuclaw.evidence-snapshot/1"
BRIEF_VERSION = "yuclaw.brief-version/1"
REVIEW_ITEM = "yuclaw.review-item/1"
SUPPORTED_SCHEMAS = (ARTIFACT, TEXT_VIEW, CLAIM_SPAN, GENERATION_RECEIPT, DETECTION_REPORT, TRANSFORM_RECORD, CALIBRATION_RECORD, BRIEF_PACKET, EVIDENCE_SNAPSHOT, BRIEF_VERSION, REVIEW_ITEM)

# ------------------------------------------------------------------ vocabularies (closed sets)
ROLES = ("direct_quotation", "computed_statement", "attributed_source_statement", "analyst_interpretation", "generated_commentary", "unresolved_claim")
SUPPORT = ("SUPPORTED", "ATTRIBUTED", "UNRESOLVED", "CONTRADICTED", "NOT_ASSESSED", "INVALIDATED")
SUPPORT_METHODS = ("exact_quotation_match/1", "registered_arithmetic/1", "typed_slot_render/1", "method_statement/1", "assessor_assertion/1", "none")
EXECUTION = ("NOT_REQUESTED", "ACCESS_UNAVAILABLE", "UNSUPPORTED", "INSUFFICIENT_INPUT", "COMPLETED", "FAILED")
SIGNAL = ("DETECTED", "NOT_DETECTED", "INCONCLUSIVE")
CALIBRATION = ("APPLICABLE", "OUT_OF_SCOPE", "NOT_ESTABLISHED")
ORIGIN_KINDS = ("operator_assertion", "connector_observed", "issuer_signed")
TRANSFORM_KINDS = ("template_render", "import", "edit", "translate", "span_correction")
RECORDING_METHODS = ("template_deterministic", "operator_entered", "imported_file", "connector_observed")
MAPPING_METHODS = ("identity", "exact_bytes_unique/1", "operator_mapped/1", "none")
LANGUAGES = ("en", "fr")
MEDIA_TYPES = ("text/plain; charset=utf-8", "text/markdown; charset=utf-8", "text/html; charset=utf-8", "application/json", "application/pdf", "application/octet-stream")
COLLECTION_METHODS = ("v8_source_registration", "operator_entered", "imported_file", "template_render", "connector_observed")
NORMALIZATION_POLICIES = ("none", "NFC/1", "NFKC/1")
CHECK_OUTCOMES = ("VERIFIED", "FAILED", "NOT_RECOMPUTABLE", "REPORT_ONLY", "UNSUPPORTED", "NOT_APPLICABLE")
REVIEW_REASONS = ("SOURCE_AVAILABILITY_CORRECTED", "CLAIM_AMENDED", "CLAIM_WITHDRAWN", "OUTCOME_CHANGED", "SPAN_UNMAPPED", "PROTECTED_FACT_CHANGED", "PROSE_CONTRADICTS_PROTECTED_FACT", "OPERATOR_FLAG")
DISCLOSURE = ("permitted", "withheld", "unknown")
RIGHTS = ("FICTIONAL", "SEC_PUBLIC_FILING", "COMPANY_PRESS_RELEASE", "UNKNOWN", "OPERATOR_OWN_TEXT")
BUNDLE_RIGHTS = ("FICTIONAL", "SEC_PUBLIC_FILING", "OPERATOR_OWN_TEXT")      # the only rights classes whose bytes travel in a packet

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(V1|R[0-9]{1,3}|C[0-9]{1,3})$")
_BRIEF_VERSION = re.compile(r"^B[0-9]{1,4}$")
_LANG = re.compile(r"^(en|fr)$")
TEXT_MAX = 65536                 # one brief text view (bytes)
FIELD_MAX = 2000                 # one free-text field
SHORT_MAX = 240
MAX_SPANS = 500
MAX_LINKS = 64
MAX_LIST = 200


# ------------------------------------------------------------------ bytes and spans
def utf8_boundary(data: bytes, off: int) -> bool:
    """True when `off` is 0, len(data), or the first byte of a UTF-8 sequence (never a continuation byte 10xxxxxx)."""
    if off == 0 or off == len(data):
        return True
    if off < 0 or off > len(data):
        return False
    return (data[off] & 0xC0) != 0x80


def span_problems(data: bytes, start, end) -> list[str]:
    reasons = []
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int):
        return ["span: integer byte offsets required (a UI's character offsets must be converted to UTF-8 byte offsets)"]
    if start < 0 or end > len(data):
        reasons.append(f"span: offsets {start}..{end} outside the view of {len(data)} bytes")
    elif start >= end:
        reasons.append(f"span: half-open range needs start < end (got {start}..{end})")
    else:
        if not utf8_boundary(data, start):
            reasons.append(f"span: start offset {start} is inside a multi-byte UTF-8 sequence")
        if not utf8_boundary(data, end):
            reasons.append(f"span: end offset {end} is inside a multi-byte UTF-8 sequence")
    return reasons


def span_digest(data: bytes, start: int, end: int) -> str:
    return hashlib.sha256(data[start:end]).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_text(text: str, policy: str) -> str:
    if policy == "none":
        return text
    if policy == "NFC/1":
        return unicodedata.normalize("NFC", text)
    if policy == "NFKC/1":
        return unicodedata.normalize("NFKC", text)
    raise ContractError(f"normalization policy {policy!r} unknown")


def record_identity(rec: dict, *, exclude=("record_id",)) -> str:
    """sha256 of the canonical JSON of the record without its own identity (never a self-referential hash)."""
    return digest({k: v for k, v in rec.items() if k not in exclude})


# ------------------------------------------------------------------ small field helpers (reasons, never exceptions)
def _s(v, field, maxlen, reasons, *, required=True) -> str | None:
    if v is None or v == "":
        if required:
            reasons.append(f"{field}: required")
        return None
    if not isinstance(v, str) or len(v) > maxlen or not _PRINTABLE.match(v):
        reasons.append(f"{field}: text up to {maxlen} characters without control characters required"); return None
    return v


def _enum(v, field, allowed, reasons, *, required=True):
    if v is None and not required:
        return None
    if v not in allowed:
        reasons.append(f"{field}: one of {list(allowed)} required (got {v!r})"); return None
    return v


def _hex(v, field, reasons, *, required=True):
    if v is None and not required:
        return None
    if not isinstance(v, str) or not _HEX64.match(v):
        reasons.append(f"{field}: sha256 hex digest required"); return None
    return v


def _ident(v, field, reasons, *, required=True, pat=_ID):
    if v is None and not required:
        return None
    if not isinstance(v, str) or not pat.match(v):
        reasons.append(f"{field}: identifier required"); return None
    return v


def _ts(v, field, reasons, *, required=True):
    if v is None and not required:
        return None
    try:
        parse_ts(v); return v
    except ContractError as exc:
        reasons.append(f"{field}: {exc}"); return None


def _int(v, field, reasons, *, lo=0, hi=10 ** 15, required=True):
    if v is None and not required:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or v < lo or v > hi:
        reasons.append(f"{field}: integer in {lo}..{hi} required"); return None
    return v


def _bool(v, field, reasons, *, required=True):
    if v is None and not required:
        return None
    if not isinstance(v, bool):
        reasons.append(f"{field}: boolean required"); return None
    return v


def _list(v, field, reasons, *, maxlen=MAX_LIST, required=False):
    if v is None:
        if required:
            reasons.append(f"{field}: list required")
        return []
    if not isinstance(v, list) or len(v) > maxlen:
        reasons.append(f"{field}: list of at most {maxlen} items required"); return []
    return v


def _unknowns(v, field, reasons) -> dict:
    """{field_name: reason} — every unexposed quantity names WHY it is unknown; a bare null is not an explanation."""
    if v is None:
        return {}
    if not isinstance(v, dict) or len(v) > 64:
        reasons.append(f"{field}: object {{name: reason}} required"); return {}
    out = {}
    for k, why in v.items():
        if not isinstance(k, str) or not _ID.match(k):
            reasons.append(f"{field}: key {k!r} is not an identifier"); continue
        r = _s(why, f"{field}.{k}", SHORT_MAX, reasons)
        if r is not None:
            out[k] = r
    return out


def check_decimal_string(v, field, reasons, *, required=True) -> str | None:
    """A finite decimal given as a canonical string or an integer (never a float, NaN or exponent form)."""
    if v is None and not required:
        return None
    if isinstance(v, float):
        reasons.append(f"{field}: floating point is refused; give a decimal string"); return None
    try:
        d = money.parse_amount(v, field)
    except ContractError as exc:
        reasons.append(str(exc)); return None
    if not d.is_finite():
        reasons.append(f"{field}: non-finite value refused"); return None
    return format(d, "f") if isinstance(v, str) else money.to_json(d)


def percent_string(v, field, reasons, *, required=False) -> str | None:
    """A diagnostic like a p-value or score: finite decimal string in [0, 1] or a plain finite decimal; floats refused."""
    if v is None and not required:
        return None
    if isinstance(v, float) or isinstance(v, bool):
        reasons.append(f"{field}: floating point is refused; give a decimal string"); return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        reasons.append(f"{field}: decimal string required"); return None
    if not d.is_finite():
        reasons.append(f"{field}: non-finite value refused"); return None
    return format(d, "f")


# ------------------------------------------------------------------ ArtifactRecord/1
def check_artifact(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["artifact: object required"]
    if raw.get("schema") != ARTIFACT:
        reasons.append(f"artifact.schema: {ARTIFACT!r} required")
    out = {"schema": ARTIFACT,
           "content_sha256": _hex(raw.get("content_sha256"), "artifact.content_sha256", reasons),
           "byte_length": _int(raw.get("byte_length"), "artifact.byte_length", reasons, hi=1 << 31),
           "media_type": _enum(raw.get("media_type"), "artifact.media_type", MEDIA_TYPES, reasons),
           "encoding": _s(raw.get("encoding", "utf-8"), "artifact.encoding", 32, reasons),
           "rights": _enum(raw.get("rights"), "artifact.rights", RIGHTS, reasons),
           "collection_method": _enum(raw.get("collection_method"), "artifact.collection_method", COLLECTION_METHODS, reasons),
           "asserted_available_as_of": _ts(raw.get("asserted_available_as_of"), "artifact.asserted_available_as_of", reasons, required=False),
           "observed_at": _ts(raw.get("observed_at"), "artifact.observed_at", reasons),
           "label": _s(raw.get("label"), "artifact.label", SHORT_MAX, reasons, required=False) or "",
           "parents": [], "v8_source_id": _s(raw.get("v8_source_id"), "artifact.v8_source_id", SHORT_MAX, reasons, required=False)}
    for i, p in enumerate(_list(raw.get("parents"), "artifact.parents", reasons, maxlen=16)):
        h = _hex(p, f"artifact.parents[{i}]", reasons)
        if h:
            out["parents"].append(h)
    if reasons:
        return None, reasons
    out["record_id"] = record_identity(out)
    return out, []


# ------------------------------------------------------------------ TextView/1
def make_text_view(data: bytes, *, source_artifact: str | None, extraction: str, normalization: str, language: str | None, location_map: list | None = None) -> dict:
    """Build a TextView over exact bytes. `extraction` names the tool/version that produced the view (e.g. the template
    renderer, the operator form, an import); `normalization` is one of NORMALIZATION_POLICIES and names the view."""
    if not isinstance(data, (bytes, bytearray)):
        raise ContractError("text view: bytes required")
    if len(data) > TEXT_MAX:
        raise ContractError(f"text view: at most {TEXT_MAX} bytes")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(f"text view: not valid UTF-8 ({exc.reason} at byte {exc.start})") from None
    if normalization not in NORMALIZATION_POLICIES:
        raise ContractError(f"text view: normalization policy {normalization!r} unknown")
    if language is not None and not _LANG.match(language):
        raise ContractError("text view: language must be en or fr")
    view = {"schema": TEXT_VIEW, "source_artifact": source_artifact, "extraction": extraction, "normalization": normalization, "language": language,
            "view_sha256": sha256_hex(bytes(data)), "byte_length": len(data), "location_map": location_map or []}
    view["record_id"] = view["view_sha256"]                  # a view IS its bytes: one byte string, one identity
    return view


def check_text_view(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["text_view: object required"]
    if raw.get("schema") != TEXT_VIEW:
        reasons.append(f"text_view.schema: {TEXT_VIEW!r} required")
    out = {"schema": TEXT_VIEW, "source_artifact": _hex(raw.get("source_artifact"), "text_view.source_artifact", reasons, required=False),
           "extraction": _s(raw.get("extraction"), "text_view.extraction", SHORT_MAX, reasons),
           "normalization": _enum(raw.get("normalization"), "text_view.normalization", NORMALIZATION_POLICIES, reasons),
           "language": _enum(raw.get("language"), "text_view.language", LANGUAGES, reasons, required=False),
           "view_sha256": _hex(raw.get("view_sha256"), "text_view.view_sha256", reasons),
           "byte_length": _int(raw.get("byte_length"), "text_view.byte_length", reasons, hi=TEXT_MAX),
           "location_map": _list(raw.get("location_map"), "text_view.location_map", reasons, maxlen=MAX_SPANS)}
    if reasons:
        return None, reasons
    out["record_id"] = out["view_sha256"]
    return out, []


# ------------------------------------------------------------------ ClaimSpan/1
def check_claim_span(raw, view_bytes: bytes | None = None) -> tuple[dict | None, list[str]]:
    """When `view_bytes` is given the span is checked against the actual bytes: boundaries, range and digest."""
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["span: object required"]
    if raw.get("schema") != CLAIM_SPAN:
        reasons.append(f"span.schema: {CLAIM_SPAN!r} required")
    start, end = raw.get("start"), raw.get("end")
    if view_bytes is not None:
        reasons += span_problems(view_bytes, start, end)
    elif isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
        reasons.append("span: half-open integer byte offsets start < end required")
    out = {"schema": CLAIM_SPAN, "view_sha256": _hex(raw.get("view_sha256"), "span.view_sha256", reasons), "start": start, "end": end,
           "span_sha256": _hex(raw.get("span_sha256"), "span.span_sha256", reasons),
           "role": _enum(raw.get("role"), "span.role", ROLES, reasons),
           "claim": None, "evidence": [], "calculation": raw.get("calculation"),
           "support": _enum(raw.get("support"), "span.support", SUPPORT, reasons),
           "method": _enum(raw.get("method"), "span.method", SUPPORT_METHODS, reasons),
           "assessor": _s(raw.get("assessor"), "span.assessor", SHORT_MAX, reasons),
           "limits": _s(raw.get("limits"), "span.limits", FIELD_MAX, reasons, required=False) or "",
           "protected": []}
    c = raw.get("claim")
    if c is not None:
        if not isinstance(c, dict):
            reasons.append("span.claim: object {claim_id, version_id, claim_digest} or null")
        else:
            out["claim"] = {"claim_id": _ident(c.get("claim_id"), "span.claim.claim_id", reasons), "version_id": _ident(c.get("version_id"), "span.claim.version_id", reasons, pat=_VERSION),
                            "claim_digest": _hex(c.get("claim_digest"), "span.claim.claim_digest", reasons)}
    for i, e in enumerate(_list(raw.get("evidence"), "span.evidence", reasons, maxlen=MAX_LINKS)):
        if not isinstance(e, dict):
            reasons.append(f"span.evidence[{i}]: object required"); continue
        out["evidence"].append({"kind": _enum(e.get("kind"), f"span.evidence[{i}].kind", ("source_excerpt", "claim_version", "outcome", "calculation", "v8_event", "artifact"), reasons),
                                "ref": _s(e.get("ref"), f"span.evidence[{i}].ref", SHORT_MAX, reasons),
                                "digest": _hex(e.get("digest"), f"span.evidence[{i}].digest", reasons, required=False)})
    if out["calculation"] is not None and not isinstance(out["calculation"], dict):
        reasons.append("span.calculation: object or null")
    for i, p in enumerate(_list(raw.get("protected"), "span.protected", reasons, maxlen=32)):
        if not isinstance(p, dict):
            reasons.append(f"span.protected[{i}]: object required"); continue
        ps, pe = p.get("start"), p.get("end")
        if view_bytes is not None:
            reasons += [f"protected[{i}] {r}" for r in span_problems(view_bytes, ps, pe)]
            if isinstance(ps, int) and isinstance(pe, int) and isinstance(start, int) and isinstance(end, int) and not (start <= ps < pe <= end):
                reasons.append(f"span.protected[{i}]: slot {ps}..{pe} is not inside its sentence {start}..{end}")
        out["protected"].append({"slot": _s(p.get("slot"), f"span.protected[{i}].slot", 64, reasons), "value": _s(p.get("value"), f"span.protected[{i}].value", SHORT_MAX, reasons),
                                 "start": ps, "end": pe})
    if out["support"] == "SUPPORTED" and out["method"] in ("assessor_assertion/1", "none"):
        reasons.append("span.support: SUPPORTED needs a deterministic method (an assessor's assertion is ATTRIBUTED, never SUPPORTED)")
    if out["role"] == "unresolved_claim" and out["support"] not in ("UNRESOLVED", "CONTRADICTED", "INVALIDATED"):
        reasons.append("span.support: an unresolved_claim is UNRESOLVED or CONTRADICTED by definition")
    if view_bytes is not None and not reasons:
        actual = span_digest(view_bytes, start, end)
        if actual != out["span_sha256"]:
            reasons.append(f"span.span_sha256: does not match the bytes {start}..{end} of the view ({actual[:16]}…)")
    if reasons:
        return None, reasons
    out["record_id"] = record_identity(out)
    return out, []


# ------------------------------------------------------------------ GenerationReceipt/1
def check_generation_receipt(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["receipt: object required"]
    if raw.get("schema") != GENERATION_RECEIPT:
        reasons.append(f"receipt.schema: {GENERATION_RECEIPT!r} required")
    out = {"schema": GENERATION_RECEIPT,
           "origin": _enum(raw.get("origin"), "receipt.origin", ORIGIN_KINDS, reasons),
           "recording_method": _enum(raw.get("recording_method"), "receipt.recording_method", RECORDING_METHODS, reasons),
           "inputs": [], "template": _s(raw.get("template"), "receipt.template", SHORT_MAX, reasons, required=False),
           "prompt_sha256": _hex(raw.get("prompt_sha256"), "receipt.prompt_sha256", reasons, required=False),
           "prompt_disclosure": _enum(raw.get("prompt_disclosure", "unknown"), "receipt.prompt_disclosure", DISCLOSURE, reasons),
           "provider": _s(raw.get("provider"), "receipt.provider", SHORT_MAX, reasons, required=False),
           "model": _s(raw.get("model"), "receipt.model", SHORT_MAX, reasons, required=False),
           "settings": raw.get("settings") if isinstance(raw.get("settings"), dict) else {},
           "raw_output_sha256": _hex(raw.get("raw_output_sha256"), "receipt.raw_output_sha256", reasons, required=False),
           "assembled_output_sha256": _hex(raw.get("assembled_output_sha256"), "receipt.assembled_output_sha256", reasons),
           "request_id": _s(raw.get("request_id"), "receipt.request_id", SHORT_MAX, reasons, required=False),
           "issued_at": _ts(raw.get("issued_at"), "receipt.issued_at", reasons, required=False),
           "observed_at": _ts(raw.get("observed_at"), "receipt.observed_at", reasons),
           "unknown": _unknowns(raw.get("unknown"), "receipt.unknown", reasons),
           "signature_envelope": raw.get("signature_envelope") if isinstance(raw.get("signature_envelope"), dict) else None}
    for i, ref in enumerate(_list(raw.get("inputs"), "receipt.inputs", reasons, maxlen=MAX_LINKS)):
        h = _hex(ref, f"receipt.inputs[{i}]", reasons)
        if h:
            out["inputs"].append(h)
    if len(canonical_json(out["settings"])) > 8192:
        reasons.append("receipt.settings: too large")
    if out["origin"] == "issuer_signed" and out["signature_envelope"] is None:
        reasons.append("receipt.origin: issuer_signed requires a signature_envelope (a filename, screenshot or request id is not a provider signature)")
    if out["origin"] == "connector_observed" and out["recording_method"] != "connector_observed":
        reasons.append("receipt.origin: connector_observed requires recording_method connector_observed")
    if out["recording_method"] == "template_deterministic" and not out["template"]:
        reasons.append("receipt.template: required for a deterministic template rendering")
    if out["recording_method"] != "template_deterministic":
        for k in ("provider", "model"):
            if not out[k] and k not in out["unknown"]:
                reasons.append(f"receipt.{k}: give the value or an explicit unknown reason under receipt.unknown.{k}")
        if not out["settings"] and "settings" not in out["unknown"]:
            reasons.append("receipt.settings: give the exposed settings or an explicit unknown reason under receipt.unknown.settings")
    if out["raw_output_sha256"] and out["raw_output_sha256"] == out["assembled_output_sha256"] and out["recording_method"] != "template_deterministic":
        out["note_same_bytes"] = "raw and assembled outputs are the same bytes; any later citation, substitution or rendering creates different bytes and a new view"
    if reasons:
        return None, reasons
    out["record_id"] = record_identity(out)
    return out, []


# ------------------------------------------------------------------ DetectionReport/1
def report_combination_problems(execution, signal, calibration, failure_reason) -> list[str]:
    reasons = []
    if execution not in EXECUTION:
        return [f"report.execution: one of {list(EXECUTION)} required (got {execution!r})"]
    if execution == "COMPLETED":
        if signal not in SIGNAL:
            reasons.append(f"report.signal: one of {list(SIGNAL)} required when execution is COMPLETED (got {signal!r})")
    else:
        if signal is not None:
            reasons.append(f"report.signal: must be absent unless execution is COMPLETED ({execution} cannot become {signal})")
        if execution != "NOT_REQUESTED" and not failure_reason:
            reasons.append(f"report.failure_reason: required for execution {execution} (the reason for failure or ineligibility is preserved)")
    if calibration not in CALIBRATION:
        reasons.append(f"report.calibration: one of {list(CALIBRATION)} required (got {calibration!r})")
    elif calibration == "APPLICABLE" and execution != "COMPLETED":
        reasons.append("report.calibration: APPLICABLE is meaningless without a COMPLETED execution")
    return reasons


def check_detection_report(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["report: object required"]
    if raw.get("schema") != DETECTION_REPORT:
        reasons.append(f"report.schema: {DETECTION_REPORT!r} required")
    ex, sig, cal = raw.get("execution"), raw.get("signal"), raw.get("calibration")
    fr = _s(raw.get("failure_reason"), "report.failure_reason", FIELD_MAX, reasons, required=False)
    reasons += report_combination_problems(ex, sig, cal, fr)
    span = raw.get("span")
    if not isinstance(span, dict) or not isinstance(span.get("start"), int) or not isinstance(span.get("end"), int) or isinstance(span.get("start"), bool) or isinstance(span.get("end"), bool):
        reasons.append("report.span: object {start, end, span_sha256} with integer byte offsets required (the exact tested span)")
        span = {}
    out = {"schema": DETECTION_REPORT,
           "view_sha256": _hex(raw.get("view_sha256"), "report.view_sha256", reasons),
           "span": {"start": span.get("start"), "end": span.get("end"), "span_sha256": _hex(span.get("span_sha256"), "report.span.span_sha256", reasons)},
           "detector": _s(raw.get("detector"), "report.detector", SHORT_MAX, reasons),
           "detector_version": _s(raw.get("detector_version"), "report.detector_version", SHORT_MAX, reasons, required=False),
           "configuration": raw.get("configuration") if isinstance(raw.get("configuration"), dict) else {},
           "key_scope": _s(raw.get("key_scope"), "report.key_scope", SHORT_MAX, reasons, required=False),
           "execution": ex, "signal": sig if ex == "COMPLETED" else None, "calibration": cal, "failure_reason": fr,
           "diagnostics": {}, "origin": _enum(raw.get("origin"), "report.origin", ORIGIN_KINDS, reasons),
           "response_sha256": _hex(raw.get("response_sha256"), "report.response_sha256", reasons, required=False),
           "selection": _s(raw.get("selection"), "report.selection", FIELD_MAX, reasons, required=False) or "",
           "test_family": _s(raw.get("test_family"), "report.test_family", SHORT_MAX, reasons, required=False),
           "calibration_ref": _hex(raw.get("calibration_ref"), "report.calibration_ref", reasons, required=False),
           "observed_at": _ts(raw.get("observed_at"), "report.observed_at", reasons),
           "issued_at": _ts(raw.get("issued_at"), "report.issued_at", reasons, required=False),
           "cache_reuse": _bool(raw.get("cache_reuse", False), "report.cache_reuse", reasons),
           "disclosure": _enum(raw.get("disclosure", "unknown"), "report.disclosure", DISCLOSURE, reasons),
           "unknown": _unknowns(raw.get("unknown"), "report.unknown", reasons),
           "signature_envelope": raw.get("signature_envelope") if isinstance(raw.get("signature_envelope"), dict) else None}
    diags = raw.get("diagnostics")
    if diags is not None:
        if not isinstance(diags, dict) or len(diags) > 32:
            reasons.append("report.diagnostics: object of at most 32 decimal-string values")
        else:
            for k, v in diags.items():
                if not isinstance(k, str) or not _ID.match(k):
                    reasons.append(f"report.diagnostics: key {k!r} is not an identifier"); continue
                d = percent_string(v, f"report.diagnostics.{k}", reasons, required=True)
                if d is not None:
                    out["diagnostics"][k] = d
    if len(canonical_json(out["configuration"])) > 8192:
        reasons.append("report.configuration: too large")
    for k in ("threshold", "p_value", "scored_context_count", "key_epoch"):
        if k not in out["diagnostics"] and k not in out["configuration"] and k not in out["unknown"]:
            reasons.append(f"report: {k} must be supplied (diagnostics/configuration) or declared unavailable under report.unknown.{k}; it is never inferred from a paper")
    if out["calibration"] == "APPLICABLE" and not out["calibration_ref"]:
        reasons.append("report.calibration: APPLICABLE requires calibration_ref (the CalibrationRecord it rests on)")
    if out["origin"] == "issuer_signed" and out["signature_envelope"] is None:
        reasons.append("report.origin: issuer_signed requires a signature_envelope")
    if out["cache_reuse"] and out["execution"] == "COMPLETED":
        out["note_cache"] = "cache reuse: this is a repeated earlier observation, not a new detector observation"
    if reasons:
        return None, reasons
    out["record_id"] = record_identity(out)
    return out, []


# ------------------------------------------------------------------ CalibrationRecord/1
def check_calibration(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["calibration: object required"]
    if raw.get("schema") != CALIBRATION_RECORD:
        reasons.append(f"calibration.schema: {CALIBRATION_RECORD!r} required")
    out = {"schema": CALIBRATION_RECORD,
           "detector": _s(raw.get("detector"), "calibration.detector", SHORT_MAX, reasons),
           "detector_version": _s(raw.get("detector_version"), "calibration.detector_version", SHORT_MAX, reasons, required=False),
           "configuration": raw.get("configuration") if isinstance(raw.get("configuration"), dict) else {},
           "key_scope": _s(raw.get("key_scope"), "calibration.key_scope", SHORT_MAX, reasons, required=False),
           "corpus": _s(raw.get("corpus"), "calibration.corpus", FIELD_MAX, reasons),
           "label_provenance": _s(raw.get("label_provenance"), "calibration.label_provenance", FIELD_MAX, reasons),
           "languages": [], "domains": [], "length_strata": [],
           "test_unit": _s(raw.get("test_unit"), "calibration.test_unit", SHORT_MAX, reasons),
           "selection_rule": _s(raw.get("selection_rule"), "calibration.selection_rule", FIELD_MAX, reasons),
           "split": _s(raw.get("split"), "calibration.split", SHORT_MAX, reasons),
           "error_rate_plan": _s(raw.get("error_rate_plan"), "calibration.error_rate_plan", FIELD_MAX, reasons),
           "confusion": {}, "interval_method": _s(raw.get("interval_method"), "calibration.interval_method", SHORT_MAX, reasons),
           "missing_strata": [], "origin": _enum(raw.get("origin"), "calibration.origin", ORIGIN_KINDS, reasons),
           "observed_at": _ts(raw.get("observed_at"), "calibration.observed_at", reasons),
           "signature_envelope": raw.get("signature_envelope") if isinstance(raw.get("signature_envelope"), dict) else None}
    for i, l in enumerate(_list(raw.get("languages"), "calibration.languages", reasons, maxlen=16, required=True)):
        v = _enum(l, f"calibration.languages[{i}]", LANGUAGES + ("other",), reasons)
        if v:
            out["languages"].append(v)
    if not out["languages"]:
        reasons.append("calibration.languages: at least one language")
    for key, maxlen in (("domains", 32), ("length_strata", 32), ("missing_strata", 32)):
        for i, v in enumerate(_list(raw.get(key), f"calibration.{key}", reasons, maxlen=maxlen)):
            s = _s(v, f"calibration.{key}[{i}]", SHORT_MAX, reasons)
            if s:
                out[key].append(s)
    conf = raw.get("confusion")
    if not isinstance(conf, dict) or set(conf) != {"tp", "fp", "tn", "fn"}:
        reasons.append("calibration.confusion: object with exactly tp, fp, tn, fn counts required")
    else:
        for k in ("tp", "fp", "tn", "fn"):
            c = _int(conf[k], f"calibration.confusion.{k}", reasons, hi=10 ** 9)
            if c is not None:
                out["confusion"][k] = c
    if out["origin"] == "issuer_signed" and out["signature_envelope"] is None:
        reasons.append("calibration.origin: issuer_signed requires a signature_envelope")
    if reasons:
        return None, reasons
    out["record_id"] = record_identity(out)
    return out, []


def calibration_scope_matches(report: dict, cal: dict, language: str | None) -> tuple[bool, list[str]]:
    """A report inherits applicability from a calibration record only inside the record's own scope: same detector,
    same version when stated, same configuration and key scope, and the view's language among the calibrated ones."""
    why = []
    if report["detector"] != cal["detector"]:
        why.append(f"detector {report['detector']!r} vs calibrated {cal['detector']!r}")
    if cal.get("detector_version") and report.get("detector_version") != cal["detector_version"]:
        why.append(f"detector version {report.get('detector_version')!r} vs calibrated {cal['detector_version']!r}")
    if canonical_json(report.get("configuration") or {}) != canonical_json(cal.get("configuration") or {}):
        why.append("configuration differs from the calibrated configuration")
    if (report.get("key_scope") or None) != (cal.get("key_scope") or None):
        why.append(f"key scope {report.get('key_scope')!r} vs calibrated {cal.get('key_scope')!r}")
    if language is None or language not in cal["languages"]:
        why.append(f"language {language!r} is not among the calibrated languages {cal['languages']}")
    return (not why), why


# ------------------------------------------------------------------ TransformRecord/1
def check_transform(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["transform: object required"]
    if raw.get("schema") != TRANSFORM_RECORD:
        reasons.append(f"transform.schema: {TRANSFORM_RECORD!r} required")
    out = {"schema": TRANSFORM_RECORD, "kind": _enum(raw.get("kind"), "transform.kind", TRANSFORM_KINDS, reasons),
           "parent_view": _hex(raw.get("parent_view"), "transform.parent_view", reasons, required=False),
           "child_view": _hex(raw.get("child_view"), "transform.child_view", reasons),
           "implementation": _s(raw.get("implementation"), "transform.implementation", SHORT_MAX, reasons),
           "language_from": _enum(raw.get("language_from"), "transform.language_from", LANGUAGES, reasons, required=False),
           "language_to": _enum(raw.get("language_to"), "transform.language_to", LANGUAGES, reasons, required=False),
           "mapping_method": _enum(raw.get("mapping_method"), "transform.mapping_method", MAPPING_METHODS, reasons),
           "mapping": [], "review_findings": [], "actor": _s(raw.get("actor"), "transform.actor", SHORT_MAX, reasons),
           "provenance": _s(raw.get("provenance"), "transform.provenance", FIELD_MAX, reasons, required=False) or "",
           "review_status": _enum(raw.get("review_status", "unreviewed"), "transform.review_status", ("unreviewed", "operator_reviewed"), reasons)}
    for i, m in enumerate(_list(raw.get("mapping"), "transform.mapping", reasons, maxlen=MAX_SPANS)):
        if not isinstance(m, dict):
            reasons.append(f"transform.mapping[{i}]: object required"); continue
        out["mapping"].append({"parent_span": _hex(m.get("parent_span"), f"transform.mapping[{i}].parent_span", reasons),
                               "child_start": m.get("child_start"), "child_end": m.get("child_end"),
                               "status": _enum(m.get("status"), f"transform.mapping[{i}].status", ("MAPPED", "UNMAPPED", "CHANGED"), reasons)})
    for i, f in enumerate(_list(raw.get("review_findings"), "transform.review_findings", reasons, maxlen=MAX_SPANS)):
        if not isinstance(f, dict):
            reasons.append(f"transform.review_findings[{i}]: object required"); continue
        out["review_findings"].append({"reason": _enum(f.get("reason"), f"transform.review_findings[{i}].reason", REVIEW_REASONS, reasons),
                                       "detail": _s(f.get("detail"), f"transform.review_findings[{i}].detail", FIELD_MAX, reasons),
                                       "span": _hex(f.get("span"), f"transform.review_findings[{i}].span", reasons, required=False)})
    if out["kind"] == "translate" and (out["language_from"] is None or out["language_to"] is None or out["language_from"] == out["language_to"]):
        reasons.append("transform: a translation names two different languages")
    if out["kind"] in ("edit", "translate", "span_correction") and out["parent_view"] is None:
        reasons.append(f"transform.parent_view: required for {out['kind']}")
    if out["parent_view"] is not None and out["parent_view"] == out["child_view"]:
        reasons.append("transform: child view equals parent view (changing language or text creates new bytes; nothing changed)")
    if reasons:
        return None, reasons
    out["record_id"] = record_identity(out)
    return out, []


# ------------------------------------------------------------------ review items
def check_review_item(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["review_item: object required"]
    out = {"schema": REVIEW_ITEM, "reason": _enum(raw.get("reason"), "review_item.reason", REVIEW_REASONS, reasons),
           "detail": _s(raw.get("detail"), "review_item.detail", FIELD_MAX, reasons),
           "brief_id": _ident(raw.get("brief_id"), "review_item.brief_id", reasons),
           "version_id": _ident(raw.get("version_id"), "review_item.version_id", reasons, pat=_BRIEF_VERSION, required=False),
           "span": _hex(raw.get("span"), "review_item.span", reasons, required=False),
           "dependency": _s(raw.get("dependency"), "review_item.dependency", SHORT_MAX, reasons, required=False)}
    if reasons:
        return None, reasons
    out["record_id"] = record_identity(out)
    return out, []


def validate(check, raw, what: str):
    rec, reasons = check(raw)
    if reasons:
        raise ContractError(f"{what} cannot be recorded: " + "; ".join(reasons))
    return rec
