"""`yuclaw packet build <dir>` / `yuclaw packet verify <dir>` — offline verification packet (v7).
Exit 0 = built / SUCCESS; 1 = MISMATCH; 2 = usage; 3 = UNSUPPORTED."""
from __future__ import annotations

import argparse
import json
import sys

from v3.receipts import packet


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw packet", description="Offline verification packet: build from the public artifacts on disk, or verify exact bytes + replay the frozen bundle. Research only — not investment advice.")
    s = p.add_subparsers(dest="cmd", required=True)
    b = s.add_parser("build"); b.add_argument("out_dir")
    v = s.add_parser("verify"); v.add_argument("packet_dir"); v.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if a.cmd == "build":
        man = packet.build(a.out_dir)
        print(f"[packet] built {a.out_dir}: {sum(1 for f in man['files'] if f['status'] == 'INCLUDED')} files, source {man['source']['head'][:12]}; verify with: yuclaw packet verify {a.out_dir}")
        return 0
    res = packet.verify(a.packet_dir)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"[packet] {res['result']} — manifest {str(res.get('manifest_digest'))[:16]}…; " + (f"first discrepancy: {res['first_discrepancy']}" if res["first_discrepancy"] else res.get("meaning", "")))
    return {"SUCCESS": 0, "MISMATCH": 1, "UNSUPPORTED": 3}[res["result"]]


if __name__ == "__main__":
    sys.exit(main())
