"""
YUCLAW MCP Server — Model Context Protocol for OpenClaw.
OpenClaw automatically uses YUCLAW for financial questions.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json, os, sys, glob
from datetime import date
sys.path.insert(0, os.path.expanduser('~/yuclaw'))

app = FastAPI(title="YUCLAW MCP Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

DATA_DIR = os.path.expanduser('~/yuclaw')

MCP_MANIFEST = {
    "schema_version": "v1",
    "name_for_human": "YUCLAW Financial Intelligence",
    "name_for_model": "yuclaw",
    "description_for_model": "Use YUCLAW for financial analysis. Provides real factor-scored signals, backtests with real prices (Calmar 3.055), market regime detection, portfolio optimization using Kelly criterion, VaR/CVaR/Sharpe risk metrics. All data is real - not LLM estimated.",
    "auth": {"type": "none"},
    "api": {"type": "openapi", "url": "http://localhost:8002/openapi.json"},
}


def _load(path):
    try:
        return json.load(open(os.path.join(DATA_DIR, path)))
    except Exception:
        return {}


@app.get("/.well-known/ai-plugin.json")
def manifest():
    return MCP_MANIFEST


@app.get("/signals")
def get_signals(limit: int = 10):
    signals = _load('output/aggregated_signals.json')
    if isinstance(signals, list):
        return {"signals": signals[:limit], "total": len(signals)}
    return {"signals": [], "error": "Run yuclaw start first"}


@app.get("/regime")
def get_regime():
    return _load('output/macro_regime.json') or {"regime": "UNKNOWN", "confidence": 0}


@app.get("/risk")
def get_risk():
    risk = _load('output/risk_analysis.json')
    if isinstance(risk, list) and risk:
        return risk[0]
    return {}


@app.get("/backtest/{ticker}")
def backtest_ticker(ticker: str, years: int = 3):
    try:
        from yuclaw.core.backtest_engine import BacktestEngine
        engine = BacktestEngine()
        return engine.backtest_ticker(ticker.upper(), years)
    except Exception as e:
        return {"error": str(e)}


@app.get("/portfolio")
def optimize_portfolio():
    try:
        signals = _load('output/aggregated_signals.json')
        from yuclaw.core.portfolio_optimizer import PortfolioOptimizer
        opt = PortfolioOptimizer()
        return opt.optimize(signals if isinstance(signals, list) else [])
    except Exception as e:
        return {"error": str(e)}


@app.get("/earnings")
def get_earnings():
    return _load('output/earnings_calendar.json') or []


@app.get("/insider")
def get_insider():
    return _load('output/insider_trades.json') or []


@app.get("/brief")
def get_brief():
    files = sorted(glob.glob(os.path.join(DATA_DIR, 'output/daily/*.txt')))
    if files:
        with open(files[-1]) as f:
            return {"brief": f.read()[:2000], "date": date.today().isoformat()}
    return {"brief": "No brief yet", "date": ""}


@app.get("/health")
def health():
    return {"status": "YUCLAW MCP running", "version": "1.1.0"}


if __name__ == '__main__':
    import uvicorn
    print("YUCLAW MCP Server starting on port 8002")
    print("OpenClaw config: add http://localhost:8002 as MCP server")
    uvicorn.run(app, host='0.0.0.0', port=8002)
