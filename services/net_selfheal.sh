#!/bin/sh
# YUCLAW network-link self-heal — cron: */5 * * * *
#
# Jun-26 lesson, link layer: at 03:22:53 MDT the SHAW-379D mesh flapped
# (deauth Reason 2, then a 4-way-handshake stall), NetworkManager entered its
# "disconnected during association, asking for new key" path, and on this
# headless box no secret agent exists -> activation failed 'no-secrets' ->
# NM BLOCKED AUTOCONNECT for the profile. The WiFi stayed down for 7 days on
# healthy hardware; one `nmcli connection up` (which clears the block and
# retries the STORED secrets) would have fixed it at any point.
#
# Recovery ladder, only after the link has been bad >5 min:
#   (a) nmcli reconnect of the profile   (clears autoconnect block)
#   (b) if still down: mt7925e driver module reload, then reconnect again
#
# HARD SAFETY RULES:
#   - Never acts while the link is healthy (healthy = default IPv4 route
#     present AND wlP9s9 in NM state >=100/connected). An upstream ISP outage
#     with the link itself up is NOT our trigger — we must never cycle a
#     working link, it carries VinZhang's only access.
#   - Acts only after >5 min continuously bad (two cron ticks).
#   - Rate-limited: one recovery attempt per 30 min. Never reboots, never
#     restarts NetworkManager.
#
# Requires the exact-match sudoers grants installed by
# services/install_root_resilience.sh; until then logs SKIP, exit 0.
#
# Dry run (read-only, safe anytime): sh net_selfheal.sh --dry-run
# POSIX-clean (cron rules). Log: /tmp/yuclaw_net_selfheal.log
#
# shellcheck disable=SC2024  # >>$LOG on sudo lines runs as zhangd2 by design:
# the log must stay user-owned; only the command itself needs root.

DEV=wlP9s9
PROFILE=SHAW-379D
MODULE=mt7925e
NMCLI=/usr/bin/nmcli
MODPROBE=/usr/sbin/modprobe
IPCMD=/usr/sbin/ip
LOG=/tmp/yuclaw_net_selfheal.log
BADSTAMP=/tmp/yuclaw_net_selfheal.badstamp
RATESTAMP=/tmp/yuclaw_net_selfheal.laststamp
BAD_PERSIST=300
RATE_LIMIT=1800

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
log() {
    if [ "$DRY" -eq 1 ]; then echo "$1"; else echo "[$TS] $1" >> "$LOG"; fi
}

# Grant check WITHOUT executing anything: `sudo -l` lists permitted commands;
# we need our exact NOPASSWD line (the passworded (ALL:ALL) entry is useless
# from cron, so string-match the NOPASSWD grant specifically).
grant_present() {
    sudo -n -l 2>/dev/null | grep -qF "NOPASSWD: $NMCLI -w 30 connection up $PROFILE"
}

link_healthy() {
    [ -n "$($IPCMD -4 route show default 2>/dev/null)" ] || return 1
    state=$($NMCLI -g GENERAL.STATE device show "$DEV" 2>/dev/null | cut -d' ' -f1)
    [ "${state:-0}" -ge 100 ] 2>/dev/null
}

# ---- 0. Healthy: clear the bad-since clock and stay silent. --------------
if link_healthy; then
    if [ "$DRY" -eq 1 ]; then
        echo "link healthy, no action"
        if grant_present; then echo "sudoers grant: present"; else echo "sudoers grant: MISSING (run: sudo sh ~/yuclaw/services/install_root_resilience.sh)"; fi
    else
        rm -f "$BADSTAMP"
    fi
    exit 0
fi

# ---- 1. Unhealthy: require >5 min of continuous badness first. -----------
now=$(date +%s)
if [ "$DRY" -eq 0 ] && [ ! -f "$BADSTAMP" ]; then
    echo "$now" > "$BADSTAMP"
fi
bad_since=$(cat "$BADSTAMP" 2>/dev/null || echo "$now")
bad_for=$((now - bad_since))

if [ "$bad_for" -lt "$BAD_PERSIST" ]; then
    log "link UNHEALTHY for ${bad_for}s (<${BAD_PERSIST}s) — watching, not acting"
    exit 0
fi

# ---- 2. Rate limit: one attempt per 30 min. ------------------------------
last=$(cat "$RATESTAMP" 2>/dev/null || echo 0)
if [ "$((now - last))" -lt "$RATE_LIMIT" ]; then
    log "link UNHEALTHY ${bad_for}s; last attempt <30 min ago — waiting"
    exit 0
fi

if [ "$DRY" -eq 1 ]; then
    echo "link UNHEALTHY for ${bad_for}s — would attempt: (a) nmcli reconnect $PROFILE, (b) $MODULE reload"
    if grant_present; then echo "sudoers grant: present"; else echo "sudoers grant: MISSING"; fi
    exit 0
fi

if ! grant_present; then
    log "SKIP: link down ${bad_for}s but sudoers grant missing (run: sudo sh ~/yuclaw/services/install_root_resilience.sh)"
    exit 0
fi

# Stamp BEFORE acting — a hung or failed attempt must not flap the link.
echo "$now" > "$RATESTAMP"

# ---- 3a. Profile reconnect: clears NM autoconnect block, retries the -----
#          stored secrets (the exact fix Jun-26 needed).
log "link down ${bad_for}s — attempting nmcli reconnect of $PROFILE"
sudo -n "$NMCLI" -w 30 connection up "$PROFILE" >>"$LOG" 2>&1
sleep 10
if link_healthy; then
    rm -f "$BADSTAMP"
    log "RECOVERED via nmcli connection up"
    exit 0
fi

# ---- 3b. Driver module reload, then reconnect again. ---------------------
log "nmcli reconnect insufficient — reloading driver $MODULE"
if ! sudo -n "$MODPROBE" -r "$MODULE" >>"$LOG" 2>&1; then
    log "driver unload failed — giving up until next 30-min window"
    exit 0
fi
sleep 5
sudo -n "$MODPROBE" "$MODULE" >>"$LOG" 2>&1
sleep 10
sudo -n "$NMCLI" -w 30 connection up "$PROFILE" >>"$LOG" 2>&1
sleep 10
if link_healthy; then
    rm -f "$BADSTAMP"
    log "RECOVERED via driver reload + reconnect"
else
    log "STILL DOWN after nmcli reconnect + driver reload — next attempt in 30 min"
fi
exit 0
