#!/bin/bash
# Traffic archiver (2026-08-06) — GitHub's traffic API serves only a rolling
# 14-day window; anything not captured daily is gone forever. Pulls the four
# traffic endpoints for YuClawLab/yuclaw-brain, stores the full raw responses
# under internal/metrics/raw/ (true append-only record), and folds the per-day
# clones/views rows into internal/metrics/traffic.jsonl: one line per
# (kind, day), deduped, MAX count/uniques winning on overlap (GitHub revises
# recent days upward as they fill in — never let a smaller early read clobber
# a later fuller one). popular/paths and popular/referrers are day-stamped
# snapshots: latest capture of the day wins.
#
# internal/ is gitignored — this data never reaches the public repo.
# Non-fatal by design when wired into the daily chain: a GitHub hiccup must
# not block the page pipeline.
set -u
REPO_DIR="/home/zhangd2/yuclaw"
GH_REPO="YuClawLab/yuclaw-brain"
OUT_DIR="$REPO_DIR/internal/metrics"
RAW_DIR="$OUT_DIR/raw"
mkdir -p "$RAW_DIR"

STAMP=$(date -u +%Y-%m-%dT%H%M%SZ)
ok=1
for ep in clones views popular/paths popular/referrers; do
    name=${ep//\//_}
    if ! /home/zhangd2/bin/gh api "repos/$GH_REPO/traffic/$ep" \
            > "$RAW_DIR/${STAMP}_${name}.json" 2>>"$RAW_DIR/errors.log"; then
        echo "[traffic-archive] FETCH FAILED: $ep (see raw/errors.log)"
        rm -f "$RAW_DIR/${STAMP}_${name}.json"
        ok=0
    fi
done

/usr/bin/python3 - "$RAW_DIR" "$OUT_DIR/traffic.jsonl" "$STAMP" <<'PY'
import json, sys
from pathlib import Path

raw_dir, out_path, stamp = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
cap_day = stamp[:10]

rows = {}          # (kind, day) -> row
if out_path.exists():
    for line in out_path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[(r["kind"], r["day"])] = r

def fold_daily(kind, payload):
    for e in payload.get(kind, []):
        day = e["timestamp"][:10]
        prev = rows.get((kind, day))
        if prev is None:
            rows[(kind, day)] = {"kind": kind, "day": day,
                                 "count": e["count"], "uniques": e["uniques"]}
        else:   # max wins on overlap
            prev["count"] = max(prev["count"], e["count"])
            prev["uniques"] = max(prev["uniques"], e["uniques"])

for name, kind in (("clones", "clones"), ("views", "views")):
    f = raw_dir / f"{stamp}_{name}.json"
    if f.exists():
        fold_daily(kind, json.loads(f.read_text()))

for name, kind in (("popular_paths", "popular_paths"),
                   ("popular_referrers", "popular_referrers")):
    f = raw_dir / f"{stamp}_{name}.json"
    if f.exists():   # latest capture of the day wins for snapshots
        rows[(kind, cap_day)] = {"kind": kind, "day": cap_day,
                                 "items": json.loads(f.read_text())}

out_path.write_text("".join(
    json.dumps(rows[k], sort_keys=True) + "\n"
    for k in sorted(rows)))

daily = [r for r in rows.values() if r["kind"] in ("clones", "views")]
if daily:
    days = sorted({r["day"] for r in daily})
    tot = {k: sum(r["count"] for r in daily if r["kind"] == k)
           for k in ("clones", "views")}
    uni = {k: sum(r["uniques"] for r in daily if r["kind"] == k)
           for k in ("clones", "views")}
    # Σdaily-uniques ≠ GitHub's window-deduped uniques (same visitor on two
    # days counts twice here) — labeled honestly; the raw responses carry
    # GitHub's own deduped window totals.
    print(f"[traffic-archive] {days[0]}..{days[-1]} · "
          f"clones {tot['clones']} (Σdaily-uniques {uni['clones']}) · "
          f"views {tot['views']} (Σdaily-uniques {uni['views']}) · "
          f"{len(days)} days on file")
else:
    print("[traffic-archive] no daily rows on file yet")
PY

[ "$ok" = 1 ] || exit 1
exit 0
