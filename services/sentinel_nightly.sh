#!/bin/bash
# YUCLAW Nightly Sentinel launcher — bounded autonomous audit (order of
# 2026-08-04). Mandate limits live in the hash-pinned prompt AND here:
#   - solo-session rule: refuses to start if any Claude session is live
#     (SENTINEL_SUPERVISED=1 bypasses, for operator-present runs only);
#     the interactive `claude` shell wrapper refuses while our lock exists
#   - prompt tamper check: sha256 pin — a changed prompt refuses to run
#   - 25-minute hard wall-clock (timeout + systemd RuntimeMaxSec)
#   - the sentinel session COMMITS but never pushes; this launcher pushes
#     only after verifying no commit touched a forbidden path — violations
#     are hard-reset away and alerted CRITICAL
set -uo pipefail
REPO=/home/zhangd2/yuclaw
LOCK=/tmp/yuclaw_sentinel.lock
PROMPT=$REPO/internal/sentinel/SENTINEL_PROMPT.md
LOG=$REPO/internal/sentinel/log.jsonl
PROMPT_PIN="9dd5e023051108f56466836bcab13c1e76f2728c2f126a7f6e630d92683b264b"
FORBIDDEN='^(registry/protocols\.jsonl|v3/universe\.json|v3/signal/base\.py|v3/universe_tiers\.py|v3/u350/|tools/check_|tools/yuclaw_c6|tools/yuclaw_reversal|services/c6_)'

cd "$REPO" || exit 1
say() { echo "[sentinel] $*"; }

# ---- solo-session rule -----------------------------------------------------
if [ "${SENTINEL_SUPERVISED:-0}" != "1" ]; then
    live=$(( $(pgrep -cx claude 2>/dev/null || echo 0) \
           + $(pgrep -cf 'claude/versions/.* --session-id' 2>/dev/null || echo 0) ))
    if [ "$live" -gt 0 ]; then
        say "refusing: $live live Claude session(s) — solo-session rule"
        exit 0
    fi
fi
if ! mkdir "$LOCK" 2>/dev/null; then
    say "refusing: lock held ($LOCK) — another sentinel run is live"
    exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# ---- prompt tamper check ---------------------------------------------------
got=$(sha256sum "$PROMPT" | cut -d' ' -f1)
if [ "$got" != "$PROMPT_PIN" ]; then
    say "refusing: prompt hash $got != pin $PROMPT_PIN (tamper-evident)"
    bash "$REPO/cron/push_alert.sh" "SENTINEL refused: prompt hash mismatch" || true
    exit 1
fi

# ---- never contend for the GPU --------------------------------------------
"$REPO/services/gpu-lock" status >/dev/null 2>&1 || true   # informational only; sentinel takes no GPU work

HEAD_BEFORE=$(git rev-parse HEAD)
T0=$(date +%s)
say "launching headless run (25 min bound) from $PROMPT"
timeout 1500 /home/zhangd2/.local/bin/claude -p "$(cat "$PROMPT")" \
    --dangerously-skip-permissions \
    > /tmp/yuclaw_sentinel_last_run.txt 2>&1
RC=$?
RUNTIME=$(( $(date +%s) - T0 ))

# ---- post-run authority check ---------------------------------------------
HEAD_AFTER=$(git rev-parse HEAD)
PUSHED=no
if [ "$HEAD_AFTER" != "$HEAD_BEFORE" ]; then
    bad=$(git diff --name-only "$HEAD_BEFORE".."$HEAD_AFTER" | grep -E "$FORBIDDEN" || true)
    if [ -n "$bad" ]; then
        say "AUTHORITY VIOLATION — forbidden paths touched: $bad — resetting"
        git reset --hard "$HEAD_BEFORE"
        bash "$REPO/cron/push_alert.sh" \
            "SENTINEL CRITICAL: authority violation reverted ($bad)" || true
    else
        if git push -q origin main 2>/dev/null; then
            PUSHED=yes
        else
            git pull --rebase -q origin main && git push -q origin main && PUSHED=yes || \
                bash "$REPO/cron/push_alert.sh" "SENTINEL: push failed after retry" || true
        fi
    fi
fi

# ---- accountability --------------------------------------------------------
LAST=$(tail -1 "$LOG" 2>/dev/null || echo '{}')
N_COMMITS=$(git rev-list --count "$HEAD_BEFORE".."$(git rev-parse HEAD)" 2>/dev/null || echo 0)
python3 - "$RC" "$RUNTIME" "$N_COMMITS" "$PUSHED" << 'PY' >> "$LOG"
import json, sys, datetime
print(json.dumps({"date": datetime.date.today().isoformat(),
                  "kind": "launcher", "rc": int(sys.argv[1]),
                  "runtime_s": int(sys.argv[2]),
                  "commits": int(sys.argv[3]), "pushed": sys.argv[4]}))
PY
bash "$REPO/cron/push_alert.sh" \
    "sentinel nightly: rc=$RC ${RUNTIME}s commits=$N_COMMITS pushed=$PUSHED · $(echo "$LAST" | head -c 160)" || true
say "done: rc=$RC runtime=${RUNTIME}s commits=$N_COMMITS pushed=$PUSHED"
exit 0
