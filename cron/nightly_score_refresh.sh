#!/usr/bin/env bash
# YUCLAW: nightly score regeneration. Runs 5 upstream engines + aggregator in order.
# Cron: 0 18 * * 1-5  (18:00 MDT weekdays ≈ ~2h after US equity close)
# Designed to be idempotent and continue past individual step failures.

LOG=/tmp/yuclaw_nightly.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
PYTHON=/usr/bin/python3
# set -a so KEY=value lines in ~/.yuclaw_env auto-export to the Python engine subprocesses.
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

cd "$YUCLAW_HOME"

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

run_step() {
    local name="$1"; shift
    log "==> $name START"
    if timeout 600 "$@" >> "$LOG" 2>&1; then
        log "<== $name OK"
    else
        local rc=$?
        log "<== $name FAILED (rc=$rc)"
    fi
}

log "=== nightly_score_refresh start ==="
START_EPOCH=$(date +%s)

# Engines run sequentially. Individual failures do not break the chain.
run_step "run_macro"           "$PYTHON" engines/run_macro.py
# Expose macro regime as a flat JSON for the many readers that expect macro_regime.json
# (refresh_dashboard.sh, cli_v2.py, mcp_server, daemon, etc.). One-liner shim.
run_step "expose_macro_regime" "$PYTHON" -c "import json; d=json.load(open('output/macro_sector_latest.json')); json.dump(d['macro'], open('output/macro_regime.json','w'), indent=2)"
run_step "run_factor_scan"     "$PYTHON" engines/run_factor_scan.py
run_step "run_backtest"        "$PYTHON" engines/run_backtest.py
run_step "run_risk"            "$PYTHON" engines/run_risk.py
run_step "run_screener"        "$PYTHON" engines/run_screener.py
run_step "signal_aggregator"   "$PYTHON" yuclaw/modules/signal_aggregator.py

# Sector + earnings: both write output/*.json that rebuild_html.py renders, but
# neither was previously scheduled — outputs had been frozen at 2026-03-31 for 44 days.
# Same class of bug as the original oil + signal_aggregator freezes.
run_step "sector_rotation"     "$PYTHON" -m yuclaw.modules.sector_rotation_v2
run_step "earnings_engine"     "$PYTHON" -m yuclaw.modules.earnings_engine

# Capture pipeline runtime + measure live Ollama tokens/sec for the dashboard stat cards.
# Replaces the previously-hardcoded "18.9 TOK/S" and "1.37ms LATENCY" inline strings.
ELAPSED=$(( $(date +%s) - START_EPOCH ))
run_step "inference_stats"     "$PYTHON" -m yuclaw.utils.inference_speed "$ELAPSED"

log "=== nightly_score_refresh done (cycle=${ELAPSED}s) ==="
