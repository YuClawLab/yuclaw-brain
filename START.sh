#!/bin/bash
# ─────────────────────────────────────────────────────────
#  YUCLAW — One-shot setup for NVIDIA DGX Spark
#  Run this ONCE after unzipping:
#    chmod +x START.sh && ./START.sh
# ─────────────────────────────────────────────────────────

set -e
clear

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   🦞  YUCLAW ATROS — Starting Setup       ║"
echo "║   NVIDIA DGX Spark — Grace Blackwell       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: Install Python dependencies ──────────────────
echo "[1/4] Installing Python packages..."
pip install -r requirements.txt -q
echo "      Done."

# ── Step 2: Create data and output folders ────────────────
echo "[2/4] Creating folders..."
mkdir -p data/filings output
echo "      Done."

# ── Step 3: Install Claude Code ──────────────────────────
echo "[3/4] Installing Claude Code..."
npm install -g @anthropic-ai/claude-code 2>/dev/null || {
    curl -fsSL https://nodejs.org/dist/v20.11.0/node-v20.11.0-linux-arm64.tar.xz | tar -xJ
    export PATH="$PWD/node-v20.11.0-linux-arm64/bin:$PATH"
    npm install -g @anthropic-ai/claude-code 2>/dev/null
}
echo "      Done."

# ── Step 4: Configure model endpoint ─────────────────────
echo "[4/4] Configuring model..."
echo ""

# Check if a local LLM endpoint is running. Two supported runtimes:
#   - vLLM Nemotron 3 Super 120B on port 8001 (when sm_121a is supported on the hardware)
#   - Ollama on port 11434 serving the 'nemotron-3-super-local' tag (Llama 3.1 70B with
#     a financial-analyst system prompt; this is the current default when vLLM is blocked)
if curl -s http://localhost:8001/v1/models > /dev/null 2>&1; then
    echo "      ✅ vLLM Nemotron 3 Super 120B detected at localhost:8001"
    echo "         Mode: DGX Spark local — \$0/token, nothing leaves your machine"
    sed -i 's|^# OPENROUTER_API_KEY.*||g' .env
    grep -q "YUCLAW_SUPER_ENDPOINT" .env || echo "YUCLAW_SUPER_ENDPOINT=http://localhost:8001/v1" >> .env
    grep -q "YUCLAW_NANO_ENDPOINT" .env  || echo "YUCLAW_NANO_ENDPOINT=http://localhost:8002/v1" >> .env
elif curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "      ✅ Ollama detected at localhost:11434 (will serve Llama 3.1 70B as 'nemotron-3-super-local')"
    echo "         Mode: DGX Spark local — \$0/token, nothing leaves your machine"
    sed -i 's|^# OPENROUTER_API_KEY.*||g' .env
    grep -q "YUCLAW_SUPER_ENDPOINT" .env || echo "YUCLAW_SUPER_ENDPOINT=http://localhost:11434/v1" >> .env
    grep -q "YUCLAW_SUPER_MODEL" .env    || echo "YUCLAW_SUPER_MODEL=nemotron-3-super-local" >> .env
else
    echo "      ⚠️  No local LLM runtime detected."
    echo ""
    echo "      Three options:"
    echo "      A) Start Ollama (works on any DGX Spark, including sm_121a-blocked hardware):"
    echo "         ollama serve &  &&  ollama pull llama3.1:70b"
    echo "         (then create a Modelfile with a financial-analyst system prompt and tag it"
    echo "          as 'nemotron-3-super-local' for compatibility with the existing env config)"
    echo ""
    echo "      B) Start vLLM-served Nemotron 3 Super 120B (requires sm_121a support):"
    echo "         See: https://build.nvidia.com/spark/nim-llm"
    echo ""
    echo "      C) Use the OpenRouter API (no local model needed, calls real Nemotron 3 Super 120B):"
    read -p "         Enter your OpenRouter API key (or press Enter to skip): " OR_KEY
    if [ -n "$OR_KEY" ]; then
        grep -q "OPENROUTER_API_KEY" .env && sed -i "s|OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$OR_KEY|" .env || echo "OPENROUTER_API_KEY=$OR_KEY" >> .env
        echo "         ✅ OpenRouter configured"
    else
        echo "         Skipped. Edit .env before running YUCLAW."
    fi
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅  Setup Complete!                      ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  NOW: Let Claude Code build and run YUCLAW for you."
echo ""
echo "  Run this command:"
echo ""
echo "     claude"
echo ""
echo "  Claude Code will read CLAUDE.md and run YUCLAW automatically."
echo "  Just press Enter to confirm each step it asks about."
echo ""
echo "  Or run YUCLAW directly:"
echo "     python yuclaw_cli.py research AAPL"
echo "     python yuclaw_cli.py validate \"Buy momentum ETFs monthly\""
echo "     python yuclaw_cli.py earnings AAPL"
echo "     python yuclaw_cli.py shock \"Fed raises rates 75bps\""
echo ""
