# spark-d89d Resilience — the Jun-26 hardening

**Incident (2026-06-26):** a Zebi benchmark loaded a second model stack next
to the prod 70B; the box exhausted its 128GB unified memory and wedged.
Tailscale died with it, so the box — still powered, still "running" — was
unreachable for 7 days until a physical power-cycle on 2026-07-03. Nothing
alerted, because all monitoring lived ON the box.

Three protection layers now exist. Boot behavior was verified **by
inspection only** — no reboot was performed during this order.

## Layer 1 — Self-rescue for true hangs (Part A)

| Piece | State | Verify |
|---|---|---|
| `kernel.panic=10`, `panic_on_oops=1` | root installer | `sysctl kernel.panic` |
| Hardware watchdog `sbsa_gwdt`, 60s via systemd | root installer | `systemctl show -p RuntimeWatchdogUSec` → `1min` |
| tailscaled `Restart=on-failure` | already in stock unit | `systemctl cat tailscaled` |
| tailscale self-heal cron (`services/tailscale_selfheal.sh`, */10) | live; restart branch needs root installer | `/tmp/yuclaw_tailscale_selfheal.log` |

The root-owned pieces install with ONE command (idempotent, **no reboot**):

```sh
sudo sh /home/zhangd2/yuclaw/services/install_root_resilience.sh
```

Until that runs: panic still hangs the box, the watchdog is unarmed, and the
self-heal cron logs `SKIP` instead of restarting tailscaled.

The self-heal never touches a working tailscale, refuses to act when the
underlying network is down (restart would fix nothing), and rate-limits to
one attempt per 30 min.

## Layer 2 — GPU exclusivity + memory caps (Part B)

See **docs/ops/gpu-exclusivity.md** — the standing contract. Summary:
`gpu-lock acquire zebi` before any benchmark, run the workload under
`systemd-run --user --scope -p MemoryMax=100G -p MemorySwapMax=0`, release
after. The event worker skips its drain whenever the lock is held. The
1G-cap OOM-kill behavior was verified live on 2026-07-04 (exit 137, box
unaffected).

## Layer 3 — Off-box dead-man heartbeat (Part C)

The layer that would have caught Jun-26 in minutes instead of days.

- **Check-in:** cron `*/5` runs `services/heartbeat_checkin.sh`, which
  PATCHes a UTC timestamp into a secret gist
  (`c650e4e684db9ab9696aae31ced97264`, owner YuClawLab). Status:
  `/tmp/yuclaw_heartbeat.log`.
- **Watcher:** `.github/workflows/heartbeat-watch.yml` runs OFF-BOX on
  GitHub's scheduler every ~15 min. Heartbeat >15 min stale → Telegram alert
  to the signals channel. Damping: continuous alerts the first hour, then
  ~4 reminders/day. Detection latency 15–35 min typical.
- **Secrets** (repo Actions secrets): `HEARTBEAT_GIST_ID`,
  `HEARTBEAT_GIST_TOKEN`, `HEARTBEAT_TG_TOKEN`, `HEARTBEAT_TG_CHAT`.
  Rotating the gh token or bot token means re-running `gh secret set`.
- **Tested live 2026-07-05:** stale timestamp → dispatched run → verdict
  STALE → Telegram `ok:true` (message delivered); fresh timestamp → verdict
  fresh → no alert. A `[TEST RESOLVED]` notice followed on the channel.
- The workflow deliberately fails its own run (without alerting) if the gist
  fetch fails — a GitHub hiccup must not fake a box outage. Actions history
  is the audit trail.

Optional second channels, staged but needing VinZhang:

1. **healthchecks.io** (email alerts): create a free account, add a check
   (period 5 min, grace 10 min), then append
   `HEALTHCHECKS_URL=https://hc-ping.com/<uuid>` to `~/.yuclaw_env`.
   `heartbeat_checkin.sh` starts pinging it automatically — no other wiring.
2. **spark-3941 tailnet watcher**: install
   `services/spark3941_monitor.sh` on spark-3941 by hand (instructions in
   the file header; spark-d89d has no SSH trust to it).

## Known gaps / escalations

- **Root installer not yet run** — needs the sudo password once (see Layer 1).
- **If the box hangs harder than the watchdog** (or before the installer
  runs): only remedy is physical power. A smart plug on spark-d89d's PSU is
  the recommended last-resort actuator.
- `check_nemotron.sh` (v4 cron) predates `gpu-lock` and does not respect it.
- The stored git credential (`~/.git-credentials`) lacks `workflow` scope;
  pushes touching `.github/workflows/` must use the gh keyring token
  (`gh auth token`) as done in this order, or the PAT needs the scope added.
