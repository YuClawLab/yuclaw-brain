#!/usr/bin/env python3
"""
YUCLAW ATROS — Command Line Interface
======================================

RESEARCH
  python yuclaw_cli.py research AAPL
  python yuclaw_cli.py research AAPL "What is the Services margin trend?"
  python yuclaw_cli.py earnings AAPL
  python yuclaw_cli.py history AAPL

VALIDATION
  python yuclaw_cli.py validate "Buy 6-month momentum ETFs, rebalance monthly, 5% stop-loss"
  python yuclaw_cli.py factor "Find best price momentum factor for US equity ETFs"
  python yuclaw_cli.py factor "Low volatility quality factor, quarterly rebalance" --calmar 1.2

PORTFOLIO
  python yuclaw_cli.py watchlist add AAPL "Core holding — services thesis"
  python yuclaw_cli.py watchlist show
  python yuclaw_cli.py sentinel AAPL
  python yuclaw_cli.py scan          (scan all watchlist positions)

MACRO / SCENARIOS
  python yuclaw_cli.py macro "Federal Reserve raises rates 75bps unexpectedly"
  python yuclaw_cli.py shock "Hormuz Strait blocked, oil supply disrupted"

SYSTEM
  python yuclaw_cli.py audit
  python yuclaw_cli.py plan "Analyze semiconductor sector investment thesis"

ENVIRONMENT (.env file):
  DGX Spark local:  YUCLAW_SUPER_ENDPOINT=http://localhost:8001/v1
  OpenRouter cloud: OPENROUTER_API_KEY=your_free_key_from_openrouter.ai
"""
import asyncio
import json
import sys
import os
from pathlib import Path

# Load .env
for line in Path(".env").read_text(errors="ignore").splitlines() if Path(".env").exists() else []:
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from yuclaw.engine import YUCLAW


BANNER = """
╔══════════════════════════════════════════════════════════╗
║   🦞  YUCLAW ATROS  —  Financial Intelligence System      ║
║   Cognition · Adversarial Validation · Evidence · Audit   ║
╚══════════════════════════════════════════════════════════╝
"""


def _pp(data: dict):
    """Pretty-print a dict, truncating long strings."""
    def _trim(v):
        if isinstance(v, str) and len(v) > 500:
            return v[:500] + " ...[truncated]"
        if isinstance(v, list) and len(v) > 8:
            return v[:8] + [f"...+{len(v)-8} more"]
        if isinstance(v, dict):
            return {k2: _trim(v2) for k2, v2 in v.items()}
        return v
    print(json.dumps({k: _trim(v) for k, v in data.items()}, indent=2, ensure_ascii=False))


async def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return

    cmd = args[0].lower()
    print(BANNER)

    yuclaw = YUCLAW(data_dir="data", output_dir="output")
    await yuclaw.initialize()

    try:

        # ── RESEARCH ────────────────────────────────────────────
        if cmd == "research":
            ticker = args[1].upper() if len(args) > 1 else "AAPL"
            query  = args[2] if len(args) > 2 else (
                "Analyze the investment thesis: key metrics, competitive moat, "
                "margin trends, risks, catalysts, and valuation"
            )
            result = await yuclaw.research(ticker, query)
            print("\n" + "─"*60 + f"\n  RESEARCH — {ticker}\n" + "─"*60)
            print(f"  Status:   {result.get('status','')}")
            print(f"  Evidence: {len(result.get('evidence_node_ids',[]))} anchors")
            if result.get("thesis"):
                for k, v in result["thesis"].items():
                    if v:
                        print(f"\n  {k.upper()} CASE:\n  {v[:200]}")
            if result.get("excel_path"):
                print(f"\n  📊 Excel saved: {result['excel_path']}")

        # ── EARNINGS WAR ROOM ────────────────────────────────────
        elif cmd == "earnings":
            ticker = args[1].upper() if len(args) > 1 else "AAPL"
            result = await yuclaw.earnings(ticker)
            if result.get("excel_path"):
                print(f"\n  📊 Excel saved: {result['excel_path']}")

        # ── VALIDATE ─────────────────────────────────────────────
        elif cmd == "validate":
            strategy = " ".join(args[1:]) if len(args) > 1 else (
                "Buy top-decile 6-month price momentum ETFs, rebalance monthly, 5% stop-loss per position"
            )
            result = await yuclaw.validate_strategy(strategy)
            print("\n" + "─"*60 + "\n  ADVERSARIAL VALIDATION RESULT\n" + "─"*60)
            _pp(result)
            if result.get("excel_path"):
                print(f"\n  📊 Excel saved: {result['excel_path']}")

        # ── FACTOR LAB ───────────────────────────────────────────
        elif cmd == "factor":
            # Parse --calmar flag
            calmar = 1.0
            factor_args = []
            i = 1
            while i < len(args):
                if args[i] == "--calmar" and i+1 < len(args):
                    calmar = float(args[i+1])
                    i += 2
                else:
                    factor_args.append(args[i])
                    i += 1
            instruction = " ".join(factor_args) if factor_args else (
                "Find the best price momentum factor for US equity ETFs over the past 90 days"
            )
            result = await yuclaw.factor(instruction, calmar_threshold=calmar)
            print("\n" + "─"*60 + "\n  FACTOR LAB RESULT\n" + "─"*60)
            print(f"  Factor:    {result.get('factor',{}).get('factor_name','')}")
            print(f"  Verdict:   {result.get('execution_recommendation','')}")
            print(f"  Calmar:    {result.get('validation',{}).get('calmar_ratio','')}")
            print(f"  Survival:  {result.get('validation',{}).get('survival_rate','')}")
            if result.get("validation",{}).get("fatal_scenarios"):
                print("\n  Fatal scenarios:")
                for s in result["validation"]["fatal_scenarios"][:3]:
                    print(f"    ✗ {s[:70]}")

        # ── MACRO ────────────────────────────────────────────────
        elif cmd == "macro":
            event = " ".join(args[1:]) if len(args) > 1 else "Federal Reserve raises rates 75bps"
            result = await yuclaw.macro_event(event)
            print("\n" + "─"*60 + "\n  MACRO EVENT ANALYSIS\n" + "─"*60)
            _pp(result)

        # ── SHOCK ENGINE ─────────────────────────────────────────
        elif cmd == "shock":
            event = " ".join(args[1:]) if len(args) > 1 else "Major oil supply disruption"
            result = await yuclaw.shock(event)

        # ── SENTINEL ─────────────────────────────────────────────
        elif cmd == "sentinel":
            ticker = args[1].upper() if len(args) > 1 else None
            if ticker:
                result = await yuclaw.sentinel(ticker)
                _pp(result)
            else:
                print("Usage: python yuclaw_cli.py sentinel AAPL")

        elif cmd == "scan":
            await yuclaw.sentinel_scan()

        # ── WATCHLIST ────────────────────────────────────────────
        elif cmd == "watchlist":
            sub = args[1].lower() if len(args) > 1 else "show"
            if sub == "add":
                ticker = args[2].upper() if len(args) > 2 else "AAPL"
                notes  = " ".join(args[3:]) if len(args) > 3 else ""
                await yuclaw.add_to_watchlist(ticker, notes)
                print(f"  ✅ Added {ticker} to watchlist")
            elif sub == "show":
                wl = await yuclaw.get_watchlist()
                print(f"\n  WATCHLIST ({len(wl)} positions):")
                if wl:
                    for item in wl:
                        print(f"    {item['ticker']:8} — {item['added_at'][:10]}  {item['notes'][:50]}")
                else:
                    print("    Empty. Add: python yuclaw_cli.py watchlist add AAPL")

        # ── HISTORY ──────────────────────────────────────────────
        elif cmd == "history":
            ticker = args[1].upper() if len(args) > 1 else "AAPL"
            history = await yuclaw.get_thesis_history(ticker)
            print(f"\n  THESIS HISTORY — {ticker} ({len(history)} records):")
            if history:
                for h in history:
                    status_icon = "✅" if h["status"] == "active" else "⚠️" if h["status"] == "under_review" else "❌"
                    print(f"    {status_icon} [{h['created']}] {h['status']:14} {h['thesis'][:80]}")
                    if h.get("assumptions"):
                        for a in h["assumptions"][:2]:
                            print(f"              ▸ {a[:70]}")
            else:
                print(f"    No history. Run: python yuclaw_cli.py research {ticker}")

        # ── AUDIT ────────────────────────────────────────────────
        elif cmd == "audit":
            log = await yuclaw.get_audit_log()
            print(f"\n  AUDIT LOG ({len(log)} records):")
            print(f"  {'Receipt ID':35} {'Verdict':10} {'Calmar':6}  Hash")
            print("  " + "─"*75)
            for entry in log[:20]:
                icon = "✅" if "APPROVED" in entry.get("verdict","") or "passed" in entry.get("verdict","").lower() else "❌"
                print(f"  {icon} {entry.get('receipt_id','')[:33]:35} {'OK' if icon=='✅' else 'FAIL':10} "
                      f"{entry.get('calmar',0):6.2f}  {entry.get('hash','')}")
            if not log:
                print("    No records yet. Run a validation first.")

        # ── PLAN ─────────────────────────────────────────────────
        elif cmd == "plan":
            request = " ".join(args[1:]) if len(args) > 1 else "Analyze Apple investment thesis"
            result  = await yuclaw.plan(request)
            print("\n  WORK PLAN:")
            for t in result.get("tasks", []):
                print(f"    [{t['agent']:12}] {t['instruction'][:70]}")

        else:
            print(f"  Unknown command: {cmd}\n")
            print(__doc__)

    except KeyboardInterrupt:
        print("\n  Interrupted.")
    finally:
        await yuclaw.close()


if __name__ == "__main__":
    asyncio.run(main())
