#!/bin/bash
# Canada Phase-2 backfill drain loop — detached, box-owned.
#
# Runs the SAME guarded worker the 15-min production timer uses
# (event_worker_guarded.sh re-checks gpu-owner / second-stack / swarm before
# every batch, so this loop coordinates with swarm runs and the prod timer
# exactly like the timer does; FOR UPDATE SKIP LOCKED makes concurrent batches
# safe). Exits when events_raw has no pending rows.
#
# Launch detached (never session-bound):
#   systemd-run --user --unit=yuclaw-canada-drain --collect \
#       /home/zhangd2/yuclaw/services/canada_drain_loop.sh
set -u

LOG=/tmp/yuclaw_drain_loop.log
FAILS=0

echo "[drain-loop] $(date -u +%FT%TZ) started (pid $$)" >> "$LOG"
while :; do
    PENDING=$(psql -Atd yuclaw_events -c \
        "SELECT count(*) FROM events_raw WHERE extraction_status='pending'" 2>>"$LOG")
    if [ -z "${PENDING:-}" ]; then
        echo "[drain-loop] $(date -u +%FT%TZ) psql failed — retry in 60s" >> "$LOG"
        sleep 60
        continue
    fi
    if [ "$PENDING" -eq 0 ]; then
        echo "[drain-loop] $(date -u +%FT%TZ) queue empty — done, exiting" >> "$LOG"
        exit 0
    fi
    echo "[drain-loop] $(date -u +%FT%TZ) pending=$PENDING" >> "$LOG"
    if bash /home/zhangd2/yuclaw/services/event_worker_guarded.sh >> "$LOG" 2>&1; then
        FAILS=0
        sleep 5
    else
        FAILS=$((FAILS + 1))
        echo "[drain-loop] $(date -u +%FT%TZ) worker batch FAILED ($FAILS consecutive)" >> "$LOG"
        if [ "$FAILS" -ge 10 ]; then
            echo "[drain-loop] $(date -u +%FT%TZ) 10 consecutive failures — circuit breaker, exiting 1" >> "$LOG"
            exit 1
        fi
        sleep 60
    fi
done
