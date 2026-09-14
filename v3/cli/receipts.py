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

from v3.receipts import counting, credentials, export, scoreboard, verify
from v3.receipts.contracts import ContractError
from v3.receipts.store import Store


def _refuse_public_store(store: str) -> None:
    """A store must never live inside a checkout's public tree (docs/ next to release_manifest.json)."""
    p = Path(store).resolve()
    for parent in [p] + list(p.parents):
        if parent.name == "docs" and (parent.parent / "release_manifest.json").exists():
            raise ContractError(f"--store must not be inside the public tree {parent}")


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
    s = p.add_subparsers(dest="cmd", required=True)
    i = s.add_parser("import"); i.add_argument("submission_json")
    o = s.add_parser("observe"); o.add_argument("receipt_digest"); o.add_argument("--path"); o.add_argument("--allowed-root", action="append", default=[])
    r = s.add_parser("review"); r.add_argument("receipt_digest"); r.add_argument("state"); r.add_argument("--role", required=True); r.add_argument("--reason", default="")
    credentials.add_token_arguments(r)
    s.add_parser("derive"); s.add_parser("counts")
    e = s.add_parser("export"); e.add_argument("--out")
    b = s.add_parser("scoreboard"); b.add_argument("--out")
    a = p.parse_args(argv)
    try:
        _refuse_public_store(a.store)
        st = Store(a.store)
        registration = _load_json_file(a.registration, "--registration") if a.registration else None
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
            print(json.dumps(counting.counts(derived, registration=registration), indent=1)); return 0
        if a.cmd == "export":
            rows = export.project_many(derived, st, mode=("synthetic" if a.synthetic else "public"))
            txt = json.dumps(rows, indent=1)
            if a.out: Path(a.out).write_text(txt + "\n")
            else: print(txt)
            return 0
        if a.cmd == "scoreboard":
            board = scoreboard.build(a.store, synthetic=a.synthetic, registration=registration)
            txt = json.dumps(board, indent=1)
            if a.out: Path(a.out).write_text(txt + "\n"); print(f"[receipts] scoreboard written {a.out} (synthetic={a.synthetic})")
            else: print(txt)
            return 0
    except ContractError as exc:
        print(f"[receipts] REJECTED: {exc}", file=sys.stderr); return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
