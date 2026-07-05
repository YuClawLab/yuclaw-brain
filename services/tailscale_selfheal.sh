#!/bin/sh
# YUCLAW tailscale self-heal — cron: */10 * * * *
#
# Jun-26 lesson: tailscaled died while the box kept running, so the box was
# unreachable for 7 days. The stock unit already has Restart=on-failure, but
# that misses clean exits and wedged-but-running states. This closes the gap:
# if tailscale is down AND the underlying network is up, restart tailscaled.
#
# - Never touches a WORKING tailscale (healthy exit is silent, first check).
# - Requires the narrow sudoers grant installed by
#   services/install_root_resilience.sh (NOPASSWD for exactly
#   '/usr/bin/systemctl restart tailscaled'); until then logs SKIP, exit 0.
# - Rate-limited: at most one restart attempt per 30 min (no flapping).
# POSIX-clean (cron rules). Log: /tmp/yuclaw_tailscale_selfheal.log

LOG=/tmp/yuclaw_tailscale_selfheal.log
STAMP=/tmp/yuclaw_tailscale_selfheal.laststamp
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

log() { echo "[$TS] $1" >> "$LOG"; }

# 0. Healthy? The daemon answering `status` at all is the health signal
#    (peer list contents do not matter here).
if /usr/bin/tailscale status >/dev/null 2>&1; then
    exit 0
fi

# 1. If the underlying network is also down, a tailscaled restart fixes
#    nothing — stand down and let the next tick re-check.
if ! /usr/bin/ping -c1 -W3 1.1.1.1 >/dev/null 2>&1 \
   && ! /usr/bin/ping -c1 -W3 8.8.8.8 >/dev/null 2>&1; then
    log "tailscale DOWN but network also down — not restarting"
    exit 0
fi

# 2. Rate limit: one restart attempt per 30 min.
now=$(date +%s)
last=$(cat "$STAMP" 2>/dev/null || echo 0)
if [ "$((now - last))" -lt 1800 ]; then
    log "tailscale DOWN; last restart attempt <30min ago — waiting"
    exit 0
fi

# 3. Restart via the narrow sudoers grant (exact command match).
if sudo -n /usr/bin/systemctl restart tailscaled 2>>"$LOG"; then
    echo "$now" > "$STAMP"
    log "tailscale was DOWN with network up — restarted tailscaled"
else
    log "SKIP: tailscale down, network up, but sudoers grant missing (run: sudo sh ~/yuclaw/services/install_root_resilience.sh)"
fi
