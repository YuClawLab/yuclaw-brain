"""`yuclaw receipts <cmd>` — local receipt workflow (v7). Import a submission, observe an artifact's
bytes, record a review (authorized role + credential from the trusted store), derive/count, export, build
the scoreboard. Exit 0 ok; 1 contract/authority/input error; 2 usage. The reviewer credential is read from
`--token-file` (owner-only file), `--token-fd` or an interactive no-echo prompt — never from a process
argument. Research only — not investment advice."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datetime import datetime, timezone

from v3.receipts import counting, credentials, export, scoreboard, target as _target, verify
from v3.receipts.contracts import ContractError, parse_ts
from v3.receipts.store import Store

REASON_CODES = {   # public explanation codes (the private reason text stays private)
    "review state": "R_REVIEW_STATE", "review under a different policy version": "R_POLICY_VERSION", "review lacks appointment evidence": "R_NO_APPOINTMENT_EVIDENCE",
    "review appointment id has no immutable": "R_NO_APPOINTMENT_RECORD", "review appointment is": "R_APPOINTMENT_NOT_DESIGNATED", "review appointment belongs": "R_APPOINTMENT_ROLE",
    "review appointment is bound": "R_APPOINTMENT_POLICY", "review decided before": "R_REVIEW_BEFORE_APPOINTMENT", "review line authority": "R_AUTHORITY_LABEL",
    "relationship": "R_RELATIONSHIP", "OPERATOR-RUN": "R_OPERATOR_RUN", "ASSISTED without": "R_ASSISTANCE", "outcome-dependent": "R_INCENTIVE", "binding": "R_BINDING"}


def _code(reason: str) -> str:
    for k, v in REASON_CODES.items():
        if reason.startswith(k):
            return v
    return "R_OTHER"


def explain(st: Store, ref: str, *, synthetic: bool, registration: dict | None, private: bool) -> dict:
    """Why did this receipt count / not count? Public part = codes and derived states; private part only on request."""
    rec = st.find(ref)
    if rec is None:
        raise ContractError("unknown receipt reference (attempt_id, public receipt id or private digest)")
    rows = [r for r in counting.derive(st, synthetic=synthetic) if r["attempt_id"] == rec["submission"]["attempt_id"]]
    if not rows:
        raise ContractError("receipt exists but not under the requested provenance (use/omit --synthetic)")
    row = rows[0]; sub = row["submission"]; cls = counting.classify(row, counting.validate_registration(registration) if registration else None)
    out = {"receipt_id": st.public_id(row["digest"]), "attempt_id": row["attempt_id"], "activity_type": row["activity_type"], "version": row["version"], "corrected": row["corrected"],
           "artifact_scope": dict(sub["artifact_binding"]), "release_identity": sub["release_identity"],
           "observation": {"status": ("VERIFIED" if row["binding_completeness"] == "FULL" else ("UNVERIFIED" if row["observation"] else "NONE")), "source": (row["observation"] or {}).get("source")},
           "review": {"state": (row["review"] or {}).get("state", "RECEIVED"), "authority": (row["review"] or {}).get("authority", "NONE"), "appointment_bound": bool((row["review"] or {}).get("appointment_id"))},
           "qualified": row["qualified"], "successful": row["successful"], "reason_codes": [_code(r) for r in row["reasons"]],
           "counting": {"eligibility": cls["eligibility"], "window": cls["window"], "bucket": cls["key"], "registration": "REGISTERED" if registration else "PENDING (unwindowed)"},
           "lineage": {"versions": row["lineage"]["versions"], "first_observed_at": row["lineage"]["first_observed_at"], "superseded_at": row["lineage"]["superseded_at"]},
           "counts_because": ("qualified attempt in the primary population" + (" and successful" if row["successful"] else "")) if row["qualified"] else "not qualified: see reason_codes",
           "meaning": "derived from records; no trust score; research only"}
    if private:
        out["private"] = {"reasons": row["reasons"], "digest": row["digest"], "chain": row["lineage"]["chain"], "participant_id": sub["participant_id"], "group_id": sub["group_id"]}
    return out


def _load_json_file(path: str, what: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError(f"{what}: cannot read {path} ({exc.__class__.__name__})") from None
    except ValueError as exc:
        raise ContractError(f"{what}: malformed JSON in {path} ({exc.__class__.__name__})") from None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw receipts")
    p.add_argument("--store", required=True, help="private store directory (never inside docs/)")
    p.add_argument("--synthetic", action="store_true", help="fixture mode: records are synthetic and can never enter a public export")
    p.add_argument("--registration", help="JSON file with the owner's registration record {protocol_id, anchor, registered_at, policy_version}; absent → unwindowed (pending)")
    p.add_argument("--target", help="release TARGET manifest JSON (independently supplied; exact-target coverage is UNBOUND without it)")
    p.add_argument("--now", help="frozen clock for the board's source_timestamp (RFC3339 UTC with microseconds); default: now")
    p.add_argument("--legacy-log", help="public legacy replication log JSON (default: the checkout's docs/replication/replication_log.json; ABSENT is reported, never counted as zero)")
    s = p.add_subparsers(dest="cmd", required=True)
    i = s.add_parser("import"); i.add_argument("submission_json")
    o = s.add_parser("observe"); o.add_argument("receipt_digest"); o.add_argument("--path"); o.add_argument("--allowed-root", action="append", default=[])
    r = s.add_parser("review"); r.add_argument("receipt_digest"); r.add_argument("state"); r.add_argument("--role", required=True); r.add_argument("--reason", default="")
    credentials.add_token_arguments(r)
    s.add_parser("derive"); s.add_parser("counts")
    e = s.add_parser("export"); e.add_argument("--out")
    b = s.add_parser("scoreboard"); b.add_argument("--out")
    x = s.add_parser("explain", help="why did this receipt count or not count (attempt id, public receipt id or private digest)"); x.add_argument("ref"); x.add_argument("--private", action="store_true", help="include private supporting facts (never for publication)")
    h = s.add_parser("history", help="compare two bound scoreboard snapshots (validated): additions, supersessions, disposition changes, window movement, absolute movement"); h.add_argument("snapshot_a"); h.add_argument("snapshot_b")
    a = p.parse_args(argv)
    try:
        if a.cmd == "history":
            infos = [scoreboard.inspect_public(Path(x)) for x in (a.snapshot_a, a.snapshot_b)]
            bad = [(x, i["status"], i["reason"]) for x, i in zip((a.snapshot_a, a.snapshot_b), infos) if i["board"] is None]
            if bad:
                print("[receipts] history: snapshot unusable: " + "; ".join(f"{Path(x).name}: {st_} ({why})" for x, st_, why in bad), file=sys.stderr); return 3
            if infos[0]["board"]["public_schema_version"] != infos[1]["board"]["public_schema_version"]:
                print("[receipts] history: incompatible snapshots (different public schema versions)", file=sys.stderr); return 3
            print(json.dumps(scoreboard.history(infos[0]["board"], infos[1]["board"]), indent=1)); return 0
        st = Store(a.store)
        registration = _load_json_file(a.registration, "--registration") if a.registration else None
        target = _target.validate_target(_load_json_file(a.target, "--target")) if a.target else None
        now = None
        if a.now:
            now = parse_ts(a.now, "--now")
        if a.cmd == "import":
            raw = _load_json_file(a.submission_json, "submission")
            rec = st.import_submission(raw, synthetic=a.synthetic)
            print(json.dumps({"digest": rec["digest"], "version": rec["version"], "duplicate": rec.get("duplicate", False), "diagnostics": rec["diagnostics"]}, indent=1)); return 0
        if a.cmd == "observe":
            rec = st.receipt(a.receipt_digest)
            if rec is None or st.current_submissions().get(rec["submission"]["attempt_id"], {}).get("digest") != a.receipt_digest:
                print("[receipts] REJECTED: unknown or superseded receipt digest", file=sys.stderr); return 1
            try:
                obs = (verify.observe(rec["submission"]["artifact_binding"], path=a.path, allowed_roots=a.allowed_root or [str(Path.cwd())]) if a.path
                       else verify.observe(rec["submission"]["artifact_binding"]))
            except OSError as exc:
                raise ContractError(f"artifact path unreadable ({exc.__class__.__name__})") from None
            st.add_observation(a.receipt_digest, obs); print(json.dumps(obs, indent=1)); return 0
        if a.cmd == "review":
            token = credentials.read_token(a)
            rec = st.add_review(a.receipt_digest, a.state, reviewer_role=a.role, token=token, reason=a.reason)
            print(json.dumps(rec, indent=1)); return 0
        derived = counting.derive(st, synthetic=a.synthetic)
        if a.cmd == "derive":
            print(json.dumps([{k: d[k] for k in ("attempt_id", "digest", "binding_completeness", "qualified", "successful", "reasons")} for d in derived], indent=1)); return 0
        if a.cmd == "counts":
            c = counting.counts(derived, registration=registration); c["exact_target_evidence"] = _target.coverage(derived, target)
            print(json.dumps(c, indent=1)); return 0
        if a.cmd == "export":
            rows = export.project_many(derived, st, mode=("synthetic" if a.synthetic else "public"))
            if not a.synthetic:
                pol = export.publication_policy()
                if pol["denylist"] != "AVAILABLE":
                    raise ContractError("E_POLICY_UNAVAILABLE: the private publication denylist is unavailable; nothing is exported (a missing denylist is not an empty denylist)")
                export.sweep_strings(rows, "export")            # whole-object sweep at the shared public boundary; field path only, never the value
            txt = json.dumps(rows, indent=1)
            if a.out: Path(a.out).write_text(txt + "\n")
            else: print(txt)
            return 0
        if a.cmd == "scoreboard":
            board = scoreboard.build(a.store, synthetic=a.synthetic, registration=registration, target=target, now=now, legacy_log=a.legacy_log)
            txt = scoreboard.canonical_bytes(board).decode("ascii")          # ONE canonical serialization: the static file == the served object
            if a.out: Path(a.out).write_bytes(txt.encode("ascii") + b"\n"); print(f"[receipts] scoreboard written {a.out} (synthetic={a.synthetic}; target {board['target']['state']})")
            else: print(txt)
            return 0
        if a.cmd == "explain":
            print(json.dumps(explain(st, a.ref, synthetic=a.synthetic, registration=registration, private=a.private), indent=1)); return 0
    except ContractError as exc:
        print(f"[receipts] REJECTED: {exc}", file=sys.stderr); return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
