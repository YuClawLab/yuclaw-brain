#!/bin/sh
# YUCLAW resilience — one-shot ROOT installer.
#
#   Run:  sudo sh /home/zhangd2/yuclaw/services/install_root_resilience.sh
#
# Installs the three root-owned pieces of the Jun-26 hardening
# (docs/ops/resilience.md):
#   1. kernel.panic=10 + panic_on_oops=1   (panic reboots instead of hanging)
#   2. systemd hardware watchdog, 60s      (sbsa_gwdt resets a hung kernel)
#   3. narrow sudoers grant                (self-heal cron may restart tailscaled)
#
# Idempotent — safe to re-run. NO REBOOT performed or required: sysctl
# applies live, the watchdog arms via `systemctl daemon-reexec`, sudoers is
# effective immediately. Does not touch tailscaled itself, the yuclaw units,
# Ollama, or any cron.
set -eu

SRC=$(CDPATH= cd -- "$(dirname -- "$0")/etc" && pwd)

if [ "$(id -u)" != 0 ]; then
    echo "ERROR: run with sudo" >&2
    exit 1
fi

echo "== 1/3 sysctl: panic reboots instead of hanging"
install -m 0644 "$SRC/99-yuclaw-resilience.conf" /etc/sysctl.d/99-yuclaw-resilience.conf
sysctl --system >/dev/null
sysctl kernel.panic kernel.panic_on_oops

echo "== 2/3 hardware watchdog (sbsa_gwdt): RuntimeWatchdogSec=60"
mkdir -p /etc/systemd/system.conf.d
install -m 0644 "$SRC/watchdog.conf" /etc/systemd/system.conf.d/watchdog.conf
systemctl daemon-reexec
systemctl show -p RuntimeWatchdogUSec

echo "== 3/3 sudoers: self-heal cron may 'systemctl restart tailscaled'"
visudo -c -q -f "$SRC/sudoers-yuclaw-tailscale"
install -m 0440 "$SRC/sudoers-yuclaw-tailscale" /etc/sudoers.d/yuclaw-tailscale
visudo -c -q -f /etc/sudoers.d/yuclaw-tailscale || {
    rm -f /etc/sudoers.d/yuclaw-tailscale
    echo "ERROR: installed sudoers file failed validation — removed" >&2
    exit 1
}
echo "sudoers grant installed"

echo "== DONE. No reboot performed; none required."
