#!/usr/bin/env python3
"""Dashboard engine — regenerates docs/index.html from latest data."""
import json, os
from datetime import datetime

os.chdir(os.path.expanduser("~/yuclaw"))

def load(name):
    try:
        return json.load(open(f"output/{name}.json"))
    except:
        return None

macro = load("macro_sector_latest") or {"macro": {"regime": "UNKNOWN", "confidence": 0, "implications": []}, "sectors": []}
factors = load("factor_scan_full") or []
backtest = load("backtest_all") or []
risk = load("risk_analysis") or []

regime = macro["macro"]["regime"]
conf = macro["macro"]["confidence"]
implications = macro["macro"]["implications"]
sectors = macro["sectors"]
buys = [r for r in factors if r["signal"] in ("STRONG_BUY", "BUY")][:10]
strategies = sorted(backtest, key=lambda x: x["calmar"], reverse=True)[:5]
rc = {"CRISIS": "#ff2244", "RISK_OFF": "#ff8800", "TRANSITIONAL": "#ffcc00", "RISK_ON": "#44ff88", "GOLDILOCKS": "#00aaff"}.get(regime, "#888")

def rows(items, fmt):
    return "".join(fmt(i) for i in items)

html = f"""<!DOCTYPE html><html><head><meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1"><meta http-equiv=refresh content=1800><title>FINClaw Live</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#080810;color:#e0e0e0;font-family:'Courier New',monospace;padding:20px}}.logo{{font-size:28px;font-weight:bold;color:#ffd700;letter-spacing:3px}}.sub{{font-size:12px;color:#444;margin:4px 0 20px}}.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}.c{{background:#0d0d1a;border:1px solid #1a1a2e;border-radius:8px;padding:18px}}.t{{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:2px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #1a1a2e}}.reg{{font-size:32px;font-weight:bold;color:white;background:{rc};padding:10px 20px;border-radius:4px;display:inline-block}}.r{{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #111;font-size:13px}}.r:last-child{{border:none}}.b{{color:#44ff88}}.s{{color:#ff4455}}.n{{color:#ffaa00}}.f{{text-align:center;font-size:11px;color:#333;border-top:1px solid #1a1a2e;padding-top:15px;margin-top:20px}}.f a{{color:#555}}.d{{display:inline-block;width:8px;height:8px;background:#44ff88;border-radius:50%;margin-right:6px;animation:p 2s infinite}}@keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}</style></head>
<body>
<div class=logo>FINClaw</div>
<div class=sub><span class=d></span>YUCLAW Engine | DGX Spark GB10 | {datetime.now().strftime('%Y-%m-%d %H:%M')} ET | <a href=https://github.com/YuClawLab style=color:#555>GitHub</a></div>
<div class=g>
<div class=c><div class=t>Market Regime</div><div class=reg>{regime}</div><div style="font-size:13px;color:#888;margin-top:8px">{conf:.0%} confidence</div><div style=margin-top:12px>{rows(implications, lambda i: f'<div style="padding:5px 0;font-size:13px;color:#bbb">-> {i}</div>')}</div></div>
<div class=c><div class=t>Buy Signals ({len(buys)})</div>{rows(buys, lambda r: f'<div class=r><span class=b>{r["ticker"]}</span><span style="color:#555;font-size:11px">{r["signal"]}</span><span>{r["score"]:+.3f}</span></div>')}</div>
<div class=c><div class=t>Strategies (Real Calmar)</div>{rows(strategies, lambda s: f'<div class=r><span>{s["name"]}</span><span style="color:{"#44ff88" if s["calmar"]>2 else "#ffaa00"}">{s["calmar"]:.3f}</span><span style="color:#666">{s.get("annret",0):.1%}</span></div>')}</div>
<div class=c><div class=t>Portfolio Risk</div>{rows(risk[:6], lambda r: f'<div class=r><span>{r["portfolio"]}</span><span style="color:#ff8888">VaR:{r["var_95"]:.2%}</span><span style="color:#88ff88">S:{r["sharpe"]:.2f}</span></div>')}</div>
<div class=c><div class=t>Sectors</div>{rows(sectors[:8], lambda s: f'<div class=r><span style="color:#666">{s["rank"]}.</span><span>{s["sector"]}</span><span class="{"b" if s["signal"]=="OVERWEIGHT" else "s" if s["signal"]=="UNDERWEIGHT" else "n"}">{s["signal"]}</span></div>')}</div>
<div class=c><div class=t>System</div><div class=r><span>Engines</span><span class=b>10 RUNNING</span></div><div class=r><span>Model</span><span class=n>llama3.1:70b local</span></div><div class=r><span>Hardware</span><span style=color:#76b900>DGX Spark GB10</span></div></div>
</div>
<div class=f>FINClaw | <a href=https://github.com/YuClawLab>github.com/YuClawLab</a> | Zero LLM estimation in quant</div>
</body></html>"""

os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w") as f:
    f.write(html)
# Also copy to git repo
os.makedirs(os.path.expanduser("~/Yuclaw/docs"), exist_ok=True)
with open(os.path.expanduser("~/Yuclaw/docs/index.html"), "w") as f:
    f.write(html)
print(f"Dashboard: {regime} | {len(buys)} BUY | {len(strategies)} strategies")
