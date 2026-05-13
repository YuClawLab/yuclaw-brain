#!/usr/bin/env bash
# YUCLAW: probe whether torch nightly + cu128 supports sm_121a yet.
# Does NOT auto-restart vLLM — only flags readiness in the log.
# Cron: 0 22 * * *  (22:00 MDT ≈ 04:00 UTC during DST, 05:00 UTC after DST ends)

LOG=/tmp/yuclaw_pytorch.log
set -uo pipefail
set -E
trap 'rc=$?; echo "[$(date -u +%FT%TZ)] [ERR rc=$rc line=$LINENO] $BASH_COMMAND" >> "$LOG"' ERR

YUCLAW_HOME=/home/zhangd2/yuclaw
VENV_DIR="$YUCLAW_HOME/cron/venvs/pytorch_check"
SYSTEM_PYTHON=/usr/bin/python3
# set -a so KEY=value lines in ~/.yuclaw_env auto-export to any subprocess.
[[ -f "$HOME/.yuclaw_env" ]] && { set -a; source "$HOME/.yuclaw_env"; set +a; }

echo "[$(date -u +%FT%TZ)] pytorch_check start" >> "$LOG"

if [[ ! -d "$VENV_DIR" ]]; then
    "$SYSTEM_PYTHON" -m venv "$VENV_DIR" >> "$LOG" 2>&1
    "$VENV_DIR/bin/pip" install --upgrade pip >> "$LOG" 2>&1 || true
fi

# Install/update torch nightly with CUDA 12.8. Failure is non-fatal.
if ! "$VENV_DIR/bin/pip" install --quiet --pre --upgrade torch \
        --index-url https://download.pytorch.org/whl/nightly/cu128 >> "$LOG" 2>&1; then
    echo "[$(date -u +%FT%TZ)] pytorch_check: pip install failed (non-fatal)" >> "$LOG"
    exit 0
fi

"$VENV_DIR/bin/python" - >> "$LOG" 2>&1 <<'PY'
import sys
try:
    import torch
except Exception as e:
    print(f"torch import failed: {e}")
    sys.exit(0)

print(f"torch version: {torch.__version__}")
print(f"cuda available: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    print("CUDA not available — skipping arch test")
    sys.exit(0)

try:
    cap = torch.cuda.get_device_capability(0)
    print(f"device capability: sm_{cap[0]}{cap[1]}")
    arches = torch.cuda.get_arch_list() if hasattr(torch.cuda, "get_arch_list") else []
    print(f"compiled arches: {arches}")

    # try a small op to confirm kernels actually launch on this device
    x = torch.randn(64, 64, device="cuda")
    y = (x @ x.T).sum().item()
    print(f"matmul smoke: {y:.4f}")

    sm = f"sm_{cap[0]}{cap[1]}"
    if any("121" in a for a in arches) or sm in arches:
        print("=========================================")
        print(f"=== READY: torch nightly supports {sm} ===")
        print("=========================================")
    else:
        print(f"NOT READY: {sm} not in compiled arches yet")
except Exception as e:
    print(f"sm probe FAILED: {e}")
PY

echo "[$(date -u +%FT%TZ)] pytorch_check done" >> "$LOG"
