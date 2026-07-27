#!/bin/bash
# Best-effort Telegram alert for chain push failures (order of 2026-07-27).
# Never fails the caller: every path exits 0. Uses the same env file as the
# broadcast bot; silent no-op when tokens are absent (alarm still reaches the
# operator via the health monitor's marker check).
MSG="${1:-yuclaw chain push failure}"
[ -f "$HOME/.yuclaw_env" ] && { set -a; . "$HOME/.yuclaw_env"; set +a; }
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHANNEL:-}" ]; then
    /usr/bin/python3 - "$MSG" << 'PY' || true
import json, os, sys, urllib.request
msg = f"YUCLAW CHAIN ALERT: {sys.argv[1]}"
req = urllib.request.Request(
    f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
    data=json.dumps({"chat_id": os.environ["TELEGRAM_CHANNEL"],
                     "text": msg}).encode(),
    headers={"Content-Type": "application/json"})
try:
    urllib.request.urlopen(req, timeout=10)
    print("[push_alert] telegram sent")
except Exception as exc:
    print(f"[push_alert] telegram send failed (non-fatal): {exc}")
PY
else
    echo "[push_alert] telegram env absent — marker-only alerting"
fi
exit 0
