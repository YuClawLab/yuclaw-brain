#!/usr/bin/env bash
# YUCLAW: every-30-min health check. One-line status to log; alert file if anything fails.
# Cron: */30 * * * *

LOG=/tmp/yuclaw_health.log
ALERT=/tmp/yuclaw_ALERT.txt
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

DASHBOARD_STATE=/home/zhangd2/yuclaw/docs/data/dashboard_state.json
# set -a so KEY=value lines in ~/.yuclaw_env auto-export to any subprocess we spawn.
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

now_epoch=$(date +%s)
status=()
problems=()

# 1. price_history freshness — the real signal-input freshness since the v4.2
# C1-C7 migration (signals now compute from price_history via build_live_state;
# dashboard_state.json is retired as a signal input, so its mtime is no longer
# a meaningful health signal). Allow up to 4 days to cover weekends/holidays.
ph_max=$(psql -d yuclaw_events -tAc "SELECT max(trade_date) FROM price_history" 2>/dev/null | tr -d '[:space:]')
if [[ -n "$ph_max" ]]; then
    ph_epoch=$(date -d "$ph_max" +%s 2>/dev/null || echo 0)
    age_days=$(( (now_epoch - ph_epoch) / 86400 ))
    if (( age_days <= 4 )); then
        status+=("prices:OK(${ph_max})")
    else
        status+=("prices:STALE(${age_days}d)")
        problems+=("price_history stale: latest ${ph_max} (${age_days}d, >4d) — check cron/price_history_daily.sh")
    fi
else
    status+=("prices:MISSING")
    problems+=("price_history empty/unreadable")
fi

# 2. Ollama responding on 11434
if curl -fs --max-time 5 http://localhost:11434/api/version >/dev/null 2>&1; then
    status+=("ollama:OK")
else
    status+=("ollama:DOWN")
    problems+=("Ollama not responding on :11434")
fi

# 2b. EDGAR ingestion liveness — the silent 20-day outage detector.
# Primary signal is the poller's SWEEP HEARTBEAT (it logs every 5-min sweep even
# with 0 new filings), NOT max(events_raw.fetched_at): the latter goes stale on
# quiet weekends and would false-alarm. A stale sweep log => poller down/hung.
POLLER_LOG=/tmp/yuclaw_edgar_poller.log
if [[ -f "$POLLER_LOG" ]]; then
    sweep_epoch=$(stat -c %Y "$POLLER_LOG" 2>/dev/null || echo 0)
    sweep_age=$(( (now_epoch - sweep_epoch) / 60 ))   # minutes since last sweep line
    if (( sweep_age <= 20 )); then
        status+=("ingest:OK(${sweep_age}m)")
    else
        status+=("ingest:STALE(${sweep_age}m)")
        problems+=("EDGAR poller not sweeping for ${sweep_age}m (>20m) — likely down/hung. Check: systemctl --user status yuclaw-edgar-poller")
    fi
else
    status+=("ingest:NO-HEARTBEAT")
    problems+=("EDGAR poller sweep log ${POLLER_LOG} missing — poller never started? Check: systemctl --user status yuclaw-edgar-poller")
fi
# Secondary (visibility only, no alarm — weekends legitimately have no new filings):
raw_max=$(psql -d yuclaw_events -tAc "SELECT max(fetched_at)::date FROM events_raw" 2>/dev/null | tr -d '[:space:]')
[[ -n "$raw_max" ]] && status+=("raw_last:${raw_max}")

# 3. Disk usage < 90% on /
disk_pct=$(df -P / 2>/dev/null | awk 'NR==2 {gsub("%",""); print $5}')
if [[ -n "${disk_pct:-}" ]]; then
    if (( disk_pct < 90 )); then
        status+=("disk:OK(${disk_pct}%)")
    else
        status+=("disk:HIGH(${disk_pct}%)")
        problems+=("Disk usage on / is ${disk_pct}% (>=90%)")
    fi
else
    status+=("disk:UNKNOWN")
fi

# 4. Zombie processes — alert only above noise floor (small benign counts are common)
zombies=$(ps -eo stat= 2>/dev/null | awk '/^Z/' | wc -l || echo 0)
status+=("zombies:${zombies}")
if (( zombies > 5 )); then
    problems+=("${zombies} zombie process(es) (>5)")
fi

ts=$(date -u +%FT%TZ)
line="[$ts] $(IFS=' '; echo "${status[*]}")"
echo "$line" >> "$LOG"
echo "$line"

if (( ${#problems[@]} > 0 )); then
    {
        echo "[$ts] YUCLAW HEALTH ALERT"
        for p in "${problems[@]}"; do echo "  - $p"; done
    } > "$ALERT"
    echo "ALERT written to $ALERT"
else
    rm -f "$ALERT"
fi
