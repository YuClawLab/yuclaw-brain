#!/usr/bin/env bash
# YUCLAW: refresh oil intelligence (WTI/Brent prices + EIA inventory + brief).
# Cron: 0 * * * *  (hourly at :00 — oil futures trade ~24/7 so hourly is fine)
# Output: ~/yuclaw/output/oil/YYYY-MM-DD_brief.json (today's file rewritten each hour).

LOG=/tmp/yuclaw_oil.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
# set -a so KEY=value lines in ~/.yuclaw_env auto-export to the Python subprocess.
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

cd "$YUCLAW_HOME"
echo "[$(date -u +%FT%TZ)] oil_engine start" >> "$LOG"

# 180s cap: prices fetch is fast (~3s) but Nemotron brief can take up to 2 min
timeout 180 "$PYTHON" -m yuclaw.oil.oil_engine >> "$LOG" 2>&1

echo "[$(date -u +%FT%TZ)] oil_engine done" >> "$LOG"
