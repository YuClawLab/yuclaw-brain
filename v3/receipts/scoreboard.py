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
_PRINTABLE = re.compile(r"^[^\x00-\x1f\x7f]*$")      # no control characters; Unicode punctuation allowed


def _s(v, field, maxlen=2000):
    if not isinstance(v, str) or len(v) > maxlen or not _PRINTABLE.match(v):
        raise ContractError(f"board {field}: bounded string without control characters required")
    return v


def _int(v, field):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ContractError(f"board {field}: nonnegative integer required")
    return v


def validate_board(board) -> dict:
    """Typed validation of a PUBLIC scoreboard file before any surface serves it. Synthetic boards are
    refused; malformed boards are errors (surfaces then show UNAVAILABLE, never a measured zero)."""
    if not isinstance(board, dict):
        raise ContractError("board: object required")
    if board.get("synthetic") is not False:
        raise ContractError("board is synthetic or unlabeled; a public surface never serves it")
    for k in ("scoreboard_version", "source_timestamp", "definitions", "columns", "receipts_public", "challenges_public", "decisions_public", "policy_version", "not_advice"):
        if k not in board:
            raise ContractError(f"board: missing {k}")
    _s(board["scoreboard_version"], "scoreboard_version", 64); _s(board["policy_version"], "policy_version", 64); _s(board["not_advice"], "not_advice", 500)
    parse_ts(board["source_timestamp"], "board.source_timestamp")
    if not isinstance(board["definitions"], dict) or set(board["definitions"]) != set(DEFINITIONS):
        raise ContractError("board.definitions: must carry exactly the registered columns")
    cols = board["columns"]
    if not isinstance(cols, dict) or set(cols) != set(DEFINITIONS):
        raise ContractError("board.columns: must carry exactly the registered columns")
    for name, col in cols.items():
        if not isinstance(col, dict) or not isinstance(col.get("state"), str):
            raise ContractError(f"board.columns.{name}: object with state required")
        _s(col["state"], f"columns.{name}.state", 64)
        for k, v in col.items():
            if isinstance(v, str):
                _s(v, f"columns.{name}.{k}")
            elif isinstance(v, int) and not isinstance(v, bool):
                _int(v, f"columns.{name}.{k}")
    rep = cols["replications"]
    for k in ("attempts", "qualified", "successful"):
        _int(rep.get(k), f"replications.{k}")
    for k in ("visible", "windows", "registration", "artifacts", "program_evidence_legacy", "exact_release_evidence"):
        if not isinstance(rep.get(k), dict):
            raise ContractError(f"replications.{k}: object required")
    for k in ("successful_cohort_artifacts", "attempted_artifacts", "verified_artifacts", "package_reproductions_successful"):
        _int(rep["artifacts"].get(k), f"replications.artifacts.{k}")
    _s(rep["artifacts"].get("note", ""), "replications.artifacts.note")
    _int(rep["exact_release_evidence"].get("successful_package_reproductions"), "exact_release_evidence.successful_package_reproductions")
    for k in ("entries", "reproduced", "affiliated"):
        _int(rep["program_evidence_legacy"].get(k), f"program_evidence_legacy.{k}")
    _s(rep["registration"].get("status", ""), "registration.status", 64)
    for w, v in rep["windows"].items():
        _s(w, "windows.key", 256)
        if not isinstance(v, dict):
            raise ContractError("windows: object per window required")
        for k, n in v.items():
            if isinstance(n, bool):
                continue
            _int(n, f"windows.{w}.{k}")
    if not isinstance(board["receipts_public"], list) or not isinstance(board["challenges_public"], list) or not isinstance(board["decisions_public"], list):
        raise ContractError("board: receipts_public/challenges_public/decisions_public must be lists")
    for r in board["receipts_public"]:
        row = export.revalidate(r)
        if row["synthetic"] is not False:
            raise ContractError("board.receipts_public: synthetic row in a public board")
    for c in board["challenges_public"]:
        if not isinstance(c, dict) or set(c) - {"challenge_id", "artifact", "claim_id", "disposition", "version", "created_at", "synthetic", "disposed_by_authority", "resolution", "adverse"}:
            raise ContractError("board.challenges_public: unexpected shape")
        _s(c.get("challenge_id"), "challenge.challenge_id", 128); _s(c.get("claim_id"), "challenge.claim_id", 128)
        validate_binding_claim(c.get("artifact"), "challenge.artifact")
        if c.get("disposition") not in DISPOSITIONS or not isinstance(c.get("adverse"), bool) or c.get("synthetic") is not False:
            raise ContractError("board.challenges_public: disposition/adverse/synthetic invalid")
        _int(c.get("version"), "challenge.version"); parse_ts(c.get("created_at"), "challenge.created_at")
    for d in board["decisions_public"]:
        if not isinstance(d, dict) or set(d) != set(DECISION_FIELDS):
            raise ContractError("board.decisions_public: unexpected shape")
        if not isinstance(d["packet_manifest_digest"], str) or not _HEX64.match(d["packet_manifest_digest"]) or d["synthetic"] is not False:
            raise ContractError("board.decisions_public: digest/synthetic invalid")
        _s(d["decision_id"], "decision.decision_id", 128); _s(d["decision"], "decision.decision", 32); _s(d["claim_id"], "decision.claim_id", 128); parse_ts(d["decided_at"], "decision.decided_at")
    return board


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
        return {"status": "OK", "reason": "validated", "board": validate_board(board)}
    except ContractError as exc:
        return {"status": "INVALID", "reason": str(exc)[:200], "board": None}


def load_public(path: Path) -> dict | None:
    """Read-only loader for deployed surfaces (API/MCP/site): a VALIDATED, non-synthetic scoreboard file or None."""
    return inspect_public(path)["board"]
