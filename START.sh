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

# Check if local Nemotron is running
if curl -s http://localhost:8001/v1/models > /dev/null 2>&1; then
    echo "      ✅ Local Nemotron 3 Super detected at localhost:8001"
    echo "         Mode: DGX Spark local — \$0/token, nothing leaves your machine"
    sed -i 's|^# OPENROUTER_API_KEY.*||g' .env
    grep -q "YUCLAW_SUPER_ENDPOINT" .env || echo "YUCLAW_SUPER_ENDPOINT=http://localhost:8001/v1" >> .env
    grep -q "YUCLAW_NANO_ENDPOINT" .env  || echo "YUCLAW_NANO_ENDPOINT=http://localhost:8002/v1" >> .env
else
    echo "      ⚠️  Local model not running."
    echo ""
    echo "      Two options:"
    echo "      A) Start Nemotron locally (recommended for DGX Spark):"
    echo "         See: https://build.nvidia.com/spark/nim-llm"
    echo ""
    echo "      B) Use free OpenRouter API (no local model needed):"
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
