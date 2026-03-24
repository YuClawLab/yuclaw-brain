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
    echo "[OK] DGX Spark mode — using local Nemotron at $YUCLAW_SUPER_ENDPOINT"
elif [ -n "$OPENROUTER_API_KEY" ]; then
    echo "[OK] OpenRouter mode — using free Nemotron 3 Super API"
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
