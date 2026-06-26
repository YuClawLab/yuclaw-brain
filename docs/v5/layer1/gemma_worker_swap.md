# v5 Layer 1 — Gemma worker swap (Order 3)

Branch `v5-layer1`. Wire **`gemma4:26b-a4b-it-q4_K_M`** as the swarm worker tier (the validated
+29% grounding win), now that prod Ollama is 0.22.1. The binding constraint was VRAM, not the
model: under 0.22 auto-context the 70B alone is 95.4 GiB resident — Gemma can't coexist unless
context is capped.

## The context-cap math (measured, not assumed)

The 0.22 daemon now launches with **`OLLAMA_CONTEXT_LENGTH=8192`** (via `~/start-ollama.sh`),
matching the swarm's existing per-request `num_ctx=8192` (`YUCLAW_V5_NUM_CTX`). Measured resident
footprint on the GB10 (119.7 GiB unified):

| model | n_ctx | resident |
|---|---:|---:|
| yuclaw-llm-70b | 8192 | **45.8 GiB** (was 95.4 at 131072) |
| gemma4:26b-a4b | 8192 | **19.9 GiB** |
| **both resident** | | **65.7 GiB → ~52 GiB free** |

Headroom held ~50 GiB **throughout a full swarm run** — no OOM, target (≥15-20 GiB) cleared with
huge margin. The cap doesn't truncate anything: the v3 producer self-limits to 2500 chars (~800
tokens ≪ 8192), and 8192 is the swarm's established synthesis/agent default since D5B.

## In-place A/B (same ABT EARNINGS_BEAT filing, same daemon)

| metric | llama3.1:8b | **gemma4:26b-a4b** |
|---|---:|---:|
| mean grounding | 0.800 | **0.950** |
| specialist grounding | 0.67 / 0.67 | **1.0 / 1.0** |
| base citation fidelity | 0.889 | 0.846 |
| C6 direction/risk separation | PASS | **PASS** |
| wall | 250s | **218s** |

The +grounding win replicates in-place (not just the isolated A/B), strongest on the specialists,
C6 separation intact, faster, no OOM.

## The persistent config

- **Daemon** (`~/start-ollama.sh`): `OLLAMA_CONTEXT_LENGTH=8192` — caps EVERY model load incl. the
  v3 producer's 70B, so a stray uncapped 95 GiB load can't OOM a concurrent Gemma. Launch:
  `setsid nohup ~/start-ollama.sh > ~/ollama-serve.log 2>&1 < /dev/null & disown`.
- **Worker** (`yuclaw/v5/swarm/worker.py`): default `WORKER_MODEL=gemma4:26b-a4b-it-q4_K_M`,
  `WORKER_THINK=false` (required for the thinking model — empty content otherwise),
  `WORKER_NUM_CTX=8192`. Override back to 8B with `YUCLAW_V5_WORKER_MODEL=llama3.1:8b`.
- **70B synthesis** unchanged (`SYNTH_MODEL=yuclaw-llm-70b`), runs at the same 8192 cap.

## Flagged (not in scope here)

- The prod Ollama daemon has **no supervisor** (manual launch). The cap persists only if launched
  via `~/start-ollama.sh`; a reboot leaves the daemon down entirely (pre-existing fragility, same
  class as the old poller — a systemd unit would fix it, separate from this swap).

See [[v5-gemma4-worker]], [[ingestion-systemd-supervision]].
