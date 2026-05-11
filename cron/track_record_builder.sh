#!/usr/bin/env bash
# YUCLAW: build track record from aggregated_signals.json + current yfinance prices.
# Cron: 30 16 * * *  (16:30 MDT ≈ 22:30 UTC during DST, 23:30 UTC after DST ends)

LOG=/tmp/yuclaw_track.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
[[ -f "$HOME/.yuclaw_env" ]] && source "$HOME/.yuclaw_env"

mkdir -p "$YUCLAW_HOME/output/track_record"
echo "[$(date -u +%FT%TZ)] track_record_builder start" >> "$LOG"

"$PYTHON" - >> "$LOG" 2>&1 <<'PY'
import json, os, glob
from datetime import datetime, timezone

home = "/home/zhangd2/yuclaw"
src = os.path.join(home, "output/aggregated_signals.json")
out_dir = os.path.join(home, "output/track_record")
latest_path = os.path.join(home, "output/track_record_latest.json")

try:
    signals = json.load(open(src))
except Exception as e:
    print(f"FAIL load signals: {e}")
    raise SystemExit(1)

# Auto-increment day N
last_n = 0
for p in glob.glob(os.path.join(out_dir, "day*.json")):
    try:
        n = int(os.path.basename(p).replace("day", "").replace(".json", ""))
        last_n = max(last_n, n)
    except Exception:
        pass
day_n = last_n + 1

try:
    import yfinance as yf
except Exception as e:
    print(f"FAIL yfinance import: {e}")
    raise SystemExit(1)

tickers = sorted({s["ticker"] for s in signals if s.get("ticker") and (s.get("price") or 0) > 0})

bulk = None
if tickers:
    try:
        bulk = yf.download(tickers, period="1d", progress=False, auto_adjust=False, group_by="ticker", threads=True)
    except Exception as e:
        print(f"yf bulk download failed: {e}")
        bulk = None

def current_price(t):
    try:
        if bulk is not None:
            try:
                col = bulk[t]["Close"].dropna()
                if len(col):
                    return float(col.iloc[-1])
            except Exception:
                pass
        h = yf.Ticker(t).history(period="1d")
        return float(h["Close"].dropna().iloc[-1]) if not h.empty else None
    except Exception:
        return None

records = []
for s in signals:
    t = s.get("ticker"); p0 = s.get("price"); sig = s.get("signal", "")
    if not t or not p0 or p0 <= 0:
        continue
    p1 = current_price(t)
    if p1 is None:
        records.append({"ticker": t, "signal": sig, "entry_price": p0,
                        "current_price": None, "outcome_pct": None, "note": "no_quote"})
        continue
    direction = -1 if "SELL" in sig.upper() else 1
    outcome = direction * (p1 - p0) / p0 * 100.0
    records.append({"ticker": t, "signal": sig, "entry_price": round(p0, 4),
                    "current_price": round(p1, 4), "outcome_pct": round(outcome, 3),
                    "score": s.get("score"), "confidence": s.get("confidence")})

priced = [r for r in records if r.get("outcome_pct") is not None]
avg = round(sum(r["outcome_pct"] for r in priced) / len(priced), 3) if priced else None

payload = {
    "day": day_n,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "signal_count": len(records),
    "results": records,
    "summary": {"n_with_quote": len(priced), "avg_outcome_pct": avg},
}

day_path = os.path.join(out_dir, f"day{day_n}.json")
with open(day_path, "w") as f: json.dump(payload, f, indent=2)
with open(latest_path, "w") as f: json.dump(payload, f, indent=2)
print(f"OK day{day_n} written: {len(records)} records ({len(priced)} priced), avg outcome {avg}%")
PY

echo "[$(date -u +%FT%TZ)] track_record_builder done" >> "$LOG"
