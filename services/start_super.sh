#!/bin/bash
echo "Starting Nemotron 3 Super on port 8001..."
python3 -m vllm.entrypoints.openai.api_server \
    --model ~/models/nemotron-3-super \
    --served-model-name nemotron-3-super-local \
    --dtype auto \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.85 \
    --port 8001 \
    --host 0.0.0.0 \
    --trust-remote-code
