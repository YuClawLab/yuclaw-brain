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

# 1. A second model stack (NOT prod Ollama) is running.
NONOLLAMA=$(ps -eo args 2>/dev/null | grep -iE 'llama-server|vllm|sglang|text-generation-launcher' | grep -viE 'ollama' | grep -v grep || true)
if [ -n "$NONOLLAMA" ]; then
    echo "[worker-guard] $(date -u +%FT%TZ) non-Ollama model stack present — skip drain"
    exit 0
fi

# 2. A v5 swarm / Layer / capture job (our own GPU-heavy work) is running.
SWARM=$(ps -eo args 2>/dev/null | grep -iE 'v5\.swarm|run_specialized|validate_scale|batch_specialists|risk_[a-z_]*_capture|specialized\.py' | grep -v grep || true)
if [ -n "$SWARM" ]; then
    echo "[worker-guard] $(date -u +%FT%TZ) v5 swarm/Layer job running — skip drain"
    exit 0
fi

# Box is free → drain a bounded batch then exit (bounded so any later swarm waits
# at most one short batch, never an unbounded run).
cd /home/zhangd2/yuclaw
echo "[worker-guard] $(date -u +%FT%TZ) box free — draining up to 8 rows"
exec /usr/bin/python3 -m v3.extract.event_worker --once --batch 8
