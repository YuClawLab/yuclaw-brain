#!/usr/bin/env python3
"""
Statistic audit-diff (review-completion Part C2). Records the day's headline
public statistics and diffs them against the previous run with cause tags —
the public "what changed and why" section renders from this artifact.
Cause tags are mechanical: sample-size change => accrual (new events /
window completion); protocol change => method version; value-only change
=> recomputation on refreshed inputs. Runs daily in the chain (non-fatal).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

STATE = _REPO / "internal" / "audit" / "headline_state.json"
OUT = _REPO / "output" / "oie" / "audit_diff.json"


def _get(path, *keys, default=None):
    p = _REPO / "output" / "oie" / path
    if not p.exists():
        return default, default
    d = json.loads(p.read_text())
    pid = d.get("protocol_id")
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
        if d is None:
            return None, pid
    return d, pid


def headline() -> dict:
    out = {}
    v, pid = _get("smh_lens_run.json", "estimands", "backfill", "capped", "mean_pct")
    n, _ = _get("smh_lens_run.json", "estimands", "n_backfill")
    out["SMH E4 capped CAR +20d (backfill)"] = {"value": v, "n": n, "protocol": pid}
    v, pid = _get("xlk_lens_run.json", "estimands", "capped", "mean_pct")
    n, _ = _get("xlk_lens_run.json", "n_events_backfill")
    out["XLK E4 capped CAR +20d (backfill)"] = {"value": v, "n": n, "protocol": pid}
    v, pid = _get("lab_clustered_run.json", "results", "5", "spread_mean")
    n, _ = _get("lab_clustered_run.json", "results", "5", "n_obs")
    out["Lab clustered spread k=5"] = {"value": v, "n": n, "protocol": pid}
    v, pid = _get("baselines_run.json", "primary", "diff")
    n, _ = _get("baselines_run.json", "window", "n_dates")
    out["Composite minus top baseline IC k=5"] = {"value": v, "n": n, "protocol": pid}
    v, pid = _get("label_calibration.json", "primary", "consistency_k20")
    n, _ = _get("label_calibration.json", "primary", "n")
    out["Directional label consistency k=20"] = {"value": v, "n": n, "protocol": pid}
    v, pid = _get("neutralized_ic.json", "primary", "joint_ic_k5")
    n, _ = _get("neutralized_ic.json", "window", "n_dates")
    out["Composite jointly-neutralized IC k=5"] = {"value": v, "n": n, "protocol": pid}
    v, pid = _get("matched_control.json", "adjusted_E4", "mean_pct")
    n, _ = _get("matched_control.json", "n_pairs")
    out["Matched-control-adjusted E4 +20d"] = {"value": v, "n": n, "protocol": pid}
    return out


def main() -> int:
    cur = headline()
    prev = json.loads(STATE.read_text()) if STATE.exists() else {}
    prev_h = prev.get("headline", {})
    changes = []
    for name, c in cur.items():
        p = prev_h.get(name)
        if p is None:
            changes.append({"stat": name, "change": "first record",
                            "cause": "statistic newly tracked"})
            continue
        if p.get("protocol") != c.get("protocol"):
            changes.append({"stat": name,
                            "change": f"{p.get('value')} -> {c.get('value')}",
                            "cause": f"method version ({p.get('protocol')} -> "
                                     f"{c.get('protocol')})"})
        elif p.get("n") != c.get("n"):
            changes.append({"stat": name,
                            "change": f"{p.get('value')} -> {c.get('value')} "
                                      f"(n {p.get('n')} -> {c.get('n')})",
                            "cause": "accrual: new events / window completion"})
        elif p.get("value") != c.get("value"):
            changes.append({"stat": name,
                            "change": f"{p.get('value')} -> {c.get('value')}",
                            "cause": "recomputation on refreshed inputs"})
    payload = {"as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "previous_as_of": prev.get("as_of"),
               "headline": cur, "changes": changes}
    OUT.write_text(json.dumps(payload, indent=1))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"as_of": payload["as_of"], "headline": cur}))
    print(f"[audit-diff] {len(changes)} change(s) recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
