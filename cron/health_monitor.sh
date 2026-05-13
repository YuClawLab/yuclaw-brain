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

# 1. dashboard_state.json modified within last 60 min
if [[ -f "$DASHBOARD_STATE" ]]; then
    mod_epoch=$(stat -c %Y "$DASHBOARD_STATE" 2>/dev/null || echo 0)
    age_min=$(( (now_epoch - mod_epoch) / 60 ))
    if (( age_min <= 60 )); then
        status+=("dashboard:OK(${age_min}m)")
    else
        status+=("dashboard:STALE(${age_min}m)")
        problems+=("dashboard_state.json stale: ${age_min}m old (>60m)")
    fi
else
    status+=("dashboard:MISSING")
    problems+=("dashboard_state.json missing at ${DASHBOARD_STATE}")
fi

# 2. Ollama responding on 11434
if curl -fs --max-time 5 http://localhost:11434/api/version >/dev/null 2>&1; then
    status+=("ollama:OK")
else
    status+=("ollama:DOWN")
    problems+=("Ollama not responding on :11434")
fi

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

# 4. No zombie processes
zombies=$(ps -eo stat= 2>/dev/null | awk '/^Z/' | wc -l || echo 0)
if (( zombies == 0 )); then
    status+=("zombies:0")
else
    status+=("zombies:${zombies}")
    problems+=("${zombies} zombie process(es)")
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
