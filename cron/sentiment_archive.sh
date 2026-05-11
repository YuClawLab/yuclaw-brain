#!/usr/bin/env bash
# YUCLAW: re-score top news headlines with Nemotron via Ollama, archive snapshot.
# Cron: 0 2,6,10,14,18,22 * * *  (every 4h MDT ≈ 0/4/8/12/16/20 UTC during DST)

LOG=/tmp/yuclaw_sentiment.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
[[ -f "$HOME/.yuclaw_env" ]] && source "$HOME/.yuclaw_env"

if ! curl -fs --max-time 5 http://localhost:11434/api/version >/dev/null 2>&1; then
    echo "[$(date -u +%FT%TZ)] sentiment_archive: Ollama down, skipping" >> "$LOG"
    exit 0
fi

mkdir -p "$YUCLAW_HOME/output/sentiment"
echo "[$(date -u +%FT%TZ)] sentiment_archive start" >> "$LOG"

"$PYTHON" - >> "$LOG" 2>&1 <<'PY'
import json, os, re, urllib.request
from datetime import datetime, timezone

state_path = "/home/zhangd2/Yuclaw/docs/data/dashboard_state.json"
out_dir = "/home/zhangd2/yuclaw/output/sentiment"

try:
    state = json.load(open(state_path))
except Exception as e:
    print(f"FAIL read state: {e}")
    raise SystemExit(1)

news = (state.get("news") or [])[:10]
if not news:
    print("WARN no news items in dashboard_state.json")
    raise SystemExit(0)

def score(headline, ticker):
    body = json.dumps({
        "model": "nemotron-3-super-local:latest",
        "prompt": (f"Score the financial sentiment of this headline for {ticker} as a number "
                   f"from -1.0 (very bearish) to +1.0 (very bullish). Reply ONLY with the number.\n\n"
                   f"Headline: {headline}\n\nScore:"),
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 16},
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    raw = (d.get("response") or "").strip()
    m = re.search(r"-?\d+(\.\d+)?", raw)
    return float(m.group(0)) if m else None

results = []
for item in news:
    t = item.get("ticker", "")
    h = item.get("latest_headline", "")
    if not h:
        continue
    s = None
    try:
        s = score(h, t)
    except Exception as e:
        print(f"score fail {t}: {e}")
    results.append({
        "ticker": t,
        "headline": h,
        "nemotron_score": s,
        "prior_sentiment": item.get("sentiment"),
        "prior_score": item.get("score"),
    })

stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
out_path = os.path.join(out_dir, f"{stamp}.json")
with open(out_path, "w") as f:
    json.dump({"timestamp": datetime.now(timezone.utc).isoformat(),
               "n_items": len(results), "items": results}, f, indent=2)
print(f"OK sentiment: {len(results)} items, saved {out_path}")
PY

echo "[$(date -u +%FT%TZ)] sentiment_archive done" >> "$LOG"
