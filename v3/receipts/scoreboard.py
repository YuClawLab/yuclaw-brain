"""Derived evidence scoreboard and history (v7).

Built ONLY from records: the receipt store (real provenance), the legacy public log (via the adapter),
challenges and decisions. Columns are shown only when applicable; every column carries its counting
definition and the source timestamp; zero and pending states are displayed as such. Failures,
inconclusive and unresolved findings have equal visibility. No composite trust score, no financial
statistic. Program evidence (any release) is separate from exact-release evidence (bound bytes).
`history(a, b)` answers "what evidence or disposition changed between two snapshots" from the
snapshots themselves."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts import counting, export, legacy, target as _target
from v3.receipts.challenge import ChallengeStore, DISPOSITIONS
from v3.receipts.contracts import ContractError, parse_ts, validate_binding_claim
from v3.receipts.decision import DecisionStore, MEANING as DECISION_MEANING, PUBLIC_FIELDS as DECISION_FIELDS
from v3.receipts.store import Store

_REPO = Path(__file__).resolve().parents[2]
DEFINITIONS = {
    "witnesses": "WITNESS_REVIEW receipts: people who examined the methodology and left a reviewable, reviewed receipt; unreceipted relationships are never counted",
    "pilots": "BYOS pilot engagements with a signed scope (none: counsel review is the blocker)",
    "replications": "REPLICATION receipts: attempts to reproduce published artifacts; primary population = qualified attempts (failed/inconclusive retained); successful reported separately",
    "audits": "AUDIT_BREAK_ATTEMPT receipts: outsider attempts to break a published check (a found break stays visible); internal test runs are not audits",
    "refusals": "REFUSAL receipts: a real user asked for an unsupported conclusion and the product refused, reviewed separately; automated check-claim telemetry and receipt qualification failures are not counted here",
    "packet_uses": "document-use receipts bound to an exact packet digest and exported with permission",
    "challenges": "structured challenges by disposition; adverse = OPEN or CONFIRMED; RESOLVED keeps the original finding",
}
DERIVATION_VERSION = "board-derivation/2"
CANONICAL = {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": True}


def canonical_bytes(obj) -> bytes:
    """ONE declared canonical serialization for cross-surface comparison (CLI, static file, REST body minus its
    documented envelope, MCP): sorted keys, no whitespace, ASCII."""
    return json.dumps(obj, **CANONICAL).encode("ascii")


REST_ENVELOPE = ("compliance", "compliance_notice")     # documented transport envelope added by the REST stamp


def build(store_dir, *, synthetic: bool = False, registration: dict | None = None, target: dict | None = None, now: datetime | None = None, legacy_log: Path | None = None) -> dict:
    """Derive the board from RECORDS only. `target` = a validated release target manifest (exact-target coverage
    is UNBOUND without it). Raises StorageError when the store is unavailable (a surface then shows UNAVAILABLE)."""
    st = Store(store_dir); cs = ChallengeStore(store_dir); ds = DecisionStore(store_dir)
    derived = counting.derive(st, synthetic=synthetic)
    c = counting.counts(derived, registration=registration)
    cat = c["categories"]
    tgt = _target.validate_target(target) if target is not None else None
    cov = _target.coverage(derived, tgt)
    log_path = Path(legacy_log) if legacy_log else (_REPO / "docs/replication/replication_log.json")
    leg = legacy.adapt_log(json.loads(log_path.read_text())) if (log_path.exists() and not synthetic) else []
    legacy_source = "SYNTHETIC_EXCLUDED" if synthetic else ("PRESENT" if log_path.exists() else "ABSENT")   # an absent log is reported, never counted as zero silently
    chal = cs.public_view(synthetic=synthetic)
    by_disp = {}
    for r in chal: by_disp[r["disposition"]] = by_disp.get(r["disposition"], 0) + 1
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rows = export.project_many(derived, st, mode=("synthetic" if synthetic else "public"))
    policy = export.publication_policy()
    def cat_col(t, extra=None):
        k = cat[t]; col = {"receipted": k["receipted"], "qualified": k["qualified"], "distinct_persons_qualified": k["distinct_persons_qualified"],
                           "state": "ZERO" if k["receipted"] == 0 else "OBSERVED", "by_outcome": k["qualified_by_outcome"]}
        col.update(extra or {}); return col
    board = {
        "scoreboard_version": "v7-candidate-2", "public_schema_version": BOARD_SCHEMA_VERSION, "derivation_version": DERIVATION_VERSION,
        "synthetic": synthetic, "source_timestamp": ts, "definitions": DEFINITIONS,
        "publication_policy": {"denylist": policy["denylist"], "language_rail": policy["language_rail"], "free_text_publishable": policy["free_text_publishable"]},
        "target": ({"state": "BOUND", "label": tgt["label"], "tag": tgt["release"]["tag"], "version": tgt["release"]["version"], "source_sha": tgt["release"]["source_sha"], "source_tree": tgt["release"]["source_tree"],
                    "artifacts": [{"artifact_type": a["artifact_type"], "filename": a["filename"], "sha256": a["sha256"], "size_bytes": a["size_bytes"]} for a in tgt["artifacts"]], "generated_from": tgt["generated_from"]}
                   if tgt else {"state": "UNBOUND", "note": "no release target manifest supplied; exact-target coverage is UNBOUND (not zero)"}),
        "columns": {
            "witnesses": cat_col("WITNESS_REVIEW", {"note": "receipted: %d · unreceipted relationships not counted" % cat["WITNESS_REVIEW"]["receipted"]}),
            "pilots": {"count": 0, "state": "PENDING_COUNSEL_REVIEW"},
            "replications": {"attempts": c["attempts"], "qualified": c["qualified"], "successful": c["successful"], "visible": c["visible"],
                              "windows": c["windows"], "registration": c["registration"], "artifacts": c["artifacts"], "corrected_attempts": c["corrected_attempts"],
                              "program_evidence_legacy": {"source": legacy_source, "entries": len(leg), "reproduced": sum(1 for l in leg if l["outcome"] == "REPRODUCED"),
                                                          "binding": "PREFIX_ONLY (historical; not exact-release evidence)", "affiliated": sum(1 for l in leg if l["relationship"] == "OWNER-AFFILIATED")},
                              "exact_release_evidence": {"program_exact_artifact_evidence": {"successful_package_reproductions": c["artifacts"]["package_reproductions_successful"],
                                                                                            "note": "qualified successful attempts whose exact wheel/sdist bytes were verified — any release (program-wide)"},
                                                         "exact_target_evidence": cov},
                              "state": "PENDING_REGISTRATION" if c["registration"]["status"] == "PENDING" else "REGISTERED"},
            "audits": cat_col("AUDIT_BREAK_ATTEMPT", {"note": "a found break stays visible; internal test runs are not audits"}),
            "refusals": cat_col("REFUSAL", {"note": "receipted refusals of unsupported conclusions only; automated check-claim telemetry and receipt qualification failures are not refusal receipts",
                                            "unqualified_submissions_all_types": sum(k["unqualified"] for k in cat.values()),
                                            "held": sum(1 for r in derived if (r.get("review") or {}).get("state") == "HELD")}),
            "packet_uses": {"count": len(ds.export(synthetic=synthetic)), "state": "OBSERVED", "note": DECISION_MEANING},
            "challenges": {"by_disposition": by_disp, "adverse_open": sum(1 for r in chal if r["adverse"]), "total": len(chal), "state": "OBSERVED"},
        },
        "receipts_public": rows, "challenges_public": chal, "decisions_public": ds.export(synthetic=synthetic),
        "policy_version": c["policy_version"], "not_advice": "Research and education only. Not investment advice. No composite trust score is computed.",
    }
    if not synthetic:
        export.sweep_strings(board)                     # publication policy over EVERY string leaf of the public object (fail closed)
    return board


def history(a: dict, b: dict) -> dict:
    """What changed between two VALIDATED board snapshots. Keyed by attempt_id: a reviewed supersession of the
    same attempt is ONE disposition change (kind receipt_superseded), never an addition/removal. Window movement
    is the per-window delta of primary counts. Movement multipliers stay undefined on a zero baseline."""
    ra = {r["attempt_id"]: r for r in a.get("receipts_public", [])}; rb = {r["attempt_id"]: r for r in b.get("receipts_public", [])}
    ca = {c["challenge_id"]: c for c in a.get("challenges_public", [])}; cb = {c["challenge_id"]: c for c in b.get("challenges_public", [])}
    changes = []
    for k in sorted(set(ra) & set(rb)):
        x, y = ra[k], rb[k]
        if y["version"] > x["version"]:
            changes.append({"kind": "receipt_superseded", "attempt_id": k, "from_version": x["version"], "to_version": y["version"], "superseded_at": y.get("superseded_at"),
                            "from_receipt_id": x["receipt_id"], "to_receipt_id": y["receipt_id"], "eligibility_preserved": (x["qualified"], x["successful"]) == (y["qualified"], y["successful"])})
        elif any(x.get(f) != y.get(f) for f in ("outcome", "review_state", "review_authority", "qualified", "successful", "binding_completeness")):
            changes.append({"kind": "receipt_state_changed", "attempt_id": k, "from": {f: x.get(f) for f in ("outcome", "review_state", "qualified", "successful")}, "to": {f: y.get(f) for f in ("outcome", "review_state", "qualified", "successful")}})
    for k in sorted(set(ca) & set(cb)):
        if ca[k]["disposition"] != cb[k]["disposition"]:
            changes.append({"kind": "challenge_disposition_changed", "challenge_id": k, "from": ca[k]["disposition"], "to": cb[k]["disposition"]})
    wa = a["columns"]["replications"]["windows"]; wb = b["columns"]["replications"]["windows"]
    window_movement = {}
    for w in sorted(set(wa) | set(wb)):
        pa = wa.get(w, {}); pb = wb.get(w, {})
        d = {f: pb.get(f, 0) - pa.get(f, 0) for f in ("primary_attempts", "primary_distinct_persons", "primary_distinct_groups", "successful_attempts", "successful_distinct_persons", "successful_distinct_groups")}
        window_movement[w] = d
    ma = a["columns"]["replications"]; mb = b["columns"]["replications"]
    return {"from": a["source_timestamp"], "to": b["source_timestamp"], "schema": {"from": a.get("public_schema_version"), "to": b.get("public_schema_version")},
            "receipts_added": sorted(set(rb) - set(ra)), "receipts_removed": sorted(set(ra) - set(rb)),
            "challenges_added": sorted(set(cb) - set(ca)), "disposition_changes": changes,
            "window_movement": window_movement, "window_movement_nonzero": any(any(v != 0 for v in d.values()) for d in window_movement.values()),
            "target": {"from": a.get("target", {}).get("state"), "to": b.get("target", {}).get("state")},
            "movement": counting.movement({"attempts": ma["attempts"], "qualified": ma["qualified"], "successful": ma["successful"]},
                                          {"attempts": mb["attempts"], "qualified": mb["qualified"], "successful": mb["successful"]})}


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TEXT = re.compile(r"^[^\x00-\x1f\x7f]*$")      # no control characters; Unicode punctuation allowed
BOARD_SCHEMA_VERSION = "public-board-schema/2"        # /2: program_evidence_legacy.source (PRESENT/ABSENT/SYNTHETIC_EXCLUDED) required
from v3.receipts.contracts import ARTIFACT_TYPES, OUTCOMES, PACKAGE_ARTIFACTS, REVIEW_AUTHORITIES
from v3.receipts.counting import ELIGIBILITY
from v3.receipts.decision import DECISIONS

# ---- schema combinators: every validator returns a FRESH value built only from validated fields; unknown keys
# ---- at any depth are errors; error text names the field path only, never the offending value or key name.


class BoardError(ContractError):
    """Public-boundary validation failure: stable code + field path only (never a supplied value or key name)."""
    def __init__(self, code: str, field: str):
        self.code = code; self.field = field
        super().__init__(f"{code} at {field}")


def _err(field, what):
    code = what if what.startswith("E_") else {"nonnegative integer required": "E_INT", "bool required": "E_BOOL", "fixed value required": "E_CONST",
                                               "value not registered": "E_ENUM", "timestamp required": "E_TIMESTAMP", "sha256 hex required": "E_HEX",
                                               "registered id shape required": "E_ID", "object required": "E_OBJECT", "bounded object required": "E_OBJECT",
                                               "bounded list required": "E_LIST"}.get(what, "E_SHAPE")
    if what.startswith("unexpected keys"): code = "E_UNKNOWN_KEYS"
    if what.startswith("missing required keys"): code = "E_MISSING"
    if "count relationship" in what or "relationship violated" in what or "must equal" in what or "must agree" in what: code = "E_RELATION"
    if "bounded string" in what: code = "E_STRING"
    raise BoardError(code, field)


def _s(maxlen=2000):
    def f(v, field):
        if not isinstance(v, str) or len(v) > maxlen or not _TEXT.match(v):
            _err(field, "bounded string without control characters required")
        return v
    return f


def _idv(v, field):
    if not isinstance(v, str) or not _ID.match(v):
        _err(field, "registered id shape required")
    return v


def _int(v, field):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        _err(field, "nonnegative integer required")
    return v


def _bool(v, field):
    if not isinstance(v, bool):
        _err(field, "bool required")
    return v


def _const(c):
    def f(v, field):
        if v is not c and v != c:
            _err(field, "fixed value required")
        return c
    return f


def _enum(allowed):
    def f(v, field):
        if not isinstance(v, str) or v not in allowed:
            _err(field, "value not registered")
        return v
    return f


def _ts(v, field):
    if not isinstance(v, str):
        _err(field, "E_TIMESTAMP")
    try:
        parse_ts(v, field)
    except ContractError:
        _err(field, "E_TIMESTAMP")          # never echo the supplied value
    return v


def _hex(v, field):
    if not isinstance(v, str) or not _HEX64.match(v):
        _err(field, "sha256 hex required")
    return v


def _binding(v, field):
    try:
        return validate_binding_claim(v, field)
    except ContractError:
        _err(field, "artifact binding {artifact_type, sha256, size_bytes} required")


def _obj(shape, required=None, optional=()):
    """Closed object: keys ⊆ shape; `required` (default: all keys not in `optional`) must be present."""
    req = set(shape) - set(optional) if required is None else set(required)
    def f(v, field):
        if not isinstance(v, dict):
            _err(field, "object required")
        if set(v) - set(shape):
            _err(field, f"unexpected keys ({len(set(v) - set(shape))})")
        missing = req - set(v)
        if missing:
            _err(field, f"missing required keys ({len(missing)})")
        return {k: shape[k](v[k], f"{field}.{k}") for k in shape if k in v}
    return f


def _nullable(fn):
    def f(v, field):
        return None if v is None else fn(v, field)
    return f


def _map(key_fn, val_fn, maxlen=10000):
    def f(v, field):
        if not isinstance(v, dict) or len(v) > maxlen:
            _err(field, "bounded object required")
        return {key_fn(k, f"{field}.key"): val_fn(x, f"{field}[]") for k, x in v.items()}
    return f


def _list(fn, maxlen=100000):
    def f(v, field):
        if not isinstance(v, list) or len(v) > maxlen:
            _err(field, "bounded list required")
        return [fn(x, f"{field}[{i}]") for i, x in enumerate(v)]
    return f


def _receipt_row(v, field):
    try:
        row = export.revalidate(v)
    except ContractError:
        _err(field, "E_ROW")
    if row["synthetic"] is not False:
        _err(field, "E_SYNTHETIC")
    return row


WINDOW = _obj({"primary_distinct_persons": _int, "primary_distinct_groups": _int, "primary_attempts": _int, "successful_distinct_persons": _int,
               "successful_distinct_groups": _int, "successful_attempts": _int, "eligibility": _enum(ELIGIBILITY), "prospective": _bool})
TARGET_ART = _obj({"artifact_type": _enum(PACKAGE_ARTIFACTS), "filename": _s(128), "sha256": _hex, "size_bytes": _int})
COVERAGE_ART = _obj({"artifact_type": _enum(PACKAGE_ARTIFACTS), "filename": _s(128), "sha256": _hex, "size_bytes": _int, "qualified_successful_attempts": _int, "distinct_persons": _int, "distinct_groups": _int, "covered": _bool})
COVERAGE = _obj({"state": _enum(("UNBOUND", "BOUND")), "note": _s(500), "per_artifact": _list(COVERAGE_ART), "artifacts_covered": _nullable(_int), "artifacts_total": _nullable(_int),
                 "successful_package_reproductions": _nullable(_int), "label": _enum(_target.LABELS), "release": _obj({"tag": _s(32), "version": _s(32), "source_sha": _s(40), "source_tree": _s(40)})},
                required=("state", "note", "per_artifact", "artifacts_covered", "artifacts_total", "successful_package_reproductions"))
TARGET = _obj({"state": _enum(("UNBOUND", "BOUND")), "note": _s(500), "label": _enum(_target.LABELS), "tag": _s(32), "version": _s(32), "source_sha": _s(40), "source_tree": _s(40),
               "artifacts": _list(TARGET_ART), "generated_from": _enum(_target.SOURCES)}, required=("state",))
CATEGORY = _obj({"receipted": _int, "qualified": _int, "distinct_persons_qualified": _int, "state": _enum(("ZERO", "OBSERVED")), "by_outcome": _map(_enum(OUTCOMES), _int), "note": _s(500),
                 "unqualified_submissions_all_types": _int, "held": _int}, required=("receipted", "qualified", "distinct_persons_qualified", "state", "by_outcome"))
REGISTRATION = _obj({"status": _enum(("PENDING", "REGISTERED")), "note": _s(500), "protocol_id": _idv, "anchor": _s(10), "registered_at": _ts,
                     "policy_version": _s(64), "window_days": _int, "prospective_rule": _s(500)}, required=("status",))
ARTIFACTS = _obj({"successful_cohort_artifacts": _int, "attempted_artifacts": _int, "verified_artifacts": _int, "package_reproductions_successful": _int,
                  "attempted_by_type": _map(_enum(ARTIFACT_TYPES), _int), "successful_by_type": _map(_enum(ARTIFACT_TYPES), _int), "note": _s(500)})
REPLICATIONS = _obj({"attempts": _int, "qualified": _int, "successful": _int,
                     "visible": _obj({"failed": _int, "inconclusive": _int, "qualified_failed": _int, "qualified_inconclusive": _int, "unqualified": _int}),
                     "windows": _map(_s(256), WINDOW), "registration": REGISTRATION, "artifacts": ARTIFACTS,
                     "program_evidence_legacy": _obj({"source": _enum(("PRESENT", "ABSENT", "SYNTHETIC_EXCLUDED")), "entries": _int, "reproduced": _int, "affiliated": _int, "binding": _s(200)}),
                     "exact_release_evidence": _obj({"program_exact_artifact_evidence": _obj({"successful_package_reproductions": _int, "note": _s(500)}), "exact_target_evidence": COVERAGE}),
                     "corrected_attempts": _int,
                     "state": _enum(("PENDING_REGISTRATION", "REGISTERED"))})
COLUMNS = _obj({"witnesses": CATEGORY,
                "pilots": _obj({"count": _int, "state": _enum(("PENDING_COUNSEL_REVIEW", "ZERO", "OBSERVED"))}),
                "replications": REPLICATIONS,
                "audits": CATEGORY,
                "refusals": CATEGORY,
                "packet_uses": _obj({"count": _int, "state": _enum(("OBSERVED",)), "note": _s(500)}),
                "challenges": _obj({"by_disposition": _map(_enum(DISPOSITIONS), _int), "adverse_open": _int, "total": _int, "state": _enum(("OBSERVED",))})})
CHALLENGE_ROW = _obj({"challenge_id": _idv, "artifact": _binding, "claim_id": _idv, "criterion": _s(64), "disposition": _enum(DISPOSITIONS), "version": _int, "created_at": _ts,
                      "synthetic": _const(False), "disposed_by_authority": _nullable(_enum(("DESIGNATED", "SYNTHETIC", "HELD", "challenger"))),
                      "resolution": _nullable(_obj({"revised_artifact": _binding, "verification_method": _enum(("packet-verify", "receipt", "reviewer-evaluation")), "original_finding_retained": _const(True)})),
                      "adverse": _bool}, optional=("criterion",))
DECISION_ROW = _obj({"decision_id": _idv, "decision": _enum(DECISIONS), "packet_manifest_digest": _hex, "claim_id": _idv, "decided_at": _ts, "synthetic": _const(False)})
BOARD = _obj({"scoreboard_version": _s(64), "public_schema_version": _const(BOARD_SCHEMA_VERSION), "derivation_version": _s(64), "synthetic": _const(False), "source_timestamp": _ts,
              "definitions": _obj({k: _s(500) for k in DEFINITIONS}),
              "publication_policy": _obj({"denylist": _enum(("AVAILABLE", "UNAVAILABLE")), "language_rail": _enum(("AVAILABLE", "UNAVAILABLE")), "free_text_publishable": _bool}),
              "target": TARGET, "columns": COLUMNS,
              "receipts_public": _list(_receipt_row), "challenges_public": _list(CHALLENGE_ROW), "decisions_public": _list(DECISION_ROW),
              "policy_version": _s(64), "not_advice": _s(500)}, optional=("public_schema_version",))


def validate_board(board) -> dict:
    """Complete, versioned public schema (BOARD_SCHEMA_VERSION) applied to the WHOLE board. Returns a FRESH object
    constructed only from validated fields: unknown or private data at any depth is an error, never passed
    through; count relationships are checked; synthetic boards are refused. Error text carries field paths only."""
    if not isinstance(board, dict):
        _err("root", "object required")
    if board.get("synthetic") is not False:
        _err("synthetic", "board is synthetic or unlabeled; a public surface never serves it")
    out = BOARD(board, "root")
    rep = out["columns"]["replications"]; vis = rep["visible"]; ch = out["columns"]["challenges"]
    if not (rep["successful"] <= rep["qualified"] <= rep["attempts"]):
        _err("columns.replications", "count relationship violated (successful ≤ qualified ≤ attempts)")
    if vis["unqualified"] != rep["attempts"] - rep["qualified"] or vis["qualified_failed"] > vis["failed"] or vis["qualified_inconclusive"] > vis["inconclusive"]:
        _err("columns.replications.visible", "count relationship violated")
    if sum(1 for r in out["receipts_public"] if r["activity_type"] == "REPLICATION") != rep["attempts"]:
        _err("receipts_public", "count relationship violated (replication rows must equal replications.attempts)")
    for name, t in (("witnesses", "WITNESS_REVIEW"), ("audits", "AUDIT_BREAK_ATTEMPT"), ("refusals", "REFUSAL")):
        col = out["columns"][name]
        if sum(1 for r in out["receipts_public"] if r["activity_type"] == t) != col["receipted"] or col["qualified"] > col["receipted"] or (col["state"] == "ZERO") != (col["receipted"] == 0):
            _err(f"columns.{name}", "count relationship violated")
    cov = rep["exact_release_evidence"]["exact_target_evidence"]
    if (cov["state"] == "BOUND") != (out["target"]["state"] == "BOUND"):
        _err("target", "count relationship violated (target and coverage state must agree)")
    if cov["state"] == "BOUND" and (cov["artifacts_total"] != len(cov["per_artifact"]) or cov["artifacts_covered"] != sum(1 for p in cov["per_artifact"] if p["covered"])):
        _err("columns.replications.exact_release_evidence", "count relationship violated")
    if ch["adverse_open"] > ch["total"] or sum(ch["by_disposition"].values()) != ch["total"] or len(out["challenges_public"]) != ch["total"]:
        _err("columns.challenges", "count relationship violated")
    if sum(1 for c in out["challenges_public"] if c["adverse"]) != ch["adverse_open"]:
        _err("columns.challenges", "adverse_open must equal the adverse rows")
    if (rep["registration"]["status"] == "REGISTERED") != (rep["state"] == "REGISTERED"):
        _err("columns.replications.state", "state must agree with registration.status")
    for k, w in rep["windows"].items():
        if w["prospective"] != (w["eligibility"] == "prospective") or w["successful_attempts"] > w["primary_attempts"]:
            _err("columns.replications.windows", "window relationship violated")
    # state-specific required keys (every nested object the CLI/HTML/REST/MCP consume)
    tgt = out["target"]
    if tgt["state"] == "BOUND":
        for k in ("label", "tag", "version", "source_sha", "source_tree", "artifacts", "generated_from"):
            if k not in tgt: _err("target", "E_MISSING")
        if not tgt["artifacts"]: _err("target.artifacts", "E_MISSING")
    else:
        if "note" not in tgt: _err("target", "E_MISSING")
        if any(k in tgt for k in ("label", "artifacts")): _err("target", "E_UNKNOWN_KEYS")
    if cov["state"] == "BOUND":
        for k in ("label", "release"):
            if k not in cov: _err("columns.replications.exact_release_evidence.exact_target_evidence", "E_MISSING")
        if any(cov[k] is None for k in ("artifacts_covered", "artifacts_total", "successful_package_reproductions")): _err("columns.replications.exact_release_evidence.exact_target_evidence", "E_MISSING")
        if cov["label"] != tgt.get("label"): _err("columns.replications.exact_release_evidence.exact_target_evidence", "E_RELATION")
    else:
        if cov["per_artifact"] or any(cov[k] is not None for k in ("artifacts_covered", "artifacts_total", "successful_package_reproductions")): _err("columns.replications.exact_release_evidence.exact_target_evidence", "E_RELATION")
        if any(k in cov for k in ("label", "release")): _err("columns.replications.exact_release_evidence.exact_target_evidence", "E_UNKNOWN_KEYS")
    regn = rep["registration"]
    if regn["status"] == "REGISTERED":
        for k in ("protocol_id", "anchor", "registered_at", "policy_version", "window_days", "prospective_rule"):
            if k not in regn: _err("columns.replications.registration", "E_MISSING")
    elif "note" not in regn:
        _err("columns.replications.registration", "E_MISSING")
    out["public_schema_version"] = BOARD_SCHEMA_VERSION
    return out


def inspect_public(path: Path) -> dict:
    """{'status': 'OK'|'ABSENT'|'INVALID'|'SYNTHETIC_REFUSED', 'code': str, 'field': str|None, 'reason': str, 'board': dict|None}.
    ABSENT/INVALID are UNAVAILABLE states for surfaces — never a measured zero. `reason` carries a stable code
    and a field path only; supplied values, key names and exception text never reach a public consumer."""
    path = Path(path)
    if not path.exists():
        return {"status": "ABSENT", "code": "E_ABSENT", "field": None, "reason": "E_ABSENT: no public scoreboard file", "board": None}
    try:
        raw = path.read_bytes()
        board = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {"status": "INVALID", "code": "E_UNREADABLE", "field": "root", "reason": "E_UNREADABLE at root", "board": None}
    if isinstance(board, dict) and board.get("synthetic") is not False:
        return {"status": "SYNTHETIC_REFUSED", "code": "E_SYNTHETIC", "field": "synthetic", "reason": "E_SYNTHETIC at synthetic", "board": None}
    try:
        return {"status": "OK", "code": "OK", "field": None, "reason": "validated against " + BOARD_SCHEMA_VERSION, "board": validate_board(board)}
    except BoardError as exc:
        return {"status": "INVALID", "code": exc.code, "field": exc.field, "reason": f"{exc.code} at {exc.field}", "board": None}
    except ContractError:
        return {"status": "INVALID", "code": "E_SHAPE", "field": "root", "reason": "E_SHAPE at root", "board": None}
    except Exception:                                   # any lower-level failure: stable code, nothing echoed
        return {"status": "INVALID", "code": "E_INTERNAL", "field": "root", "reason": "E_INTERNAL at root", "board": None}


def load_public(path: Path) -> dict | None:
    """Read-only loader for deployed surfaces (API/MCP/site): a VALIDATED, non-synthetic scoreboard file or None."""
    return inspect_public(path)["board"]
