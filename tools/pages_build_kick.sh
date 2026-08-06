#!/bin/bash
# Pages check-and-kick (2026-08-06) — a push does NOT reliably trigger a
# GitHub Pages build: observed on the v5.3.3 release push, where CI ran but
# builds/latest sat on the previous day's commit until an explicit
# POST /pages/builds. This step makes that observation structural: after
# every push, confirm builds/latest picks up HEAD; if it hasn't and nothing
# is queued/building, request a build once, then keep polling to `built`.
#
# Runs BEFORE tools/deploy_verify.py in the deploy path — deploy_verify can
# only poll the live site; it cannot start a build that never got queued.
# Exit 0 = Pages built this commit; exit 1 = not built by the deadline
# (surfaced in the pipeline log + health monitor, same as a stale deploy).
set -u
GH=/home/zhangd2/bin/gh
GH_REPO="YuClawLab/yuclaw-brain"
REPO_DIR="/home/zhangd2/yuclaw"
DEADLINE=$((SECONDS + ${1:-600}))
WANT=$(/usr/bin/git -C "$REPO_DIR" rev-parse HEAD)
KICKED=0

while [ $SECONDS -lt $DEADLINE ]; do
    LINE=$("$GH" api "repos/$GH_REPO/pages/builds/latest" \
           --jq '"\(.status) \(.commit)"' 2>/dev/null) || LINE=""
    STATUS=${LINE%% *}
    COMMIT=${LINE##* }
    if [ "$COMMIT" = "$WANT" ] && [ "$STATUS" = "built" ]; then
        echo "[pages-kick] built $WANT"
        exit 0
    fi
    if [ "$COMMIT" != "$WANT" ] && [ "$STATUS" != "building" ] && \
       [ "$STATUS" != "queued" ] && [ "$KICKED" = 0 ]; then
        echo "[pages-kick] latest build is $COMMIT ($STATUS), HEAD is $WANT — requesting a build"
        "$GH" api -X POST "repos/$GH_REPO/pages/builds" >/dev/null 2>&1 && KICKED=1
    fi
    sleep 15
done
echo "[pages-kick] TIMEOUT — Pages never built $WANT (last: $COMMIT $STATUS)"
exit 1
