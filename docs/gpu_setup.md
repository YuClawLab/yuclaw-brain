# GPU Setup — Ollama on the GB10 (sm_121a) — DO NOT regress to CPU

**Last verified:** 2026-05-30. **Hardware:** NVIDIA GB10 (Grace-Blackwell, unified memory,
compute capability **12.1 / sm_121a**, `type=iGPU`). **Driver:** 580.126.09, **CUDA:** 13.0.

## TL;DR — the one thing that matters

**Run Ollama from the bundle that ships the CUDA runner, not the bare binary.**

| | Path | Result |
|---|---|---|
| ❌ WRONG (was running 23 days) | `/home/zhangd2/bin/ollama` | 36 MB standalone binary, **no `lib/ollama/` runner** → discovers **0 GPUs** → 70B runs on **CPU** (~274 s/filing) |
| ✅ RIGHT | `/home/zhangd2/ollama-install/bin/ollama` | auto-loads sibling `../lib/ollama/` incl. **`cuda_v13/`** runner → detects GB10 → 70B on **GPU** (~25 s/filing) |

Start command that works (used for Order 1E GPU run):
```bash
OLLAMA_KEEP_ALIVE=30m setsid nohup /home/zhangd2/ollama-install/bin/ollama serve \
    > /tmp/ollama_gpu.log 2>&1 < /dev/null &
```

## Why the bare binary fails

Ollama's GPU support lives in a **separate runner library tree** (`lib/ollama/`), not the
`ollama` binary. The official install ships both; someone had dropped only the 36 MB binary
into `~/bin`. With no runner libs, GPU bootstrap finishes in ~13 ms and logs:
```
inference compute  id=cpu  library=cpu  ...  total="119.7 GiB"
vram-based default context  total_vram="0 B"
```
`~/bin` is first on `$PATH`, so `which ollama` → the broken one. **Any cron/script that runs
bare `ollama serve` silently regresses to CPU.**

## The working bundle

`/home/zhangd2/ollama-install/` (Ollama **0.18.0**) contains:
```
bin/ollama
lib/ollama/cuda_v12/   ← sm_120 only; correctly FILTERED OUT for the GB10
lib/ollama/cuda_v13/   ← libggml-cuda.so (CUDA 13) — SUPPORTS sm_121 / GB10  ✅
lib/ollama/cuda_v13/libcublas*.so.13, libcudart.so.13
```
On startup the bundle logs (this is the success signal):
```
verifying if device is supported  library=.../cuda_v13  description="NVIDIA GB10" compute=12.1
inference compute  library=CUDA compute=12.1 name=CUDA0 description="NVIDIA GB10"
                   libdirs=ollama,cuda_v13 driver=13.0 type=iGPU total="119.7 GiB" available="110.7 GiB"
```
Note: **0.18.0 was already sufficient** — no upgrade to v0.24.0 was needed. The problem was
never the version; it was running the binary without its runner libs. (A local
`~/llama.cpp/build` exists but is built for **sm_120a only** (`CMAKE_CUDA_ARCHITECTURES=120`,
no PTX) and will **not** load on the GB10 — do not use it as a backend.)

## Verify GPU is actually in use (run after any Ollama restart/upgrade)
```bash
# 1. Ollama sees the GPU (look for library=CUDA ... NVIDIA GB10, NOT id=cpu):
grep "inference compute" /tmp/ollama_gpu.log

# 2. Model is resident in VRAM (size_vram must be > 0; ~102 GB for the 70B w/ default ctx):
curl -s localhost:11434/api/ps | python3 -c "import sys,json;[print(m['name'],'size_vram=%.1fGB'%(m['size_vram']/1e9)) for m in json.load(sys.stdin)['models']]"

# 3. GPU busy during inference (util should hit ~90%+, power ~45W; CPU-fallback sits ~0%/7W):
nvidia-smi --query-gpu=utilization.gpu,power.draw --format=csv,noheader
```

## Performance (measured, 70B Q4_K_M, real SEC filing extraction)
- **CPU fallback:** ~274 s/filing  → a 45-filing reprocess = ~3.5 h
- **GPU (cuda_v13):** ~25 s/filing → same job = ~18 min  (**~11× faster**, 96% GPU util)
- One-time model load into unified memory: ~46 s.

## Durability — preventing silent regression
1. **Make the good binary the default** so `which ollama` resolves to the bundle:
   `ln -sf /home/zhangd2/ollama-install/bin/ollama /home/zhangd2/bin/ollama`
   (Ollama resolves the symlink and finds `../lib/ollama` relative to the *real* path.)
   — or set `OLLAMA_LIBRARY_PATH=/home/zhangd2/ollama-install/lib/ollama`.
2. **After any Ollama upgrade,** re-run the 3 verification checks above. An upgrade that drops
   or replaces `lib/ollama/cuda_v13` will silently fall back to CPU.
3. The live `event_worker` and the v3 extraction pipeline only talk to the Ollama HTTP API on
   `localhost:11434` — they don't care which binary, only that the **serving process is the
   GPU-enabled bundle.** Confirm with check #2 after restarts.
