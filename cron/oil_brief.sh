#!/usr/bin/env bash
# YUCLAW: nightly LLM oil brief — once per day, separate from hourly price refresh.
# Cron: 0 23 * * *  (23:00 MDT daily)
# The LLM brief is slow (~21s for 50 tokens measured; longer briefs take 60-120s)
# and not user-facing on the dashboard; the hourly cron/oil_engine.sh skips it
# for latency. This wrapper runs the full pipeline once a day so brief.txt
# stays roughly fresh. Local LLM is Llama 3.1 70B via the 'nemotron-3-super-local'
# Ollama tag.

LOG=/tmp/yuclaw_oil.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

cd "$YUCLAW_HOME"
echo "[$(date -u +%FT%TZ)] oil_brief start (with LLM)" >> "$LOG"

# 600s cap — the local LLM can take 1-2 min on this hardware
timeout 600 "$PYTHON" -m yuclaw.oil.oil_engine >> "$LOG" 2>&1

echo "[$(date -u +%FT%TZ)] oil_brief done" >> "$LOG"
