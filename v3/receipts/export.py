"""Public export — a TYPED boundary (v7 receipts).

`project(derived_row, store, mode)` builds a FRESH object from PUBLIC_SHAPE. Every field is validated
against its registered vocabulary/type; nested objects have a complete allowed shape; anything else is
an error, never passed through. Free text reaches the public object only as `public_note` and only
when the participant permitted disclosure AND the text passes the language rail AND the private
denylist sweep — type correctness alone is not publication safety.

`synthetic` is carried from IMPORT PROVENANCE (never from the record body). A synthetic record cannot
enter a non-synthetic export; a real record cannot be labeled synthetic. Deleting or flipping a
participant-supplied marker changes nothing because the marker is never read.
Pseudonyms are store-keyed HMACs (opaque, unguessable from identity data); identity maps stay private.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from v3.receipts.contracts import (ARTIFACT_TYPES, ASSISTANCE, BINDING, ContractError, EXEC_CONTROL, OUTCOMES, RELATIONSHIPS,
                                   REVIEW_STATES, SCHEMA_VERSION, parse_ts)

_REPO = Path(__file__).resolve().parents[2]
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PRINTABLE = re.compile(r"^[\x20-\x7e]*$")


def _s(maxlen, pat=None):
    def f(v, field):
        if not isinstance(v, str) or not v or len(v) > maxlen or not _PRINTABLE.match(v) or (pat and not pat.match(v)):
            raise ContractError(f"export {field}: bounded printable string required")
        return v
    return f


def _enum(allowed):
    def f(v, field):
        if v not in allowed:
            raise ContractError(f"export {field}: {v!r} not registered")
        return v
    return f


def _bool(v, field):
    if not isinstance(v, bool):
        raise ContractError(f"export {field}: bool required")
    return v


def _nonneg(v, field):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0 or (isinstance(v, float) and not math.isfinite(v)):
        raise ContractError(f"export {field}: nonnegative integer required")
    return v


def _ts(v, field):
    parse_ts(v, field); return v


def _hex64(v, field):
    if not isinstance(v, str) or not _HEX64.match(v):
        raise ContractError(f"export {field}: sha256 hex required")
    return v


def _obj(shape):
    def f(v, field):
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ContractError(f"export {field}: object required")
        extra = set(v) - set(shape)
        if extra:
            raise ContractError(f"export {field}: unexpected keys {sorted(extra)}")
        return {k: fn(v.get(k), f"{field}.{k}") for k, fn in shape.items() if k in v}
    return f


PUBLIC_SHAPE = {
    "schema_version": _enum((SCHEMA_VERSION,)),
    "synthetic": _bool,
    "attempt_id": _s(128, re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")),
    "activity_id": _s(128),
    "participant": _s(18, re.compile(r"^p-[0-9a-f]{16}$")),
    "group": _s(18, re.compile(r"^g-[0-9a-f]{16}$")),
    "relationship": _enum(RELATIONSHIPS),
    "execution_control": _enum(EXEC_CONTROL),
    "assistance": _enum(ASSISTANCE),
    "incentive_outcome_dependent": _bool,
    "protocol_id": _s(128),
    "observed_at": _ts,
    "artifact_binding": _obj({"artifact_type": _enum(ARTIFACT_TYPES), "sha256": _hex64, "size_bytes": _nonneg}),
    "release_identity": _obj({"tag": _s(64), "source_sha": _s(40, _SHA40)}),
    "environment": _obj({"os": _s(64), "python": _s(32)}),
    "outcome": _enum(OUTCOMES),
    "review_state": _enum(REVIEW_STATES),
    "review_authority": _enum(("DESIGNATED", "SYNTHETIC", "NONE")),
    "binding_completeness": _enum(BINDING),
    "qualified": _bool,
    "successful": _bool,
    "version": _nonneg,
    "receipt_digest": _hex64,
    "public_note": _s(280),
}
NEVER_EXPORTED = ("participant_id", "group_id", "private", "limitations", "reasons", "diagnostics", "supersedes", "disclosure_permitted",
                  "reviewer_role", "reason", "arch", "observation")


def _denylist_terms() -> list[str]:
    p = _REPO / "internal" / "witness_denylist.txt"
    if not p.exists():
        return []
    return [(l.split("|")[-1].strip() if "|" in l else l.strip()) for l in p.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]


def text_publishable(text: str) -> tuple[bool, str]:
    """Separate publication gates for free text: language rail + private denylist sweep."""
    low = text.lower()
    for t in _denylist_terms():
        if t.lower() in low:
            return False, "denylisted term"
    try:
        sys.path.insert(0, str(_REPO / "tools"))
        from check_language import lint_text
        problems = lint_text(text, pages_mode=True)
        if problems:
            return False, f"language rail: {problems[0]}"
    except ImportError:
        return False, "language rail unavailable (fail closed)"
    return True, "ok"


def project(row: dict, store, *, mode: str) -> dict:
    """Build the public object for one DERIVED row. mode ∈ {'synthetic','public'}."""
    if mode not in ("synthetic", "public"):
        raise ContractError("export mode must be 'synthetic' or 'public'")
    prov_synthetic = bool(row["synthetic"])                # from import provenance (derive), never the body
    if mode == "public" and prov_synthetic:
        raise ContractError("refusing to export a synthetic record in a non-synthetic (public) export")
    if mode == "synthetic" and not prov_synthetic:
        raise ContractError("refusing to label a real record as synthetic")
    sub = row["submission"]
    rev = row.get("review") or {}
    candidate = {
        "schema_version": sub["schema_version"], "synthetic": prov_synthetic, "attempt_id": sub["attempt_id"], "activity_id": sub["activity_id"],
        "participant": store.pseudonym(sub["participant_id"]),
        "relationship": sub["relationship"], "execution_control": sub["execution_control"], "assistance": sub["assistance"],
        "incentive_outcome_dependent": sub["incentive_outcome_dependent"], "protocol_id": sub["protocol_id"], "observed_at": sub["observed_at"],
        "artifact_binding": {"artifact_type": sub["artifact_binding"]["artifact_type"], "sha256": sub["artifact_binding"]["sha256"], "size_bytes": sub["artifact_binding"]["size_bytes"]},
        "release_identity": None if sub["release_identity"] is None else {"tag": sub["release_identity"]["tag"], "source_sha": sub["release_identity"]["source_sha"]},
        "environment": {k: sub["environment"][k] for k in ("os", "python") if k in sub["environment"]},
        "outcome": sub["outcome"], "review_state": rev.get("state", "RECEIVED"), "review_authority": rev.get("authority", "NONE"),
        "binding_completeness": row["binding_completeness"], "qualified": row["qualified"], "successful": row["successful"],
        "version": row["version"], "receipt_digest": row["digest"],
    }
    if sub["group_id"]:
        candidate["group"] = "g-" + store.pseudonym("group:" + sub["group_id"])[2:]
    if sub.get("public_note") and sub.get("disclosure_permitted"):
        ok, why = text_publishable(sub["public_note"])
        if ok:
            candidate["public_note"] = sub["public_note"]
    out = {}
    for k, fn in PUBLIC_SHAPE.items():
        if k in candidate:
            out[k] = fn(candidate[k], k)
    for k in NEVER_EXPORTED:
        assert k not in out
    return out


def project_many(rows: list[dict], store, *, mode: str) -> list[dict]:
    return [project(r, store, mode=mode) for r in rows]
