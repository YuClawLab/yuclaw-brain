"""`yuclaw decision` — document-use receipts bound to an exact packet manifest digest (v7).
Exit 0 ok; 1 contract/input error; 2 usage. Context is private and never exported; recording a use is not
evidence of investment benefit."""
from __future__ import annotations

import argparse, json, sys
from v3.receipts.decision import DecisionStore
from v3.receipts.contracts import ContractError


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw decision"); p.add_argument("--store", required=True); p.add_argument("--synthetic", action="store_true")
    s = p.add_subparsers(dest="cmd", required=True)
    r = s.add_parser("record"); r.add_argument("decision_id"); r.add_argument("decision"); r.add_argument("--packet-manifest-digest", required=True); r.add_argument("--claim-id", required=True); r.add_argument("--export-permitted", action="store_true"); r.add_argument("--context", default="{}")
    s.add_parser("export")
    a = p.parse_args(argv)
    try:
        ds = DecisionStore(a.store)
        if a.cmd == "record":
            try:
                ctx = json.loads(a.context)
            except ValueError:
                raise ContractError("--context: malformed JSON (a JSON object is required)") from None
            print(json.dumps(ds.record(a.decision_id, a.decision, packet_manifest_digest=a.packet_manifest_digest, claim_id=a.claim_id, context=ctx, export_permitted=a.export_permitted, synthetic=a.synthetic), indent=1)); return 0
        if a.cmd == "export":
            print(json.dumps(ds.export(synthetic=a.synthetic), indent=1)); return 0
    except ContractError as exc:
        print(f"[decision] REJECTED: {exc}", file=sys.stderr); return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
