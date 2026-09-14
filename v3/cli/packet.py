"""`yuclaw packet build <dir>` / `yuclaw packet verify <dir>` — offline verification packet (v7).
Exit 0 = built / SUCCESS; 1 = MISMATCH; 2 = usage; 3 = UNSUPPORTED (malformed packet, unsupported format,
missing checkout, environment error). With `--trusted-manifest`, exit 1 also when the packet's bytes differ
from the independently supplied identity (integrity SUCCESS is reported separately from provenance)."""
from __future__ import annotations

import argparse
import json
import sys

from v3.receipts import packet


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw packet", description="Offline verification packet: build from the public artifacts on disk, or verify exact bytes + replay the frozen bundle. Research only — not investment advice.")
    s = p.add_subparsers(dest="cmd", required=True)
    b = s.add_parser("build"); b.add_argument("out_dir"); b.add_argument("--source", help="YUCLAW checkout holding the public artifacts (default: the package's checkout or the current directory)")
    v = s.add_parser("verify"); v.add_argument("packet_dir"); v.add_argument("--json", action="store_true")
    v.add_argument("--trusted-manifest", help="INDEPENDENTLY obtained identity (packet-manifest shape or {path: {sha256, size_bytes}}); without it the packet's origin is reported UNVERIFIED")
    a = p.parse_args(argv)
    if a.cmd == "build":
        try:
            man = packet.build(a.out_dir, repo=a.source)
        except ValueError as exc:
            print(f"[packet] {exc}", file=sys.stderr); return 3
        except OSError as exc:
            print(f"[packet] cannot build: {exc.__class__.__name__}", file=sys.stderr); return 3
        print(f"[packet] built {a.out_dir}: {sum(1 for f in man['files'] if f['status'] == 'INCLUDED')} files, source {man['source']['head'][:12]}; verify with: yuclaw packet verify {a.out_dir}")
        return 0
    trusted = None
    if a.trusted_manifest:
        try:
            trusted = packet.load_trusted(a.trusted_manifest)
        except (OSError, ValueError) as exc:
            print(f"[packet] trusted identity unusable: {exc if isinstance(exc, ValueError) else exc.__class__.__name__}", file=sys.stderr); return 3
    res = packet.verify(a.packet_dir, trusted=trusted)
    prov = res.get("provenance", {})
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"[packet] {res['result']} — manifest {str(res.get('manifest_digest'))[:16]}…; " + (f"first discrepancy: {res['first_discrepancy']}" if res["first_discrepancy"] else res.get("meaning", ""))
              + f" | provenance: official artifact equality {prov.get('official_artifact_equality')}")
    rc = {"SUCCESS": 0, "MISMATCH": 1, "UNSUPPORTED": 3}[res["result"]]
    if rc == 0 and trusted is not None and prov.get("official_artifact_equality") != "EQUAL":
        print(f"[packet] provenance: packet bytes differ from / are not covered by the trusted identity ({prov.get('official_artifact_equality')})", file=sys.stderr)
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
