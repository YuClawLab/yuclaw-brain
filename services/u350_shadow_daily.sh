#!/bin/bash
# U350 Phase-A shadow daily pass. Shadow data is never a forward record;
# the drain step yields to ALL U79 work (gpu-lock + canonical backlog
# checks live inside shadow_ops drain). Ordering: prices -> ingest ->
# drain (bounded GPU) -> score -> guards -> calendar. A step failure is
# logged and the pass continues — shadow freshness may degrade, U79 never.
set -uo pipefail
cd /home/zhangd2/yuclaw || exit 1
LOG=/home/zhangd2/yuclaw/services/u350_shadow.log
{
  echo "=== u350 shadow pass $(date '+%Y-%m-%dT%H:%M:%S%z') ==="
  for step in prices ingest drain score guards calendar; do
    /usr/bin/python3 v3/u350/shadow_ops.py "$step" || \
      echo "[u350-shadow] step '$step' rc=$? (logged, continuing)"
  done
} >> "$LOG" 2>&1
