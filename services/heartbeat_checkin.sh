#!/bin/sh
# YUCLAW off-box heartbeat check-in — cron: */5 * * * *
#
# Updates the dead-man heartbeat so an OFF-BOX watcher can detect this box
# going dark — the 2026-06-26 failure mode (box alive, remote access gone,
# nobody knew for 7 days). See docs/ops/resilience.md.
#
# Two channels, independent, both best-effort:
#   1. GitHub secret gist, PATCHed via gh (auth already on box). The watcher
#      .github/workflows/heartbeat-watch.yml alerts Telegram when the
#      timestamp goes >15 min stale. LIVE.
#   2. healthchecks.io-style ping. Dormant until HEALTHCHECKS_URL=... is
#      added to ~/.yuclaw_env; activates automatically, no other wiring.
#
# POSIX-clean (cron rules). Last-run status only in /tmp/yuclaw_heartbeat.log.

GIST_ID=c650e4e684db9ab9696aae31ced97264
GH=/home/zhangd2/bin/gh
LOG=/tmp/yuclaw_heartbeat.log
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

[ -f "$HOME/.yuclaw_env" ] && { set -a; . "$HOME/.yuclaw_env"; set +a; }

# Success = the PATCH *response* echoes our timestamp back (a follow-up GET
# can lag behind a replica and false-fail; the response itself cannot).
gist=FAIL
gist_err=""
resp=$(printf '{"files":{"spark-d89d-heartbeat.txt":{"content":"%s alive"}}}' "$TS" \
    | "$GH" api "gists/$GIST_ID" -X PATCH --input - \
        -q '.files["spark-d89d-heartbeat.txt"].content' 2>&1)
if [ "$resp" = "$TS alive" ]; then
    gist=OK
else
    gist_err=$resp
fi

hc=unset
if [ -n "${HEALTHCHECKS_URL:-}" ]; then
    hc=FAIL
    curl -fsS -m 10 --retry 2 "$HEALTHCHECKS_URL" >/dev/null 2>&1 && hc=OK
fi

echo "[$TS] gist=$gist healthchecks=$hc${gist_err:+ gist_err=$gist_err}" > "$LOG"
[ "$gist" = OK ]
