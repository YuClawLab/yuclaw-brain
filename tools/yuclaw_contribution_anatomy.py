#!/usr/bin/env python3
"""Phase-5 contribution anatomy command (v7): python3 tools/yuclaw_contribution_anatomy.py WHY.json --anatomy INPUT.json [--json]
INPUT.json = {"weights": {...}, "confidence": {...}, "gates": {"c2": "confidence-gated"}, "expected_contributions": {...}?}
Without an anatomy input the published why-JSON cannot be reconciled (weights/confidence are not published): the tool says so."""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v3.anatomy.contribution import AnatomyError, decompose, reconcile  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("why"); ap.add_argument("--anatomy"); ap.add_argument("--json", action="store_true"); a = ap.parse_args(argv)
    why = json.loads(Path(a.why).read_text())
    if not a.anatomy:
        print(json.dumps({"verdict": "NOT_POSSIBLE", "reason": "weights and confidence are not published in the why-JSON; supply --anatomy", "components": sorted(why.get("components", {}))}, indent=1)); return 3
    try:
        an = decompose(why, json.loads(Path(a.anatomy).read_text())); an["expected_contributions"] = json.loads(Path(a.anatomy).read_text()).get("expected_contributions")
        rec = reconcile(an)
    except AnatomyError as exc:
        print(f"[anatomy] REJECTED: {exc}", file=sys.stderr); return 1
    out = {**an, "reconciliation": rec}
    print(json.dumps(out, indent=1) if a.json else f"[anatomy] {rec['verdict']} — Σ={an['sum_of_contributions']} vs composite {an['composite_published']} (diff {rec['difference']}, tol {rec['tolerance']:.2e}); mismatches {len(rec['mismatches'])}")
    return 0 if rec["reconciled"] else 1


if __name__ == "__main__":
    sys.exit(main())
