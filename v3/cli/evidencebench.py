"""`yuclaw evidencebench score <predictions.json> <model-name> --items <items.jsonl>` (7.0.1; stdlib-only).

Exit codes: 0 scored · 2 usage / missing file · 3 identity or rubric contract violation (controlled, no score emitted).
Identity contract: the items file's sha256 is computed and bound into the result; when `--expect-items-sha256`
(or a sidecar meta.json with `item_set_hash`/`items_sha256` next to the items file) is present, a mismatch is a
refusal. `--rubric v1` reproduces the released rule exactly; `--rubric v2` is the candidate structured rule and
is labelled as such in every result."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v3.bench import evidencebench as B


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw evidencebench", description="Score EvidenceBench predictions against a supplied item set (stdlib-only).")
    s = p.add_subparsers(dest="cmd", required=True)
    sc = s.add_parser("score", help="score predictions: item_id -> answer")
    sc.add_argument("predictions"); sc.add_argument("model_name"); sc.add_argument("--items", required=True, help="items.jsonl to score against (read exactly as given)")
    sc.add_argument("--rubric", choices=list(B.RUBRICS), default="v1"); sc.add_argument("--expect-items-sha256", help="refuse unless the items file has this sha256")
    sc.add_argument("--meta", help="meta.json carrying item_set_hash / items_sha256 (default: <items dir>/meta.json when present)"); sc.add_argument("--out", help="write the result JSON here")
    a = p.parse_args(argv)
    if a.cmd == "score":
        items_path = Path(a.items)
        if not items_path.is_file():
            print(f"[evidencebench] missing items file: {items_path.name}", file=sys.stderr); return 2
        if not Path(a.predictions).is_file():
            print("[evidencebench] missing predictions file", file=sys.stderr); return 2
        try:
            ident = B.items_identity(items_path)
            expect = a.expect_items_sha256
            meta_path = Path(a.meta) if a.meta else items_path.parent / "meta.json"
            if not expect and meta_path.is_file():
                try:
                    m = json.loads(meta_path.read_text()); expect = m.get("items_sha256") or m.get("item_set_hash")
                except ValueError:
                    raise B.BenchError("meta.json malformed")
            if expect and expect != ident["items_sha256"]:
                raise B.BenchError(f"item-set identity mismatch: file sha256 {ident['items_sha256'][:16]}… != expected {str(expect)[:16]}…")
            items = B.load_items(items_path); preds = B.load_predictions(a.predictions)
            res = B.score(items, preds, rubric=a.rubric, label=a.model_name, items_sha256=ident["items_sha256"])
        except B.BenchError as exc:
            print(f"[evidencebench] REFUSED: {exc}", file=sys.stderr); return 3
        txt = json.dumps(res, indent=1)
        if a.out:
            Path(a.out).write_text(txt + "\n")
        print(txt); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
