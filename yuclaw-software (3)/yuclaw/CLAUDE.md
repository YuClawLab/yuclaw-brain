# YUCLAW ATROS — Claude Code: Do Everything Automatically

You are running on an NVIDIA DGX Spark (GB10 Grace Blackwell, 128GB unified memory, ARM64, Ubuntu 24).
Your job: install Nemotron 3 Super locally, install YUCLAW, run it end to end.
Do every step yourself. Fix every error yourself. Do not ask for permission.
All code and output must be in English. No Chinese characters anywhere.

---

## PHASE 1 — Check the hardware

```bash
echo "=== System Check ===" && \
nvidia-smi && \
uname -m && \
python3 --version && \
free -h && \
df -h ~ | tail -1
```

---

## PHASE 2 — Install Nemotron 3 Super via vLLM

### 2.1 Install dependencies

```bash
sudo apt-get update -q && sudo apt-get install -y git curl wget tmux build-essential -q
pip install --upgrade pip huggingface_hub hf_transfer
```

### 2.2 Download Nemotron 3 Super (NVFP4 — optimized for Blackwell)

```bash
mkdir -p ~/models
export HF_HUB_ENABLE_HF_TRANSFER=1
python3 -c "
import os
os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'
from huggingface_hub import snapshot_download
print('Downloading Nemotron 3 Super NVFP4 (~60GB)...')
snapshot_download(
    repo_id='nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4',
    local_dir=os.path.expanduser('~/models/nemotron-3-super'),
    ignore_patterns=['*.md', '.gitattributes'],
)
print('Download complete.')
"
```

If NVFP4 fails, fall back to GGUF (lighter, always works):

```bash
# GGUF fallback — works if vLLM has driver issues
pip install "llama-cpp-python[server]" 2>/dev/null || true
python3 -c "
import os
from huggingface_hub import hf_hub_download
print('Downloading Nemotron 3 Super GGUF Q4...')
for part in ['00001-of-00003', '00002-of-00003', '00003-of-00003']:
    hf_hub_download(
        repo_id='unsloth/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF',
        filename=f'NVIDIA-Nemotron-3-Super-120B-A12B-UD-Q4_K_XL-{part}.gguf',
        local_dir=os.path.expanduser('~/models/nemotron-gguf'),
    )
print('GGUF download complete.')
" 2>/dev/null || echo "GGUF download skipped"
```

### 2.3 Install vLLM

```bash
pip install vllm 2>/dev/null || \
pip install "vllm>=0.6.0" --pre --extra-index-url https://wheels.vllm.ai/nightly/ 2>/dev/null || \
pip install vllm --upgrade --quiet
python3 -c "import vllm; print('vLLM OK:', vllm.__version__)"
```

### 2.4 Create server scripts

```bash
mkdir -p ~/yuclaw/services

cat > ~/yuclaw/services/start_super.sh << 'SCRIPT'
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
SCRIPT
chmod +x ~/yuclaw/services/start_super.sh
```

### 2.5 Start Nemotron in background via tmux

```bash
tmux new-session -d -s yuclaw-model "bash ~/yuclaw/services/start_super.sh 2>&1 | tee ~/yuclaw/services/model.log" || \
nohup bash ~/yuclaw/services/start_super.sh > ~/yuclaw/services/model.log 2>&1 &

echo "Model loading... waiting 90 seconds"
sleep 90
```

### 2.6 Verify Nemotron is alive

```bash
for i in $(seq 1 10); do
    STATUS=$(curl -s http://localhost:8001/v1/models 2>/dev/null)
    if echo "$STATUS" | grep -q "nemotron"; then
        echo "Nemotron 3 Super is RUNNING on localhost:8001"
        break
    fi
    echo "Still loading... ($i/10) checking again in 30s"
    sleep 30
done

# Test it
curl -s http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nemotron-3-super-local","messages":[{"role":"user","content":"What is EBITDA? One sentence."}],"max_tokens":80}' \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('MODEL TEST:', r['choices'][0]['message']['content'])"
```

---

## PHASE 3 — If vLLM fails, use Ollama instead (simpler fallback)

Only run this if Phase 2 vLLM fails.

```bash
curl -fsSL https://ollama.ai/install.sh | sh
sleep 3
ollama serve &
sleep 5
ollama pull llama3.1:70b
# Point YUCLAW at Ollama
sed -i 's|YUCLAW_SUPER_ENDPOINT=.*|YUCLAW_SUPER_ENDPOINT=http://localhost:11434/v1|g' ~/yuclaw/.env
sed -i 's|nemotron-3-super-local|llama3.1:70b|g' ~/yuclaw/yuclaw/core/router.py
echo "Ollama fallback configured"
```

---

## PHASE 4 — Install and configure YUCLAW

```bash
cd ~/yuclaw

# Install Python dependencies
pip install -r requirements.txt -q

# Fix any missing packages
pip install httpx pydantic aiosqlite networkx yfinance openpyxl python-dotenv rich pandas numpy 2>/dev/null
pip install PyMuPDF 2>/dev/null || pip install pymupdf 2>/dev/null || true

# Create directories
mkdir -p data/filings output

# Write .env for DGX Spark local mode
cat > .env << 'ENV'
YUCLAW_SUPER_ENDPOINT=http://localhost:8001/v1
YUCLAW_NANO_ENDPOINT=http://localhost:8001/v1
ENV

# Verify imports
python3 -c "
from yuclaw.core.router import get_router
from yuclaw.engine import YUCLAW
print('YUCLAW imports: OK')
"
```

---

## PHASE 5 — Run YUCLAW end to end

Run each command. Show the full output. Fix any error before moving to the next.

### 5.1 Research

```bash
cd ~/yuclaw
python3 yuclaw_cli.py research AAPL "Analyze investment thesis, key metrics, margin trends, risks, and catalysts"
```

### 5.2 Adversarial Validation

```bash
python3 yuclaw_cli.py validate "Buy top-decile 6-month price momentum ETFs, rebalance monthly, 5% stop-loss per position, 20% max single name"
```

### 5.3 Earnings War Room

```bash
python3 yuclaw_cli.py earnings AAPL
```

### 5.4 Scenario Shock Engine

```bash
python3 yuclaw_cli.py shock "Federal Reserve surprises markets with emergency 75bps rate hike"
```

### 5.5 Macro Event

```bash
python3 yuclaw_cli.py macro "Oil price spikes 40% due to Middle East escalation"
```

### 5.6 Portfolio Watchlist + Sentinel Scan

```bash
python3 yuclaw_cli.py watchlist add AAPL "Core holding — services margin expansion thesis"
python3 yuclaw_cli.py watchlist add NVDA "AI infrastructure — datacenter capex cycle"
python3 yuclaw_cli.py watchlist add MSFT "Cloud + Copilot — Azure growth acceleration"
python3 yuclaw_cli.py watchlist show
python3 yuclaw_cli.py scan
```

### 5.7 Factor Lab

```bash
python3 yuclaw_cli.py factor "Find the best price momentum factor for US large-cap ETFs over the past 90 days"
```

### 5.8 Audit log

```bash
python3 yuclaw_cli.py audit
```

### 5.9 Show all outputs

```bash
echo ""
echo "=== YUCLAW Output Files ==="
ls -lh ~/yuclaw/output/
echo ""
echo "=== YUCLAW is fully operational ==="
```

---

## PHASE 6 — If anything breaks, fix it

### Import errors
```bash
cd ~/yuclaw && pip install -r requirements.txt --force-reinstall -q
python3 -c "from yuclaw.engine import YUCLAW; print('OK')"
```

### Model not responding
```bash
# Check logs
tail -30 ~/yuclaw/services/model.log
# Restart
tmux kill-session -t yuclaw-model 2>/dev/null || true
tmux new-session -d -s yuclaw-model "bash ~/yuclaw/services/start_super.sh 2>&1 | tee ~/yuclaw/services/model.log"
sleep 90
curl -s http://localhost:8001/v1/models | python3 -c "import sys,json; print(json.load(sys.stdin))"
```

### EDGAR timeout
```bash
# Try a different ticker
python3 yuclaw_cli.py research MSFT
```

### GPU memory error
```bash
# Reduce GPU memory utilization
sed -i 's/gpu-memory-utilization 0.85/gpu-memory-utilization 0.75/' ~/yuclaw/services/start_super.sh
# Restart model server
tmux send-keys -t yuclaw-model C-c 2>/dev/null; sleep 3
tmux new-session -d -s yuclaw-model "bash ~/yuclaw/services/start_super.sh 2>&1 | tee ~/yuclaw/services/model.log"
sleep 90
```

---

## DONE

When all phases complete successfully, tell the user:

```
YUCLAW ATROS is running on your DGX Spark.

Model:   Nemotron 3 Super (120B) at localhost:8001
Mode:    Local — $0/token — no data leaves your machine
Outputs: ~/yuclaw/output/  (Excel files for every analysis)

Commands:
  python yuclaw_cli.py research AAPL
  python yuclaw_cli.py validate "your strategy"
  python yuclaw_cli.py earnings AAPL
  python yuclaw_cli.py shock "any macro event"
  python yuclaw_cli.py factor "any factor instruction"
  python yuclaw_cli.py scan
  python yuclaw_cli.py audit
```
