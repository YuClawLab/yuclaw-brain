#!/bin/bash
# Daily price_history populate — RESTORED 2026-06-10.
#
# Root cause of the 2026-05-20 feed freeze: the Day-7 daily price_history populate
# was dropped when the v3.0 daily pipeline was consolidated (~2026-05-20, commit
# e5dd546a "Day 11a … consolidated daily pipeline cron"; L75 "supersedes Day 7
# outcome_updater"). outcome_updater only READS price_history, so nothing wrote
# fresh closes and the table froze at 2026-05-20 — making published signals stale.
#
# This restores the daily populate. Rolling 7-day window so a missed run / weekend
# / holiday self-heals on the next run; the writer is idempotent
# (INSERT ... ON CONFLICT (ticker, trade_date) DO UPDATE). Runs 16:45 MDT, ahead of
# the 17:00 v3 daily pipeline so outcome_updater matures outcomes against fresh data.
#
# Crontab line (NOT in repo; added 2026-06-10):
#   45 16 * * 1-5 /bin/bash /home/zhangd2/yuclaw/cron/price_history_daily.sh >> /tmp/yuclaw_price_history.log 2>&1
set -euo pipefail
export PATH=/usr/bin:/usr/local/bin:$PATH
cd /home/zhangd2/yuclaw || exit 1
START=$(date -d '7 days ago' +%Y-%m-%d)
END=$(date +%Y-%m-%d)
echo "[price_history_daily] $(date '+%Y-%m-%dT%H:%M:%S%z') window ${START}..${END}"
/usr/bin/python3 -m v3.track.price_history --start "$START" --end "$END"
