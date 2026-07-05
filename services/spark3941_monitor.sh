#!/bin/sh
# spark-3941 → spark-d89d tailnet watcher (SECOND, tailnet-internal dead-man).
#
# STAGED, NOT YET INSTALLED: spark-d89d has no SSH trust to spark-3941, so
# VinZhang must install this by hand ON spark-3941 (~2 min):
#   1. copy this file there:            mkdir -p ~/bin  &&  (paste) ~/bin/spark_d89d_monitor.sh  &&  chmod +x
#   2. create ~/.yuclaw_alert_env (0600) with two lines:
#        TELEGRAM_BOT_TOKEN=<same bot token as spark-d89d ~/.yuclaw_env>
#        ALERT_CHAT=@yuclaw_signals
#   3. crontab -e, add:
#        */10 * * * * /bin/sh $HOME/bin/spark_d89d_monitor.sh
#
# Behavior: pings spark-d89d over the tailnet every 10 min. On the 3rd
# consecutive failure (~30 min dark) it alerts Telegram, re-alerts every 18th
# tick (~3h) while still dark, and sends a recovery note when the box returns.
# POSIX-clean. State: /tmp/d89d_fail_count. Log: /tmp/d89d_monitor.log

TARGET=100.121.222.47          # spark-d89d tailscale IP
CNT=/tmp/d89d_fail_count
LOG=/tmp/d89d_monitor.log
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

[ -f "$HOME/.yuclaw_alert_env" ] && { set -a; . "$HOME/.yuclaw_alert_env"; set +a; }

send() {
    curl -fsS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        --data-urlencode chat_id="${ALERT_CHAT}" \
        --data-urlencode text="$1" >/dev/null 2>&1
}

n=$(cat "$CNT" 2>/dev/null || echo 0)

if /usr/bin/ping -c1 -W5 "$TARGET" >/dev/null 2>&1; then
    if [ "$n" -ge 3 ]; then
        send "spark-d89d RECOVERED: reachable again from spark-3941 (was dark for $((n * 10)) min)."
        echo "[$TS] recovered after $n failures" >> "$LOG"
    fi
    rm -f "$CNT"
    exit 0
fi

n=$((n + 1))
echo "$n" > "$CNT"
echo "[$TS] ping fail #$n" >> "$LOG"

if [ "$n" -eq 3 ] || [ $((n % 18)) -eq 0 ]; then
    send "SPARK-D89D DOWN? Unreachable from spark-3941 over the tailnet for $((n * 10)) min ($n consecutive ping failures). Jun-26-class outage — if the off-box heartbeat also fired, power-cycle the box."
fi
