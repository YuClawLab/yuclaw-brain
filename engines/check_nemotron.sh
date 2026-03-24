#!/bin/bash
# Check if PyTorch nightly supports sm_121a, auto-start Nemotron if so
cd ~/yuclaw

# Skip if Nemotron already running
curl -s http://localhost:8001/v1/models 2>/dev/null | grep -q nemotron && exit 0

# Check current torch sm support
SM_CHECK=$(python3 -c "
import torch
archs = torch.cuda.get_arch_list() if hasattr(torch.cuda, 'get_arch_list') else []
print('sm_121a' if 'sm_121a' in archs or 'sm_121' in archs else 'no')
" 2>/dev/null)

if [ "$SM_CHECK" = "no" ]; then
    echo "$(date): sm_121a not yet supported" >> /tmp/nemotron_check.log
    exit 0
fi

echo "$(date): sm_121a DETECTED — starting Nemotron" >> /tmp/nemotron_check.log
pkill -f vllm 2>/dev/null; sleep 3

export C_INCLUDE_PATH="$HOME/include/python3.12"
export LD_LIBRARY_PATH="/usr/local/cuda/targets/sbsa-linux/lib:/lib/aarch64-linux-gnu:$HOME/lib"
export MAX_JOBS=1

nohup python3 -m vllm.entrypoints.openai.api_server \
    --model ~/models/nemotron-3-super \
    --served-model-name nemotron-3-super-local \
    --dtype auto --max-model-len 32768 \
    --gpu-memory-utilization 0.85 \
    --port 8001 --host 0.0.0.0 --trust-remote-code \
    > /tmp/nemotron.log 2>&1 &

echo "$(date): vLLM started PID $!" >> /tmp/nemotron_check.log
