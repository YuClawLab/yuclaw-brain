#!/bin/bash
# YUCLAW — One-command install for NVIDIA DGX Spark (Ubuntu 24, ARM64)
# Run: chmod +x install.sh && ./install.sh

set -e
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   YUCLAW ATROS — Installing               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Python deps
pip install -r requirements.txt

# Create data and output dirs
mkdir -p data/filings output

# Check which mode to use
if [ -n "$YUCLAW_SUPER_ENDPOINT" ]; then
    echo "[OK] Local LLM mode — using endpoint at $YUCLAW_SUPER_ENDPOINT"
    echo "     (default config serves Llama 3.1 70B via Ollama as the 'nemotron-3-super-local' tag;"
    echo "      vLLM-served Nemotron 3 Super 120B available when sm_121a is supported)"
elif [ -n "$OPENROUTER_API_KEY" ]; then
    echo "[OK] OpenRouter mode — using Nemotron 3 Super 120B via cloud API"
else
    echo ""
    echo "[!] No model endpoint configured."
    echo "    Edit .env and set either:"
    echo "    YUCLAW_SUPER_ENDPOINT=http://localhost:8001/v1  (DGX Spark)"
    echo "    OPENROUTER_API_KEY=your_free_key               (cloud fallback)"
    echo ""
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Installation complete!                   ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  HOW TO USE:"
echo ""
echo "  Research a company:"
echo "    python yuclaw_cli.py research AAPL"
echo ""
echo "  Validate a strategy (Red Team attack):"
echo '    python yuclaw_cli.py validate "Buy momentum ETFs monthly rebalance"'
echo ""
echo "  Analyze a macro event:"
echo '    python yuclaw_cli.py macro "Fed raises rates 75bps"'
echo ""
echo "  Generate + validate a strategy:"
echo '    python yuclaw_cli.py strategy "Find best ETF momentum factor"'
echo ""
echo "  See your watchlist:"
echo "    python yuclaw_cli.py watchlist show"
echo ""
echo "  See audit log:"
echo "    python yuclaw_cli.py audit"
echo ""
