#!/usr/bin/env bash
# YUCLAW: refresh oil prices + EIA inventory (fast path, no LLM brief).
# Cron: 0 * * * *  (hourly at :00 — oil futures trade ~24/7 so hourly is fine)
# Output: ~/yuclaw/output/oil/YYYY-MM-DD_brief.json (today's file rewritten each hour;
#         brief field preserved from the most recent nightly cron/oil_brief.sh run).

LOG=/tmp/yuclaw_oil.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
# set -a so KEY=value lines in ~/.yuclaw_env auto-export to the Python subprocess.
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

cd "$YUCLAW_HOME"
echo "[$(date -u +%FT%TZ)] oil_engine start (no brief)" >> "$LOG"

# 30s cap is plenty for prices + EIA (no LLM call). Brief lives in oil_brief.sh.
timeout 30 "$PYTHON" -m yuclaw.oil.oil_engine --no-brief >> "$LOG" 2>&1

echo "[$(date -u +%FT%TZ)] oil_engine done" >> "$LOG"
