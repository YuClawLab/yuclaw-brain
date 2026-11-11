#!/usr/bin/env bash
# One logged, bounded run, including upstream failures before page generation.
set -Eeuo pipefail
cd /home/zhangd2/yuclaw
exec >> /tmp/yuclaw_pipeline.log 2>&1
exec 8>/tmp/yuclaw_public_pipeline.lock
flock -n 8 || { echo '[public-pipeline] already running'; exit 75; }
stage=preflight
trap 'rc=$?; if ((rc != 0)); then printf "[public-pipeline] FAILED stage=%s rc=%s at=%s\n" "$stage" "$rc" "$(date -u +%FT%TZ)" | tee /tmp/yuclaw_pipeline_failed.marker; fi' EXIT
echo "[public-pipeline] START $(date -u +%FT%TZ)"
[[ $(git branch --show-current) == main ]] || { echo 'production checkout must be main'; exit 81; }
run_stage() { stage=$1; shift; echo "[public-pipeline] stage=$stage"; timeout --signal=TERM --kill-after=30s 3600 "$@"; }
run_stage signal-health /usr/bin/python3 -m v3.signal.healthcheck
run_stage snapshots /usr/bin/python3 -m v3.signal.snapshot_writer
run_stage outcomes /usr/bin/python3 -m v3.track.outcome_updater
run_stage radar /usr/bin/python3 -m v3.radar.run
run_stage ledger /usr/bin/python3 -m v3.proof.ledger
run_stage publish /bin/bash cron/refresh_v3_pages.sh
rm -f /tmp/yuclaw_pipeline_failed.marker
echo "[public-pipeline] COMPLETE $(date -u +%FT%TZ)"
