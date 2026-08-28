#!/bin/bash
# U350 Phase-A shadow daily pass. Shadow data is never a forward record;
# the drain step yields to ALL U79 work (gpu-lock + canonical backlog
# checks live inside shadow_ops drain). Ordering: prices -> ingest ->
# drain (bounded GPU) -> score -> guards -> calendar -> phase health ->
# maturity report. Every step runs every day regardless of earlier
# failures (shadow freshness may degrade, U79 never), and the unit's exit
# status is the TRUTH: 0 iff every step returned 0, else the worst
# (highest) nonzero rc — Order 2026-08-28C FIX 2b. A label-anomaly guard
# trip therefore makes the unit fail; that is correct, not a regression.
#
# Isolation note (FIX 1e): the shadow's v5-persistence steps
# (yuclaw_v5.swarm_inputs / event_type_corrected, reached from the reused
# canonical worker) fail closed by privilege — u350_writer holds NO
# yuclaw_v5 grants. This is intentional isolation; do not grant.
#
# --selftest-fail: SYNTHETIC ONLY. Runs stub steps PASS -> FAIL(rc=17) ->
# PASS, touches no database, no drain, no guards, no report; proves the
# step after a failure still executes and the final exit is nonzero (17).
set -uo pipefail
cd /home/zhangd2/yuclaw || exit 1
LOG=/home/zhangd2/yuclaw/services/u350_shadow.log
WORST=0
track() {  # $1=name $2=rc
  echo "[u350-shadow] step '$1' rc=$2"
  if [ "$2" -ne 0 ] && [ "$2" -gt "$WORST" ]; then WORST=$2; fi
}
run_step() {  # $1=name, rest=command; set -e-safe capture of rc
  local name=$1; shift
  local rc
  if "$@"; then rc=0; else rc=$?; fi
  track "$name" "$rc"
}
selftest() {
  echo "=== u350 shadow SELFTEST-FAIL (synthetic; no real steps) $(date '+%Y-%m-%dT%H:%M:%S%z') ==="
  run_step "selftest-pass-1" /bin/true
  run_step "selftest-fail"   /bin/sh -c 'exit 17'
  run_step "selftest-pass-2" /bin/sh -c 'echo "[selftest] step after failure executed"'
  echo "[u350-shadow] SELFTEST final exit=$WORST (expect 17)"
  exit "$WORST"
}
if [ "${1:-}" = "--selftest-fail" ]; then
  selftest 2>&1 | tee -a "$LOG"
  exit "${PIPESTATUS[0]}"
fi
{
  echo "=== u350 shadow pass $(date '+%Y-%m-%dT%H:%M:%S%z') ==="
  for step in prices ingest drain score guards calendar; do
    run_step "$step" /usr/bin/python3 v3/u350/shadow_ops.py "$step"
  done
  # Phase-A verification harness: health line + phase_a_log.jsonl record
  run_step "phase-health" /usr/bin/python3 tools/u350_phase_health.py
  # FIX 4: maturity report regenerated daily as the final tracked step
  run_step "phase-report" /usr/bin/python3 tools/u350_phase_report.py
  echo "[u350-shadow] pass complete: worst rc=$WORST (0 = all steps clean)"
} >> "$LOG" 2>&1
exit "$WORST"
