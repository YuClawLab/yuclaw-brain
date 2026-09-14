"""`yuclaw challenge` — local structured challenges bound to artifact + claim identifiers (v7).
Exit 0 ok; 1 contract/authority/input error; 2 usage. CONFIRMED / REFUTED / RESOLVED need a reviewer
appointment (`--role` + credential from --token-file / --token-fd / no-echo prompt); RESOLVED also needs the
revised artifact's actual bytes (`--revised-path`) and a `--verification-id` produced by `verify-revision` (exit 1 when the
executed verification did not succeed)."""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
from v3.receipts import credentials
from v3.receipts.challenge import ChallengeStore, CRITERIA, EVALUATION_OUTCOMES, TRUSTED_DISPOSITIONS
from v3.receipts.contracts import ContractError


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw challenge"); p.add_argument("--store", required=True); p.add_argument("--synthetic", action="store_true")
    s = p.add_subparsers(dest="cmd", required=True)
    c = s.add_parser("create"); c.add_argument("challenge_id"); c.add_argument("--artifact-type", required=True); c.add_argument("--sha256", required=True); c.add_argument("--size-bytes", type=int, required=True)
    c.add_argument("--claim-id", required=True); c.add_argument("--expected", required=True); c.add_argument("--observed", required=True)
    c.add_argument("--criterion", default="general", choices=list(CRITERIA), help="machine-checkable criterion (allowlisted verifier) or 'general' (needs a reviewer evaluation)")
    d = s.add_parser("dispose"); d.add_argument("challenge_id"); d.add_argument("disposition"); d.add_argument("--role", help="reviewer role (required for CONFIRMED/REFUTED/RESOLVED)")
    credentials.add_token_arguments(d)
    d.add_argument("--revised-type"); d.add_argument("--revised-sha256"); d.add_argument("--revised-size-bytes", type=int)
    d.add_argument("--revised-path", help="actual bytes of the revised artifact (must equal the claimed revised binding)"); d.add_argument("--allowed-root", action="append", default=[])
    d.add_argument("--verification-id", help="id of a verification record produced by `verify-revision` for this challenge, criterion and revised artifact")
    d.add_argument("--evaluation-id", help="id of an evaluation record produced by `evaluate` (general criteria)"); d.add_argument("--reason", default="")
    ev = s.add_parser("evaluate", help="record a reviewer's explicit evaluation of the stated criterion (general criteria; DESIGNATED for real challenges)")
    ev.add_argument("challenge_id"); ev.add_argument("--role", required=True); credentials.add_token_arguments(ev); ev.add_argument("--outcome", required=True, choices=list(EVALUATION_OUTCOMES)); ev.add_argument("--statement", required=True)
    ev.add_argument("--revised-type"); ev.add_argument("--revised-sha256"); ev.add_argument("--revised-size-bytes", type=int)
    vr = s.add_parser("verify-revision", help="execute the permitted deterministic verifier for a revised artifact and record the result (packet-verify or receipt)")
    vr.add_argument("challenge_id"); vr.add_argument("--revised-type", required=True); vr.add_argument("--revised-sha256", required=True); vr.add_argument("--revised-size-bytes", type=int, required=True)
    vr.add_argument("--method", required=True, choices=["packet-verify", "receipt"]); vr.add_argument("--packet"); vr.add_argument("--receipt-digest")
    s.add_parser("list"); h = s.add_parser("history"); h.add_argument("challenge_id")
    a = p.parse_args(argv)
    try:
        cs = ChallengeStore(a.store)
        if a.cmd == "create":
            print(json.dumps(cs.create(a.challenge_id, artifact={"artifact_type": a.artifact_type, "sha256": a.sha256, "size_bytes": a.size_bytes}, claim_id=a.claim_id, expected=a.expected, observed=a.observed, synthetic=a.synthetic, criterion=a.criterion), indent=1)); return 0
        if a.cmd == "evaluate":
            token = credentials.read_token(a)
            ra = {"artifact_type": a.revised_type, "sha256": a.revised_sha256, "size_bytes": a.revised_size_bytes} if a.revised_sha256 else None
            rec = cs.evaluate(a.challenge_id, reviewer_role=a.role, token=token, outcome=a.outcome, statement=a.statement, revised_artifact=ra)
            print(json.dumps({k: rec[k] for k in ("evaluation_id", "challenge_id", "criterion", "outcome", "evaluated_at")} | {"authority": rec["evaluator"]["authority"]}, indent=1)); return 0
        if a.cmd == "dispose":
            token = credentials.read_token(a) if a.disposition in TRUSTED_DISPOSITIONS else None
            ra = {"artifact_type": a.revised_type, "sha256": a.revised_sha256, "size_bytes": a.revised_size_bytes} if a.revised_sha256 else None
            try:
                rec = cs.dispose(a.challenge_id, a.disposition, reviewer_role=a.role, token=token, revised_artifact=ra, revised_path=a.revised_path,
                                 allowed_roots=a.allowed_root or [str(Path.cwd())], verification_id=a.verification_id, evaluation_id=a.evaluation_id, reason=a.reason)
            except OSError as exc:
                raise ContractError(f"revised artifact path unreadable ({exc.__class__.__name__})") from None
            print(json.dumps(rec, indent=1)); return 0
        if a.cmd == "verify-revision":
            ra = {"artifact_type": a.revised_type, "sha256": a.revised_sha256, "size_bytes": a.revised_size_bytes}
            rec = cs.verify_revision(a.challenge_id, revised_artifact=ra, method=a.method, packet_dir=a.packet, receipt_digest=a.receipt_digest)
            print(json.dumps({k: rec[k] for k in ("verification_id", "challenge_id", "criterion", "method", "result", "reason", "executed_at")}, indent=1)); return 0 if rec["result"] == "SUCCESS" else 1
        if a.cmd == "list":
            print(json.dumps(cs.public_view(synthetic=a.synthetic), indent=1)); return 0
        if a.cmd == "history":
            print(json.dumps(cs.history(a.challenge_id), indent=1)); return 0
    except ContractError as exc:
        print(f"[challenge] REJECTED: {exc}", file=sys.stderr); return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
