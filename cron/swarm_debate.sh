#!/usr/bin/env bash
# YUCLAW: run Bull/Bear/Oracle swarm debate via the local LLM (Llama 3.1 70B
# served by Ollama as the 'nemotron-3-super-local' tag).
# Cron: 0 23 * * *  (23:00 MDT ≈ 05:00 UTC during DST, 06:00 UTC after DST ends)

LOG=/tmp/yuclaw_swarm.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
# set -a so KEY=value lines in ~/.yuclaw_env auto-export to the Python subprocess.
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

# Skip silently if Ollama is down
if ! curl -fs --max-time 5 http://localhost:11434/api/version >/dev/null 2>&1; then
    echo "[$(date -u +%FT%TZ)] swarm_debate: Ollama down, skipping" >> "$LOG"
    exit 0
fi

mkdir -p "$YUCLAW_HOME/output/swarm"
echo "[$(date -u +%FT%TZ)] swarm_debate start" >> "$LOG"

"$PYTHON" - >> "$LOG" 2>&1 <<'PY'
import os, sys, json
from datetime import datetime, timezone

os.chdir("/home/zhangd2/yuclaw")
sys.path.insert(0, "/home/zhangd2/yuclaw")

from yuclaw.swarm.debate import run_swarm
results = run_swarm(top_n=5)

day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
out_path = f"output/swarm/{day}.json"
with open(out_path, "w") as f:
    json.dump({"date": day, "top_n": 5, "n_results": len(results), "results": results}, f, indent=2)
print(f"OK swarm: {len(results)} signals debated, saved {out_path}")
PY

echo "[$(date -u +%FT%TZ)] swarm_debate done" >> "$LOG"
