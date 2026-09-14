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

from v3.receipts import counting, export, legacy
from v3.receipts.challenge import ChallengeStore, DISPOSITIONS
from v3.receipts.contracts import ContractError, parse_ts, validate_binding_claim
from v3.receipts.decision import DecisionStore, MEANING as DECISION_MEANING, PUBLIC_FIELDS as DECISION_FIELDS
from v3.receipts.store import Store

_REPO = Path(__file__).resolve().parents[2]
DEFINITIONS = {
    "witnesses": "people who examined the methodology and left a reviewable receipt (none recorded: 0)",
    "pilots": "BYOS pilot engagements with a signed scope (none: counsel review is the blocker)",
    "replications": "attempts to reproduce published artifacts; primary population = qualified attempts (failed/inconclusive retained); successful reported separately",
    "audits": "third-party audits with a receipt (internal gate runs are not audits)",
    "refusals": "recorded refusals/held submissions (visible, never hidden)",
    "packet_uses": "document-use receipts bound to an exact packet digest and exported with permission",
    "challenges": "structured challenges by disposition; adverse = OPEN or CONFIRMED; RESOLVED keeps the original finding",
}


def build(store_dir, *, synthetic: bool = False, registration: dict | None = None, now: datetime | None = None, legacy_log: Path | None = None) -> dict:
    st = Store(store_dir); cs = ChallengeStore(store_dir); ds = DecisionStore(store_dir)
    derived = counting.derive(st, synthetic=synthetic)
    c = counting.counts(derived, registration=registration)
    log_path = legacy_log or (_REPO / "docs/replication/replication_log.json")
    leg = legacy.adapt_log(json.loads(log_path.read_text())) if (log_path.exists() and not synthetic) else []
    chal = cs.public_view(synthetic=synthetic)
    by_disp = {}
    for r in chal: by_disp[r["disposition"]] = by_disp.get(r["disposition"], 0) + 1
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rows = export.project_many(derived, st, mode=("synthetic" if synthetic else "public"))
    board = {
        "scoreboard_version": "v7-candidate-1", "synthetic": synthetic, "source_timestamp": ts, "definitions": DEFINITIONS,
        "columns": {
            "witnesses": {"count": 0, "state": "ZERO"},
            "pilots": {"count": 0, "state": "PENDING_COUNSEL_REVIEW"},
            "replications": {"attempts": c["attempts"], "qualified": c["qualified"], "successful": c["successful"], "visible": c["visible"],
                              "windows": c["windows"], "registration": c["registration"], "artifacts": c["artifacts"],
                              "program_evidence_legacy": {"entries": len(leg), "reproduced": sum(1 for l in leg if l["outcome"] == "REPRODUCED"),
                                                          "binding": "PREFIX_ONLY (historical; not exact-release evidence)", "affiliated": sum(1 for l in leg if l["relationship"] == "OWNER-AFFILIATED")},
                              "exact_release_evidence": {"successful_package_reproductions": c["artifacts"]["package_reproductions_successful"],
                                                         "note": "counts only qualified successful attempts whose exact wheel/sdist bytes were verified"},
                              "state": "PENDING_REGISTRATION" if c["registration"]["status"] == "PENDING" else "REGISTERED"},
            "audits": {"count": 0, "state": "ZERO"},
            "refusals": {"count": c["visible"]["unqualified"], "held": sum(1 for r in derived if (r.get("review") or {}).get("state") == "HELD"), "state": "OBSERVED"},
            "packet_uses": {"count": len(ds.export(synthetic=synthetic)), "state": "OBSERVED", "note": DECISION_MEANING},
            "challenges": {"by_disposition": by_disp, "adverse_open": sum(1 for r in chal if r["adverse"]), "total": len(chal), "state": "OBSERVED"},
        },
        "receipts_public": rows, "challenges_public": chal, "decisions_public": ds.export(synthetic=synthetic),
        "policy_version": c["policy_version"], "not_advice": "Research and education only. Not investment advice. No composite trust score is computed.",
    }
    return board


def history(a: dict, b: dict) -> dict:
    """What changed between two scoreboard snapshots (evidence and dispositions only)."""
    ra = {r["receipt_digest"]: r for r in a.get("receipts_public", [])}; rb = {r["receipt_digest"]: r for r in b.get("receipts_public", [])}
    ca = {c["challenge_id"]: c for c in a.get("challenges_public", [])}; cb = {c["challenge_id"]: c for c in b.get("challenges_public", [])}
    changed = [{"challenge_id": k, "from": ca[k]["disposition"], "to": cb[k]["disposition"]} for k in ca if k in cb and ca[k]["disposition"] != cb[k]["disposition"]]
    ma = a["columns"]["replications"]; mb = b["columns"]["replications"]
    return {"from": a["source_timestamp"], "to": b["source_timestamp"],
            "receipts_added": sorted(set(rb) - set(ra)), "receipts_removed_or_superseded": sorted(set(ra) - set(rb)),
            "challenges_added": sorted(set(cb) - set(ca)), "dispositions_changed": changed,
            "movement": counting.movement({"attempts": ma["attempts"], "qualified": ma["qualified"], "successful": ma["successful"]},
                                          {"attempts": mb["attempts"], "qualified": mb["qualified"], "successful": mb["successful"]})}


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TEXT = re.compile(r"^[^\x00-\x1f\x7f]*$")      # no control characters; Unicode punctuation allowed
BOARD_SCHEMA_VERSION = "public-board-schema/1"
from v3.receipts.contracts import ARTIFACT_TYPES, REVIEW_AUTHORITIES
from v3.receipts.counting import ELIGIBILITY
from v3.receipts.decision import DECISIONS

# ---- schema combinators: every validator returns a FRESH value built only from validated fields; unknown keys
# ---- at any depth are errors; error text names the field path only, never the offending value or key name.


def _err(field, what):
    raise ContractError(f"board {field}: {what}")


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
        _err(field, "timestamp required")
    parse_ts(v, field); return v


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
        _err(field, "public receipt row does not match PUBLIC_SHAPE")
    for k in ("attempt_id", "artifact_binding", "outcome", "review_state", "review_authority", "binding_completeness", "qualified", "successful", "receipt_digest", "participant"):
        if k not in row:
            _err(field, "public receipt row missing a required field")
    if row["synthetic"] is not False:
        _err(field, "synthetic row in a public board")
    return row


WINDOW = _obj({"primary_distinct_persons": _int, "primary_distinct_groups": _int, "primary_attempts": _int, "successful_distinct_persons": _int,
               "successful_distinct_groups": _int, "successful_attempts": _int, "eligibility": _enum(ELIGIBILITY), "prospective": _bool})
REGISTRATION = _obj({"status": _enum(("PENDING", "REGISTERED")), "note": _s(500), "protocol_id": _idv, "anchor": _s(10), "registered_at": _ts,
                     "policy_version": _s(64), "window_days": _int, "prospective_rule": _s(500)}, required=("status",))
ARTIFACTS = _obj({"successful_cohort_artifacts": _int, "attempted_artifacts": _int, "verified_artifacts": _int, "package_reproductions_successful": _int,
                  "attempted_by_type": _map(_enum(ARTIFACT_TYPES), _int), "successful_by_type": _map(_enum(ARTIFACT_TYPES), _int), "note": _s(500)})
REPLICATIONS = _obj({"attempts": _int, "qualified": _int, "successful": _int,
                     "visible": _obj({"failed": _int, "inconclusive": _int, "qualified_failed": _int, "qualified_inconclusive": _int, "unqualified": _int}),
                     "windows": _map(_s(256), WINDOW), "registration": REGISTRATION, "artifacts": ARTIFACTS,
                     "program_evidence_legacy": _obj({"entries": _int, "reproduced": _int, "affiliated": _int, "binding": _s(200)}),
                     "exact_release_evidence": _obj({"successful_package_reproductions": _int, "note": _s(500)}),
                     "state": _enum(("PENDING_REGISTRATION", "REGISTERED"))})
COLUMNS = _obj({"witnesses": _obj({"count": _int, "state": _enum(("ZERO", "OBSERVED"))}),
                "pilots": _obj({"count": _int, "state": _enum(("PENDING_COUNSEL_REVIEW", "ZERO", "OBSERVED"))}),
                "replications": REPLICATIONS,
                "audits": _obj({"count": _int, "state": _enum(("ZERO", "OBSERVED"))}),
                "refusals": _obj({"count": _int, "held": _int, "state": _enum(("OBSERVED",))}),
                "packet_uses": _obj({"count": _int, "state": _enum(("OBSERVED",)), "note": _s(500)}),
                "challenges": _obj({"by_disposition": _map(_enum(DISPOSITIONS), _int), "adverse_open": _int, "total": _int, "state": _enum(("OBSERVED",))})})
CHALLENGE_ROW = _obj({"challenge_id": _idv, "artifact": _binding, "claim_id": _idv, "disposition": _enum(DISPOSITIONS), "version": _int, "created_at": _ts,
                      "synthetic": _const(False), "disposed_by_authority": _nullable(_enum(("DESIGNATED", "SYNTHETIC", "HELD", "challenger"))),
                      "resolution": _nullable(_obj({"revised_artifact": _binding, "verification_method": _enum(("packet-verify", "receipt")), "original_finding_retained": _const(True)})),
                      "adverse": _bool})
DECISION_ROW = _obj({"decision_id": _idv, "decision": _enum(DECISIONS), "packet_manifest_digest": _hex, "claim_id": _idv, "decided_at": _ts, "synthetic": _const(False)})
BOARD = _obj({"scoreboard_version": _s(64), "synthetic": _const(False), "source_timestamp": _ts,
              "definitions": _obj({k: _s(500) for k in DEFINITIONS}), "columns": COLUMNS,
              "receipts_public": _list(_receipt_row), "challenges_public": _list(CHALLENGE_ROW), "decisions_public": _list(DECISION_ROW),
              "policy_version": _s(64), "not_advice": _s(500)})


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
    if out["columns"]["refusals"]["count"] != vis["unqualified"]:
        _err("columns.refusals", "count relationship violated (refusals = unqualified attempts)")
    if len(out["receipts_public"]) != rep["attempts"]:
        _err("receipts_public", "row count must equal replications.attempts")
    if ch["adverse_open"] > ch["total"] or sum(ch["by_disposition"].values()) != ch["total"] or len(out["challenges_public"]) != ch["total"]:
        _err("columns.challenges", "count relationship violated")
    if sum(1 for c in out["challenges_public"] if c["adverse"]) != ch["adverse_open"]:
        _err("columns.challenges", "adverse_open must equal the adverse rows")
    if (rep["registration"]["status"] == "REGISTERED") != (rep["state"] == "REGISTERED"):
        _err("columns.replications.state", "state must agree with registration.status")
    for k, w in rep["windows"].items():
        if w["prospective"] != (w["eligibility"] == "prospective") or w["successful_attempts"] > w["primary_attempts"]:
            _err("columns.replications.windows", "window relationship violated")
    out["public_schema_version"] = BOARD_SCHEMA_VERSION
    return out


def inspect_public(path: Path) -> dict:
    """{'status': 'OK'|'ABSENT'|'INVALID'|'SYNTHETIC_REFUSED', 'reason': str, 'board': dict|None}.
    ABSENT/INVALID are UNAVAILABLE states for surfaces — never a measured zero."""
    path = Path(path)
    if not path.exists():
        return {"status": "ABSENT", "reason": "no public scoreboard file", "board": None}
    try:
        board = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return {"status": "INVALID", "reason": f"unreadable: {exc.__class__.__name__}", "board": None}
    if isinstance(board, dict) and board.get("synthetic") is not False:
        return {"status": "SYNTHETIC_REFUSED", "reason": "a synthetic board is never served as public", "board": None}
    try:
        return {"status": "OK", "reason": "validated against " + BOARD_SCHEMA_VERSION, "board": validate_board(board)}
    except ContractError as exc:
        return {"status": "INVALID", "reason": str(exc)[:200], "board": None}      # field path only; no values echoed


def load_public(path: Path) -> dict | None:
    """Read-only loader for deployed surfaces (API/MCP/site): a VALIDATED, non-synthetic scoreboard file or None."""
    return inspect_public(path)["board"]
