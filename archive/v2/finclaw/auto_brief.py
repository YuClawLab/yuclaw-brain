"""Auto Daily Brief — generates and saves morning briefing."""
import json, os
from datetime import datetime

YUCLAW_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(YUCLAW_ROOT, "output")


def _load(f):
    try:
        with open(os.path.join(OUTPUT_DIR, f)) as fh:
            return json.load(fh)
    except:
        return None


def generate_and_save():
    today = datetime.now().strftime("%Y-%m-%d")
    time = datetime.now().strftime("%H:%M")
    s = [f"# FINClaw Daily Brief — {today} {time} ET\n"]

    macro = _load("macro_sector_latest.json")
    if macro:
        s.append(f"## MARKET REGIME: {macro['macro']['regime']} ({macro['macro']['confidence']:.0%})")
        for imp in macro["macro"]["implications"]:
            s.append(f"- {imp}")
        s.append("")

    factors = _load("factor_scan_full.json")
    if factors:
        buys = [r for r in factors if r["signal"] in ("STRONG_BUY", "BUY")][:5]
        sells = [r for r in factors if r["signal"] in ("STRONG_SELL", "SELL")][:3]
        s.append("## TOP BUY SIGNALS")
        for r in buys:
            s.append(f"- **{r['ticker']}** {r['signal']} score:{r['score']:+.3f}")
        s.append("\n## TOP SELL SIGNALS")
        for r in sells:
            s.append(f"- **{r['ticker']}** {r['signal']} score:{r['score']:+.3f}")
        s.append("")

    bt = _load("backtest_all.json")
    if bt:
        best = max(bt, key=lambda x: x["calmar"])
        s.append(f"## BEST STRATEGY\n- **{best['name']}** Calmar:{best['calmar']} AnnRet:{best.get('annret',0):.1%}\n")

    risk = _load("risk_analysis.json")
    if risk:
        s.append("## PORTFOLIO RISK")
        for r in risk[:4]:
            s.append(f"- **{r['portfolio']}** VaR:{r['var_95']:.2%} Sharpe:{r['sharpe']:.2f}")
        s.append("")

    s.append("---\n*FINClaw powered by YUCLAW Engine | github.com/YuClawLab*")

    brief = "\n".join(s)
    os.makedirs(os.path.join(OUTPUT_DIR, "briefs"), exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "briefs", f"brief_{today}.md")
    with open(path, "w") as f:
        f.write(brief)
    with open(os.path.join(OUTPUT_DIR, "briefs", "latest.md"), "w") as f:
        f.write(brief)
    print(brief)
    return path


if __name__ == "__main__":
    p = generate_and_save()
    print(f"\nSaved: {p}")
