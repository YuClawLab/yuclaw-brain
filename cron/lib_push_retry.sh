#!/bin/bash
# push_with_retry — the Friday-race fix (order of 2026-07-27).
#
# Contract: rebase onto the remote immediately before pushing; on push
# rejection, re-rebase and retry exactly once; on double failure NEVER exit
# silently — write a marker the health monitor reads, fire the alert hook
# (best-effort), and return the distinct code 22. On success the marker is
# cleared. POSIX-clean enough for cron (bash function, no exotic features).
#
# Usage:   push_with_retry <remote> <branch> <marker_file> [alert_hook_cmd]
# Returns: 0 push landed · 21 rebase failed · 22 push failed twice

push_with_retry() {
    local remote="$1" branch="$2" marker="$3" alert_hook="${4:-}"
    local ts
    ts=$(date -u +"%Y-%m-%d %H:%M UTC")

    if ! /usr/bin/git pull --rebase --autostash "$remote" "$branch"; then
        echo "[push_with_retry] rebase against $remote/$branch FAILED at $ts" \
            | tee "$marker"
        [ -n "$alert_hook" ] && $alert_hook "rebase failed ($remote/$branch)" || true
        return 21
    fi
    if /usr/bin/git push "$remote" "$branch"; then
        rm -f "$marker"
        return 0
    fi
    echo "[push_with_retry] push rejected — re-rebasing and retrying once"
    if ! /usr/bin/git pull --rebase --autostash "$remote" "$branch"; then
        echo "[push_with_retry] re-rebase FAILED at $ts" | tee "$marker"
        [ -n "$alert_hook" ] && $alert_hook "re-rebase failed ($remote/$branch)" || true
        return 21
    fi
    if /usr/bin/git push "$remote" "$branch"; then
        rm -f "$marker"
        return 0
    fi
    {
        echo "PUSH FAILED TWICE: $remote/$branch at $ts"
        echo "The page chain rendered and committed but is NOT deployed."
        echo "Manual action: cd repo && git pull --rebase && git push; then"
        echo "python3 tools/deploy_verify.py"
    } | tee "$marker"
    [ -n "$alert_hook" ] && $alert_hook "push failed twice ($remote/$branch) — pages NOT deployed" || true
    return 22
}
