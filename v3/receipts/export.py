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

import os

import math
import re
import sys
from pathlib import Path

from v3.receipts.contracts import (ACTIVITY_TYPES, ARTIFACT_TYPES, ASSISTANCE, BINDING, ContractError, EXEC_CONTROL, OUTCOMES, RELATIONSHIPS,
                                   REVIEW_AUTHORITIES, REVIEW_STATES, SCHEMA_VERSION, parse_ts)

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
            raise ContractError(f"export {field}: value not registered")
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


def _obj(shape, required=(), nullable=False):
    """Closed nested object: keys ⊆ shape, `required` keys present; None only when `nullable`."""
    def f(v, field):
        if v is None:
            if nullable:
                return None
            raise ContractError(f"export {field}: object required (not null)")
        if not isinstance(v, dict):
            raise ContractError(f"export {field}: object required")
        extra = set(v) - set(shape)
        if extra:
            raise ContractError(f"export {field}: unexpected keys ({len(extra)})")
        missing = set(required) - set(v)
        if missing:
            raise ContractError(f"export {field}: missing required keys ({len(missing)})")
        return {k: fn(v.get(k), f"{field}.{k}") for k, fn in shape.items() if k in v}
    return f


def _nullable(fn):
    def f(v, field):
        return None if v is None else fn(v, field)
    return f


def _receipt_id(v, field):
    if not isinstance(v, str) or not re.match(r"^r-[0-9a-f]{32}$", v):
        raise ContractError(f"export {field}: public receipt id required")
    return v


PUBLIC_SHAPE = {
    "schema_version": _enum((SCHEMA_VERSION,)),
    "synthetic": _bool,
    "attempt_id": _s(128, re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")),
    "activity_id": _s(128),
    "activity_type": _enum(ACTIVITY_TYPES),
    "participant": _s(18, re.compile(r"^p-[0-9a-f]{16}$")),
    "group": _s(18, re.compile(r"^g-[0-9a-f]{16}$")),
    "relationship": _enum(RELATIONSHIPS),
    "execution_control": _enum(EXEC_CONTROL),
    "assistance": _enum(ASSISTANCE),
    "incentive_outcome_dependent": _bool,
    "protocol_id": _s(128),
    "observed_at": _ts,
    "first_observed_at": _ts,
    "artifact_binding": _obj({"artifact_type": _enum(ARTIFACT_TYPES), "sha256": _hex64, "size_bytes": _nonneg}, required=("artifact_type", "sha256", "size_bytes")),
    "release_identity": _obj({"tag": _s(64), "source_sha": _s(40, _SHA40)}, required=("tag", "source_sha"), nullable=True),
    "environment": _obj({"os": _s(64), "python": _s(32)}),
    "outcome": _enum(OUTCOMES),
    "review_state": _enum(REVIEW_STATES),
    "review_authority": _enum(REVIEW_AUTHORITIES),
    "binding_completeness": _enum(BINDING),
    "qualified": _bool,
    "successful": _bool,
    "version": _nonneg,
    "corrected": _bool,
    "superseded_at": _nullable(_ts),
    "receipt_id": _receipt_id,
    "public_note": _s(280),
}
# Fields every public row must carry (the renderer, CLI, REST and MCP consume them); the rest are conditional.
PUBLIC_REQUIRED = ("schema_version", "synthetic", "attempt_id", "activity_id", "activity_type", "participant", "relationship", "execution_control",
                   "assistance", "incentive_outcome_dependent", "protocol_id", "observed_at", "first_observed_at", "artifact_binding", "release_identity",
                   "environment", "outcome", "review_state", "review_authority", "binding_completeness", "qualified", "successful", "version",
                   "corrected", "superseded_at", "receipt_id")
NEVER_EXPORTED = ("participant_id", "group_id", "private", "limitations", "reasons", "diagnostics", "supersedes", "disclosure_permitted",
                  "reviewer_role", "reason", "arch", "observation", "receipt_digest", "digest", "chain")


def _denylist_terms() -> list[str] | None:
    """The PRIVATE publication denylist. None when unavailable — which is NOT an empty denylist: free text is
    then never published and the board records the policy as UNAVAILABLE."""
    override = os.environ.get("YUCLAW_PUBLICATION_DENYLIST")            # private path supplied by the operator (installed-package runs); never a default
    p = Path(override) if override else _REPO / "internal" / "witness_denylist.txt"
    if not p.is_file():
        return None
    try:
        return [(l.split("|")[-1].strip() if "|" in l else l.strip()) for l in p.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]
    except OSError:
        return None


def publication_policy() -> dict:
    terms = _denylist_terms()
    try:
        sys.path.insert(0, str(_REPO / "tools"))
        from check_language import lint_text  # noqa: F401
        rail = "AVAILABLE"
    except ImportError:
        rail = "UNAVAILABLE"
    return {"denylist": "AVAILABLE" if terms is not None else "UNAVAILABLE", "language_rail": rail,
            "free_text_publishable": terms is not None and rail == "AVAILABLE",
            "note": "free text is published only when both the private denylist and the language rail are available and pass; a missing denylist is not an empty denylist"}


def text_publishable(text: str) -> tuple[bool, str]:
    """Separate publication gates for free text: private denylist sweep (fail closed) + language rail."""
    terms = _denylist_terms()
    if terms is None:
        return False, "publication policy unavailable (denylist missing; fail closed)"
    low = text.lower()
    for t in terms:
        if t.lower() in low:
            return False, "denylisted term"
    try:
        sys.path.insert(0, str(_REPO / "tools"))
        from check_language import lint_text
        problems = lint_text(text, pages_mode=True)
        if problems:
            return False, "language rail"
    except ImportError:
        return False, "language rail unavailable (fail closed)"
    return True, "ok"


def sweep_strings(obj, path="root") -> None:
    """Denylist sweep over EVERY string leaf of an object destined for a public surface. Raises with the field
    path only. A missing denylist fails closed."""
    terms = _denylist_terms()
    if terms is None:
        raise ContractError("publication policy unavailable (denylist missing); nothing is published")
    low_terms = [t.lower() for t in terms if t]
    def walk(v, fp):
        if isinstance(v, str):
            lv = v.lower()
            if any(t in lv for t in low_terms):
                raise ContractError(f"publication sweep: denylisted term at {fp}")
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{fp}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{fp}[{i}]")
    walk(obj, path)


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
    lin = row.get("lineage") or {}
    candidate = {
        "schema_version": sub["schema_version"], "synthetic": prov_synthetic, "attempt_id": sub["attempt_id"], "activity_id": sub["activity_id"],
        "activity_type": row.get("activity_type", sub.get("activity_type", "REPLICATION")),
        "participant": store.pseudonym(sub["participant_id"]),
        "relationship": sub["relationship"], "execution_control": sub["execution_control"], "assistance": sub["assistance"],
        "incentive_outcome_dependent": sub["incentive_outcome_dependent"], "protocol_id": sub["protocol_id"], "observed_at": sub["observed_at"],
        "first_observed_at": lin.get("first_observed_at", sub["observed_at"]),
        "artifact_binding": {"artifact_type": sub["artifact_binding"]["artifact_type"], "sha256": sub["artifact_binding"]["sha256"], "size_bytes": sub["artifact_binding"]["size_bytes"]},
        "release_identity": None if sub["release_identity"] is None else {"tag": sub["release_identity"]["tag"], "source_sha": sub["release_identity"]["source_sha"]},
        "environment": {k: sub["environment"][k] for k in ("os", "python") if k in sub["environment"]},
        "outcome": sub["outcome"], "review_state": rev.get("state", "RECEIVED"), "review_authority": rev.get("authority", "NONE"),
        "binding_completeness": row["binding_completeness"], "qualified": row["qualified"], "successful": row["successful"],
        "version": row["version"], "corrected": bool(row.get("corrected", row["version"] > 1)), "superseded_at": lin.get("superseded_at"),
        "receipt_id": store.public_id(row["digest"]),
    }
    if sub["group_id"]:
        candidate["group"] = "g-" + store.pseudonym("group:" + sub["group_id"])[2:]
    if sub.get("public_note") and sub.get("disclosure_permitted") and candidate["activity_type"] != "REFUSAL":
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


def revalidate(row: dict) -> dict:
    """Re-apply PUBLIC_SHAPE to a public row read back from disk (scoreboard loader): unknown keys and
    unregistered values are errors, never passed through to a surface."""
    if not isinstance(row, dict):
        raise ContractError("public row: object required")
    extra = set(row) - set(PUBLIC_SHAPE)
    if extra:
        raise ContractError(f"public row: unexpected keys ({len(extra)})")
    missing = [k for k in PUBLIC_REQUIRED if k not in row]
    if missing:
        raise ContractError(f"public row: missing required fields ({len(missing)})")
    return {k: fn(row[k], k) for k, fn in PUBLIC_SHAPE.items() if k in row}
