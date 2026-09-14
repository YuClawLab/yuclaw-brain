"""`yuclaw receipts <cmd>` — local receipt workflow (v7). Import a submission, observe an artifact's
bytes, record a review (authorized role + token from the trusted store), derive/count, export, build the
scoreboard. Exit 0 ok; 1 contract/authority error; 2 usage. Research only — not investment advice."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts import counting, export, scoreboard, verify
from v3.receipts.contracts import ContractError
from v3.receipts.store import Store


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw receipts")
    p.add_argument("--store", required=True, help="private store directory (never inside docs/)")
    p.add_argument("--synthetic", action="store_true", help="fixture mode: records are synthetic and can never enter a public export")
    s = p.add_subparsers(dest="cmd", required=True)
    i = s.add_parser("import"); i.add_argument("submission_json")
    o = s.add_parser("observe"); o.add_argument("receipt_digest"); o.add_argument("--path"); o.add_argument("--allowed-root", action="append", default=[])
    r = s.add_parser("review"); r.add_argument("receipt_digest"); r.add_argument("state"); r.add_argument("--role", required=True); r.add_argument("--token", required=True); r.add_argument("--reason", default="")
    s.add_parser("derive"); s.add_parser("counts")
    e = s.add_parser("export"); e.add_argument("--out")
    b = s.add_parser("scoreboard"); b.add_argument("--out")
    a = p.parse_args(argv)
    st = Store(a.store)
    try:
        if a.cmd == "import":
            raw = json.loads(Path(a.submission_json).read_text())
            rec = st.import_submission(raw, synthetic=a.synthetic)
            print(json.dumps({"digest": rec["digest"], "version": rec["version"], "duplicate": rec.get("duplicate", False), "diagnostics": rec["diagnostics"]}, indent=1)); return 0
        if a.cmd == "observe":
            recs = [x for x in st.current_submissions().values() if x["digest"] == a.receipt_digest]
            if not recs: print("unknown receipt digest", file=sys.stderr); return 1
            obs = verify.observe(recs[0]["submission"]["artifact_binding"], path=a.path, allowed_roots=a.allowed_root or [str(Path.cwd())]) if a.path else verify.observe(recs[0]["submission"]["artifact_binding"])
            st.add_observation(a.receipt_digest, obs); print(json.dumps(obs, indent=1)); return 0
        if a.cmd == "review":
            print(json.dumps(st.add_review(a.receipt_digest, a.state, reviewer_role=a.role, token=a.token, reason=a.reason), indent=1)); return 0
        derived = counting.derive(st, synthetic=a.synthetic)
        if a.cmd == "derive":
            print(json.dumps([{k: d[k] for k in ("attempt_id", "digest", "binding_completeness", "qualified", "successful", "reasons")} for d in derived], indent=1)); return 0
        if a.cmd == "counts":
            print(json.dumps(counting.counts(derived), indent=1)); return 0
        if a.cmd == "export":
            rows = export.project_many(derived, st, mode=("synthetic" if a.synthetic else "public"))
            txt = json.dumps(rows, indent=1)
            if a.out: Path(a.out).write_text(txt + "\n")
            else: print(txt)
            return 0
        if a.cmd == "scoreboard":
            board = scoreboard.build(a.store, synthetic=a.synthetic)
            txt = json.dumps(board, indent=1)
            if a.out: Path(a.out).write_text(txt + "\n"); print(f"[receipts] scoreboard written {a.out} (synthetic={a.synthetic})")
            else: print(txt)
            return 0
    except ContractError as exc:
        print(f"[receipts] REJECTED: {exc}", file=sys.stderr); return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
