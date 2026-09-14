"""`yuclaw challenge` — local structured challenges bound to artifact + claim identifiers (v7).
Exit 0 ok; 1 contract/authority/input error; 2 usage. CONFIRMED / REFUTED / RESOLVED need a reviewer
appointment (`--role` + credential from --token-file / --token-fd / no-echo prompt); RESOLVED also needs the
revised artifact's actual bytes (`--revised-path`) and a structured `--verification-json`."""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
from v3.receipts import credentials
from v3.receipts.challenge import ChallengeStore, TRUSTED_DISPOSITIONS
from v3.receipts.contracts import ContractError


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw challenge"); p.add_argument("--store", required=True); p.add_argument("--synthetic", action="store_true")
    s = p.add_subparsers(dest="cmd", required=True)
    c = s.add_parser("create"); c.add_argument("challenge_id"); c.add_argument("--artifact-type", required=True); c.add_argument("--sha256", required=True); c.add_argument("--size-bytes", type=int, required=True)
    c.add_argument("--claim-id", required=True); c.add_argument("--expected", required=True); c.add_argument("--observed", required=True)
    d = s.add_parser("dispose"); d.add_argument("challenge_id"); d.add_argument("disposition"); d.add_argument("--role", help="reviewer role (required for CONFIRMED/REFUTED/RESOLVED)")
    credentials.add_token_arguments(d)
    d.add_argument("--revised-type"); d.add_argument("--revised-sha256"); d.add_argument("--revised-size-bytes", type=int)
    d.add_argument("--revised-path", help="actual bytes of the revised artifact (must equal the claimed revised binding)"); d.add_argument("--allowed-root", action="append", default=[])
    d.add_argument("--verification-json", help='structured test result: {"method": "packet-verify|replay-lab|receipt", "result": "SUCCESS", "reference": "<sha256>"}'); d.add_argument("--reason", default="")
    s.add_parser("list"); h = s.add_parser("history"); h.add_argument("challenge_id")
    a = p.parse_args(argv); cs = ChallengeStore(a.store)
    try:
        if a.cmd == "create":
            print(json.dumps(cs.create(a.challenge_id, artifact={"artifact_type": a.artifact_type, "sha256": a.sha256, "size_bytes": a.size_bytes}, claim_id=a.claim_id, expected=a.expected, observed=a.observed, synthetic=a.synthetic), indent=1)); return 0
        if a.cmd == "dispose":
            token = credentials.read_token(a) if a.disposition in TRUSTED_DISPOSITIONS else None
            ra = {"artifact_type": a.revised_type, "sha256": a.revised_sha256, "size_bytes": a.revised_size_bytes} if a.revised_sha256 else None
            ver = None
            if a.verification_json is not None:
                try:
                    ver = json.loads(a.verification_json)
                except ValueError:
                    raise ContractError("--verification-json: malformed JSON") from None
            try:
                rec = cs.dispose(a.challenge_id, a.disposition, reviewer_role=a.role, token=token, revised_artifact=ra, revised_path=a.revised_path,
                                 allowed_roots=a.allowed_root or [str(Path.cwd())], verification=ver, reason=a.reason)
            except OSError as exc:
                raise ContractError(f"revised artifact path unreadable ({exc.__class__.__name__})") from None
            print(json.dumps(rec, indent=1)); return 0
        if a.cmd == "list":
            print(json.dumps(cs.public_view(synthetic=a.synthetic), indent=1)); return 0
        if a.cmd == "history":
            print(json.dumps(cs.history(a.challenge_id), indent=1)); return 0
    except ContractError as exc:
        print(f"[challenge] REJECTED: {exc}", file=sys.stderr); return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
