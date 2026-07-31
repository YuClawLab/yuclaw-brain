#!/bin/bash
# YUCLAW event-extraction worker — GPU-AWARE guarded drain.
#
# The worker classifies pending events_raw rows via the 70B on the shared box.
# It must NEVER collide with a v5 swarm / Layer run or a second model stack
# (Gemma/vLLM/llama-server). So before draining it checks the box is free and,
# if not, EXITS CLEANLY (0) — a busy box is a successful no-op, not a failure,
# so systemd/the timer never "fights" the operator. The poller keeps buffering
# filings to events_raw safely meanwhile; the drain just waits for the next
# timer tick when the box is free. Stop draining entirely with:
#     systemctl --user stop  yuclaw-event-worker.timer
#     systemctl --user disable yuclaw-event-worker.timer   # also across reboot
set -uo pipefail

# 0. The explicit GPU mutex is held (zebi benchmark or a manual swarm run —
#    see docs/ops/gpu-exclusivity.md). Whoever holds /tmp/gpu-owner owns the
#    GPU outright; never drain underneath them.
if [ -s /tmp/gpu-owner ]; then
    echo "[worker-guard] $(date -u +%FT%TZ) gpu-lock held ($(cat /tmp/gpu-owner)) — skip drain"
    exit 0
fi

# 1. A second model stack (NOT prod Ollama) is running.
NONOLLAMA=$(ps -eo args 2>/dev/null | grep -iE 'llama-server|vllm|sglang|text-generation-launcher' | grep -viE 'ollama' | grep -v grep || true)
if [ -n "$NONOLLAMA" ]; then
    echo "[worker-guard] $(date -u +%FT%TZ) non-Ollama model stack present — skip drain"
    exit 0
fi

# 2. A v5 swarm / Layer / capture job (our own GPU-heavy work) is running.
SWARM=$(ps -eo args 2>/dev/null | grep -iE 'v5\.swarm|run_specialized|validate_scale|batch_specialists|risk_[a-z_]*_capture|specialized\.py|c6_specialized_live' | grep -v grep || true)
if [ -n "$SWARM" ]; then
    echo "[worker-guard] $(date -u +%FT%TZ) v5 swarm/Layer job running — skip drain"
    exit 0
fi

# Box is free → drain a bounded batch then exit (bounded so any later swarm waits
# at most one short batch, never an unbounded run).
cd /home/zhangd2/yuclaw
echo "[worker-guard] $(date -u +%FT%TZ) box free — draining up to 8 rows"
/usr/bin/python3 -m v3.extract.event_worker --once --batch 8
RC=$?

# C6 specialized live step (restoration order, 2026-07-31): same GPU slot,
# bounded (2/tick), idempotent, forward-only from 2026-07-31 — the Jul-16..30
# backlog is an owner decision (Part C) and is never touched here. Non-fatal:
# a C6 failure must not fail the extraction chain.
if [ $RC -eq 0 ]; then
    /usr/bin/python3 /home/zhangd2/yuclaw/services/c6_specialized_live.py --max 2 \
        || echo "[worker-guard] $(date -u +%FT%TZ) c6-live step failed (non-fatal)"
fi
exit $RC
