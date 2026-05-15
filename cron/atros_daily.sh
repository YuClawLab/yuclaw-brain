#!/usr/bin/env bash
# YUCLAW: one-shot ATROS daemon run (heartbeat + auto_dream once and exit).
# Cron: 15 18 * * *  (18:15 MDT daily, ~15 min after nightly_score_refresh)
# atros_daemon.py's run() is an infinite loop; this wrapper invokes its methods
# directly for cron-friendly one-shot execution.

LOG=/tmp/yuclaw_atros.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
# Use set -a so KEY=value lines in ~/.yuclaw_env are auto-exported
# to subprocesses (Python). Without this, sourcing only sets shell-local vars
# and FINNHUB_KEY / YUCLAW_SUPER_* env vars never reach Python.
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

cd "$YUCLAW_HOME"
echo "[$(date -u +%FT%TZ)] atros_daily start" >> "$LOG"

timeout 300 "$PYTHON" - >> "$LOG" 2>&1 <<'PY'
import sys, os
sys.path.insert(0, '/home/zhangd2/yuclaw')
os.chdir('/home/zhangd2/yuclaw')
from yuclaw.daemon.atros_daemon import YUCLAWDaemon

daemon = YUCLAWDaemon()
alerts = daemon.heartbeat()
print(f"heartbeat: {len(alerts)} new alerts")
daemon.auto_dream()
print("auto_dream complete")
PY

echo "[$(date -u +%FT%TZ)] atros_daily done" >> "$LOG"

# Relay any new ATROS alerts to the Telegram channel. Bot dedupes via its own
# audit log at ~/.yuclaw/telegram_broadcasts.jsonl using a per-alert watermark
# (advances only on SENT/DRY_RUN), so re-runs are idempotent. SIGNAL_CHANGE
# below |delta|=0.20 is filtered out by the bot. TRACK_UPDATE is skipped.
# 60-second timeout prevents a stuck Telegram call from blocking the cron unit.
echo "[$(date -u +%FT%TZ)] telegram alerts relay start" >> "$LOG"
timeout 60 "$PYTHON" -m yuclaw.telegram.broadcast_bot alerts >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] telegram alerts relay done" >> "$LOG"
