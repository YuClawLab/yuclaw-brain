"""Institutional Brief — every claim sourced, every number traceable."""
import json, os
from datetime import datetime
from pathlib import Path

OUTPUT = Path(os.path.expanduser("~/yuclaw/output"))


def _load(name):
    try:
        return json.load(open(OUTPUT / f"{name}.json"))
    except:
        return None


def generate() -> str:
    dt = datetime.now()
    lines = [f"# FINClaw Institutional Brief", f"## {dt.strftime('%Y-%m-%d')} | {dt.strftime('%H:%M')} ET | YUCLAW Engine", "---"]

    macro = _load("macro_sector_latest")
    if macro:
        m = macro["macro"]
        lines += [f"\n## 1. MARKET REGIME: {m['regime']}",
                  f"**Confidence:** {m['confidence']:.0%} | **Source:** Live prices (SPY/TLT/GLD/UUP)", ""]
        for imp in m["implications"]:
            lines.append(f"- {imp}")
        ow = [s for s in macro["sectors"] if s["signal"] == "OVERWEIGHT"]
        uw = [s for s in macro["sectors"] if s["signal"] == "UNDERWEIGHT"]
        if ow:
            lines.append(f"\n**Overweight:** {', '.join(s['sector'] for s in ow)}")
        if uw:
            lines.append(f"**Underweight:** {', '.join(s['sector'] for s in uw)}")

    factors = _load("factor_scan_full")
    if factors:
        buys = [r for r in factors if r["signal"] in ("STRONG_BUY", "BUY")][:8]
        sells = [r for r in factors if r["signal"] in ("STRONG_SELL", "SELL")][:5]
        lines += [f"\n## 2. SIGNALS ({len(factors)} instruments)", "**Source:** 12-factor model from real price history", ""]
        if buys:
            lines.append("| Ticker | Signal | Score | RSI |")
            lines.append("|---|---|---|---|")
            for r in buys:
                lines.append(f"| {r['ticker']} | {r['signal']} | {r['score']:+.3f} | {r.get('rsi', '-')} |")

    bt = _load("backtest_all")
    if bt:
        best = sorted(bt, key=lambda x: x["calmar"], reverse=True)[:5]
        lines += [f"\n## 3. STRATEGIES (Real Backtest)", "**Source:** 15yr historical prices | Real Calmar", ""]
        lines.append("| Strategy | Calmar | MaxDD | AnnRet | Sharpe |")
        lines.append("|---|---|---|---|---|")
        for s in best:
            lines.append(f"| {s['name']} | {s['calmar']:.3f} | {s.get('maxdd',0):.1%} | {s.get('annret',0):.1%} | {s.get('sharpe',0):.2f} |")

    risk = _load("risk_analysis")
    if risk:
        lines += [f"\n## 4. RISK", "**Source:** 2yr historical VaR simulation", ""]
        lines.append("| Portfolio | VaR95 | Sharpe | MaxDD | Kelly |")
        lines.append("|---|---|---|---|---|")
        for r in risk:
            lines.append(f"| {r['portfolio']} | {r['var_95']:.2%} | {r['sharpe']:.2f} | {r['maxdd']:.1%} | {r['kelly']:.1%} |")

    lines += ["", "---", "*FINClaw | YUCLAW Engine | github.com/YuClawLab*",
              "*Every number traceable. Zero LLM estimation in quantitative components.*"]
    return "\n".join(lines)


if __name__ == "__main__":
    brief = generate()
    print(brief)
    os.makedirs(str(OUTPUT / "briefs"), exist_ok=True)
    path = OUTPUT / "briefs" / f"institutional_{datetime.now().strftime('%Y%m%d')}.md"
    path.write_text(brief)
    print(f"\nSaved: {path}")
