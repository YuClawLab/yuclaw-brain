# GPU Exclusivity Contract — spark-d89d (DGX Spark GB10)

**Standing rule: YUCLAW and any benchmark/second workload (Zebi or otherwise)
never touch the GPU at the same time.** This is enforced by `gpu-lock` and
respected by the YUCLAW event worker; it is a hard requirement for every
future benchmark order.

## Why this exists (2026-06-26 incident)

A Zebi benchmark loaded a second model stack alongside the prod 70B on the
GB10's 128GB **unified** memory. The box exhausted memory, wedged, and lost
remote access (Tailscale died with it). It sat unreachable — while still
running — until a physical power-cycle on 2026-07-03. Two failures compounded:

1. Nothing made GPU ownership exclusive (both stacks loaded "successfully").
2. Nothing capped the second workload's memory, so the failure mode was a
   wedged box instead of a killed process.

## The contract — every Zebi/benchmark order MUST

1. **Acquire the GPU before loading anything:**

   ```sh
   gpu-lock acquire zebi        # exits 1 if YUCLAW holds the GPU — wait, don't force
   ```

2. **Run the workload under a memory cap** (as a systemd scope, so the kernel
   OOM-kills the *process* instead of wedging the *box* — the Jun-26 root
   cause):

   ```sh
   systemd-run --user --scope -p MemoryMax=100G -p MemorySwapMax=0 <benchmark cmd>
   ```

   100G of 128G leaves headroom for the OS, tailscaled, and the YUCLAW
   services. `MemorySwapMax=0` makes the kill immediate instead of a
   swap-thrash death spiral.

3. **Restore state, then release:**

   ```sh
   gpu-lock release zebi
   ```

Or combine 1+3 automatically (releases on exit, including Ctrl-C):

```sh
gpu-lock run zebi -- systemd-run --user --scope -p MemoryMax=100G -p MemorySwapMax=0 <benchmark cmd>
```

## Verified on this box (2026-07-04)

- `systemd-run --user --scope -p MemoryMax=1G` installs `memory.max` in the
  scope's cgroup (memory controller is delegated to user@1000).
- A 2G write inside a 1G-capped scope was OOM-killed (exit 137) with zero
  impact on the rest of the box.
- Unified-memory note: on GB10 there is no separate VRAM — model weights live
  in the same LPDDR5X the cap governs, so the cap bounds the blast radius of
  a runaway load. (Verified for host allocations; not load-tested against a
  real CUDA workload in this order.)

## gpu-lock mechanics

- Tool: `~/bin/gpu-lock` → symlink to `services/gpu-lock` (repo-canonical).
- Owner file `/tmp/gpu-owner` holds `<name> pid=<caller> since=<utc>`;
  mutations are atomic via `flock` on `/tmp/gpu-owner.lock`. Locks live in
  tmpfs and vanish on reboot (nobody owns the GPU after boot).
- `gpu-lock status` → `free` (exit 0) or `held: ...` (exit 1), and flags a
  dead caller pid as possibly stale. Stale lock after a crashed run:
  verify nothing is on the GPU, then `gpu-lock clear --force`.

## Who respects the lock today

- **event worker** (`services/event_worker_guarded.sh`, check 0): skips its
  15-min drain whenever `/tmp/gpu-owner` exists, whoever holds it. A held
  lock is a clean no-op skip (exit 0), so the timer never fights the holder.
- **YUCLAW swarm/Layer runs**: should `gpu-lock acquire yuclaw` at start
  (adopt in the next swarm order; today they are covered by the worker
  guard's process-pattern checks and by stopping `yuclaw-event-worker.timer`).
- **Known gap**: the v4 `check_nemotron.sh` cron predates the lock and does
  not check it (it can double-load the 70B blob — see memory note from the
  June swarm work). Out of scope for the resilience order; fix with the next
  v4 maintenance pass.
