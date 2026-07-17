# spark-d89d Resilience — the Jun-26 hardening

**Incident (2026-06-26):** a Zebi benchmark loaded a second model stack next
to the prod 70B; the box exhausted its 128GB unified memory and wedged.
Tailscale died with it, so the box — still powered, still "running" — was
unreachable for 7 days until a physical power-cycle on 2026-07-03. Nothing
alerted, because all monitoring lived ON the box.

**Link-layer root cause (from the kernel + NetworkManager journals):** the
durable failure was the WiFi link itself. 03:19:45 MDT the SHAW-379D mesh
dropped the association; over the next 3 minutes wlP9s9 bounced between the
two mesh BSSIDs (deauth Reason 2 `PREV_AUTH_NOT_VALID`, auth timeouts); at
03:22:53 a 4-way handshake stalled and NetworkManager took its "disconnected
during association, asking for new key" path. Headless box → no secret agent
→ `no secrets: No agents were available` → activation failed `no-secrets` →
**NM blocked autoconnect for the profile**. The link then stayed down until
the on-site reconnect at Jul-3 15:39 — 7 days — on healthy hardware (no
firmware crash, no mt7925e/PCIe errors in the journal). One
`nmcli connection up SHAW-379D` (clears the block, retries stored secrets)
would have restored it at any point. Layer 4 closes exactly this gap.

Four protection layers now exist. Boot behavior was verified **by
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

## Layer 4 — WiFi link self-heal (Part D, added 2026-07-05)

Companion to the tailscale self-heal, one layer down the stack: tailscaled
cannot come back if the underlying link is down and NM refuses to reconnect.

- **Cron `*/5`** runs `services/net_selfheal.sh`. Healthy = default IPv4
  route present AND wlP9s9 in NM state `connected`. Healthy → exits silently,
  touches nothing (an upstream ISP outage with the link up is deliberately
  NOT a trigger — never cycle a working link; it carries the only access).
- **Trigger:** link continuously unhealthy >5 min. Recovery ladder:
  (a) `nmcli -w 30 connection up SHAW-379D` — clears the autoconnect block
  and retries the stored PSK (the exact Jun-26 fix); (b) if still down,
  `modprobe -r mt7925e` + `modprobe mt7925e`, then reconnect again.
- **Rate limit:** one attempt per 30 min, stamped before acting. Never
  reboots, never restarts NetworkManager. Log: `/tmp/yuclaw_net_selfheal.log`.
- **Sudoers:** three exact-match NOPASSWD lines in the same
  `etc/sudoers-yuclaw-tailscale` file (nmcli reconnect + modprobe pair);
  until the installer is re-run the script logs `SKIP` and exits 0.
- **Dry run** (read-only, safe anytime):
  `sh ~/yuclaw/services/net_selfheal.sh --dry-run` → on a healthy link prints
  `link healthy, no action` plus grant status.
- **Honest test boundary:** the recovery branch (nmcli up / driver reload)
  has never been executed — running it against a healthy link is forbidden
  by the standing safety rule. Its first real execution will be the next
  actual link outage. The decision logic (health check, 5-min persistence,
  rate limit, grant check) is what dry-run inspection verified.

## Known gaps / escalations

- **Root installer run on 2026-07-04** (verified by inspection:
  `kernel.panic=10`, `panic_on_oops=1`, `RuntimeWatchdogUSec=1min`,
  tailscaled sudoers grant live). **Re-run needed once** to pick up the
  Layer 4 sudoers lines added 2026-07-05:
  `sudo sh /home/zhangd2/yuclaw/services/install_root_resilience.sh`
- **If the box hangs harder than the watchdog** (or before the installer
  runs): only remedy is physical power. A smart plug on spark-d89d's PSU is
  the recommended last-resort actuator.
- `check_nemotron.sh` (v4 cron) predates `gpu-lock` and does not respect it.
- The stored git credential (`~/.git-credentials`) lacks `workflow` scope;
  pushes touching `.github/workflows/` must use the gh keyring token
  (`gh auth token`) as done in this order, or the PAT needs the scope added.
- Pages deploy failure mode added: build-level failure (Jekyll/Liquid), distinct from push-≠-live; `.nojekyll` is the guard.
