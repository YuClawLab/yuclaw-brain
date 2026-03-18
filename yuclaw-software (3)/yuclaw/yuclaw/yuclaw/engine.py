"""yuclaw/engine.py — The YUCLAW ATROS engine. This is the system."""
from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .core.router import get_router
from .core.ontology.models import ValidationStatus
from .core.security.injection_shield import InjectionShield
from .memory.evidence_graph import EvidenceGraph
from .memory.portfolio_memory import PortfolioMemory, ThesisRecord
from .agents.agents import CIOAgent, ResearchAgent, MacroAgent, QuantAgent
from .validation.engine import ValidationAgent
from .audit.vault import AuditVault
from .data.connectors import EDGARConnector, YahooFinanceConnector
from .output.excel import ExcelExporter
from .modules.earnings_war_room import EarningsWarRoom
from .modules.factor_lab import FactorLab
from .modules.portfolio_sentinel import PortfolioSentinel
from .modules.scenario_shock import ScenarioShockEngine


class YUCLAW:
    """
    YUCLAW ATROS — Autonomous Trading & Research Operating System.
    
    The complete system:
    - Reads financial documents with Evidence Graph anchoring
    - Remembers your thesis history across sessions
    - Validates strategies adversarially (GAN Red Team + Calmar filter)
    - Audits every decision cryptographically
    - Exports to Excel
    
    Usage:
        yuclaw = YUCLAW()
        await yuclaw.initialize()
        result = await yuclaw.research("AAPL", "Analyze latest earnings")
        result = await yuclaw.validate_strategy("Momentum ETF rotation strategy")
        result = await yuclaw.macro_event("Fed hikes 75bps")
    """

    def __init__(self, data_dir: str = "data", output_dir: str = "output"):
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self._data_dir   = data_dir
        self._output_dir = output_dir

        self._evidence   = EvidenceGraph(f"{data_dir}/evidence.db")
        self._memory     = PortfolioMemory(f"{data_dir}/portfolio.db")
        self._audit      = AuditVault(f"{data_dir}/audit.db")

        self._shield     = InjectionShield()
        self._cio        = CIOAgent()
        self._macro      = MacroAgent()
        self._quant      = QuantAgent()
        self._validator  = ValidationAgent(calmar_threshold=1.0)
        self._excel      = ExcelExporter()
        self._edgar      = EDGARConnector(f"{data_dir}/filings")
        self._yahoo      = YahooFinanceConnector()
        self._shock      = ScenarioShockEngine()

        # Modules that need memory/graph (initialized after initialize())
        self._research:   ResearchAgent | None = None
        self._earnings:   EarningsWarRoom | None = None
        self._factor_lab: FactorLab | None = None
        self._sentinel:   PortfolioSentinel | None = None

    async def initialize(self):
        await self._evidence.initialize()
        await self._memory.initialize()
        await self._audit.initialize()
        await self._validator.initialize()
        self._research   = ResearchAgent(self._evidence, self._memory)
        self._earnings   = EarningsWarRoom(self._evidence)
        self._factor_lab = FactorLab(self._validator)
        self._sentinel   = PortfolioSentinel(self._memory)
        print("[YUCLAW] System initialized. All databases ready.")
        print("[YUCLAW] Modules: Research | Earnings War Room | Factor Lab | Sentinel | Shock Engine | Validation | Audit")

    # ─── PRIMARY COMMANDS ─────────────────────────────────

    async def earnings(self, ticker: str, doc_text: str = "", export_excel: bool = True) -> dict:
        """Earnings War Room — complete earnings analysis."""
        result = await self._earnings.analyze(ticker, doc_text)
        print(self._earnings.format_console_output(result))
        if export_excel:
            xlsx_path = f"{self._output_dir}/{ticker}_{datetime.now().strftime('%Y%m%d_%H%M')}_earnings.xlsx"
            try:
                self._excel.export_research(ticker, {"summary": result.get("headline",""),
                    "key_metrics": [{"name":"Revenue","value":result.get("revenue",{}).get("actual",""),
                                     "page":1,"significance":result.get("revenue",{}).get("surprise_pct","")},
                                    {"name":"EPS","value":result.get("earnings_per_share",{}).get("actual",""),
                                     "page":1,"significance":result.get("earnings_per_share",{}).get("surprise_pct","")},
                                    {"name":"Gross Margin","value":result.get("gross_margin",{}).get("actual",""),
                                     "page":1,"significance":result.get("gross_margin",{}).get("trend","")}],
                    "thesis":{}, "key_assumptions":[], "risks":result.get("key_concerns",[]),
                    "catalysts":result.get("key_questions_for_call",[]),
                    "evidence_node_ids":result.get("evidence_node_ids",[])}, xlsx_path)
                result["excel_path"] = xlsx_path
            except Exception as e:
                print(f"  [Excel] Error: {e}")
        return result

    async def factor(self, instruction: str, calmar_threshold: float = 1.0) -> dict:
        """Factor Lab — natural language → adversarial validation → paper trading recommendation."""
        return await self._factor_lab.build_and_validate(instruction, calmar_threshold)

    async def sentinel(self, ticker: str) -> dict:
        """Check a single position for thesis integrity."""
        result = await self._sentinel.check_position(ticker)
        print(self._sentinel.format_alert(result))
        return result

    async def sentinel_scan(self) -> list[dict]:
        """Scan all watchlist positions."""
        wl = await self._memory.get_watchlist()
        if not wl:
            print("[Sentinel] Watchlist is empty. Add tickers: python yuclaw_cli.py watchlist add AAPL")
            return []
        tickers = [item["ticker"] for item in wl]
        print(f"\n[Sentinel] Scanning {len(tickers)} positions...")
        results = await self._sentinel.scan_watchlist(tickers)
        print("\n" + "═"*60)
        print("  PORTFOLIO SENTINEL SCAN RESULTS")
        print("═"*60)
        for r in results:
            print(self._sentinel.format_alert(r))
        print("═"*60)
        return results

    async def shock(self, event: str) -> dict:
        """Scenario Shock Engine — model complete impact cascade."""
        result = await self._shock.analyze(event)
        print(self._shock.format_output(result))
        return result

    async def research(
        self, ticker: str, query: str,
        save_thesis: bool = True,
        export_excel: bool = True
    ) -> dict:
        """
        Full research pipeline for a ticker.
        1. Fetch latest 10-K from EDGAR (cached)
        2. Get market snapshot from Yahoo Finance
        3. Run Research Agent with Evidence Graph anchoring
        4. Save thesis to Portfolio Memory
        5. Export to Excel
        """
        print(f"\n[Research] Starting: {ticker} — {query}")

        # Get market data
        snapshot = self._yahoo.get_snapshot(ticker)
        print(f"  Market data: {snapshot.get('short_name', ticker)} @ ${snapshot.get('price', 'N/A')}")

        # Get 10-K from EDGAR
        doc_text = ""
        doc_id   = f"{ticker.upper()}_SNAPSHOT"
        edgar_result = await self._edgar.get_10k_text(ticker)
        if edgar_result:
            doc_text, doc_id = edgar_result
            print(f"  Filing loaded: {doc_id} ({len(doc_text):,} chars)")
        else:
            # Fall back to Yahoo Finance description
            doc_text = json.dumps(snapshot)
            print(f"  No 10-K found — using market data snapshot")

        # Append snapshot data
        doc_text += f"\n\nMARKET DATA SNAPSHOT:\n{json.dumps(snapshot, indent=2)}"

        # Run Research Agent
        result = await self._research.analyze(doc_text, doc_id, ticker, query)
        print(f"  Analysis complete: {len(result.get('evidence_node_ids', []))} evidence anchors")

        # Save thesis to memory
        if save_thesis and result.get("thesis"):
            thesis_text = result["thesis"].get("base", result.get("summary", "")[:500])
            record = ThesisRecord(
                ticker=ticker.upper(),
                thesis=thesis_text,
                key_assumptions=result.get("key_assumptions", [])[:5],
                target_price=None,
                created_at=datetime.now(timezone.utc).isoformat()
            )
            await self._memory.save_thesis(record)
            print(f"  Thesis saved to Portfolio Memory")

        # Export to Excel
        if export_excel:
            xlsx_path = f"{self._output_dir}/{ticker}_{datetime.now().strftime('%Y%m%d_%H%M')}_research.xlsx"
            self._excel.export_research(ticker, result, xlsx_path)
            result["excel_path"] = xlsx_path
            print(f"  Excel: {xlsx_path}")

        return result

    async def validate_strategy(
        self, strategy_description: str,
        strategy_id: str | None = None,
        export_excel: bool = True
    ) -> dict:
        """
        Adversarial validation pipeline.
        GAN Red Team attacks the strategy. Calmar filter decides survival.
        """
        if not strategy_id:
            strategy_id = f"strat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        print(f"\n[Validation] Red Team attacking: {strategy_id}")
        print(f"  Strategy: {strategy_description[:80]}...")

        result = await self._validator.validate(strategy_id, strategy_description)

        verdict_icon = "✅ PASSED" if result["passed"] else "❌ REJECTED"
        print(f"  {verdict_icon}")
        print(f"  Calmar: {result['calmar_ratio']} | Survival: {result['survival_rate']}")
        print(f"  Killed by {result['scenarios_killed']}/{result['scenarios_tested']} scenarios")

        # Audit record
        receipt = await self._audit.record(
            strategy_id=strategy_id,
            verdict=result["verdict"],
            calmar=result["calmar_ratio"],
            reasoning=f"Adversarial validation: {result['survival_rate']} survival, "
                      f"Calmar {result['calmar_ratio']}",
            validation_status=result["status"]
        )
        result["audit_receipt"] = receipt.receipt_id
        result["audit_hash"]    = receipt.local_hash[:16] + "..."
        print(f"  Audit: {receipt.receipt_id}")

        # Export to Excel
        if export_excel:
            xlsx_path = f"{self._output_dir}/{strategy_id}_validation.xlsx"
            self._excel.export_validation_report(result, xlsx_path)
            result["excel_path"] = xlsx_path
            print(f"  Excel: {xlsx_path}")

        return result

    async def macro_event(self, event: str) -> dict:
        """Analyze a macro event — impact chains, beneficiaries, casualties."""
        print(f"\n[Macro] Analyzing: {event}")
        result = await self._macro.analyze_event(event)
        print(f"  Severity: {result.get('severity', 'unknown')}")
        if result.get("first_order_impacts"):
            for impact in result["first_order_impacts"][:3]:
                print(f"  {impact.get('asset_class','')}: {impact.get('direction','')} ({impact.get('magnitude','')})")
        return result

    async def generate_strategy(self, instruction: str) -> dict:
        """Generate a quantitative strategy specification, then validate it."""
        print(f"\n[Quant] Generating strategy: {instruction}")
        strategy = await self._quant.generate_strategy(instruction)
        desc = strategy.get("strategy_description", json.dumps(strategy))
        print(f"  Strategy: {strategy.get('strategy_name', 'unnamed')}")
        print(f"  Sending to Red Team...")
        validation = await self.validate_strategy(desc)
        return {"strategy": strategy, "validation": validation}

    async def get_watchlist(self) -> list[dict]:
        return await self._memory.get_watchlist()

    async def add_to_watchlist(self, ticker: str, notes: str = ""):
        await self._memory.add_to_watchlist(ticker, notes)
        print(f"[Watchlist] Added: {ticker}")

    async def get_thesis_history(self, ticker: str) -> list[dict]:
        records = await self._memory.get_history(ticker)
        return [
            {"created": r.created_at[:10], "status": r.status,
             "thesis": r.thesis[:120], "assumptions": r.key_assumptions[:3]}
            for r in records
        ]

    async def get_audit_log(self) -> list[dict]:
        return await self._audit.get_all()

    async def plan(self, request: str) -> dict:
        """Decompose a complex request into a work plan."""
        work_plan = await self._cio.decompose(request)
        return {
            "request": work_plan.request,
            "tasks":   [{"id": t.task_id, "agent": t.agent,
                          "instruction": t.instruction, "priority": t.priority}
                        for t in work_plan.tasks],
            "capital_limit_usd": work_plan.capital_limit_usd
        }

    async def close(self):
        await self._edgar.close()
