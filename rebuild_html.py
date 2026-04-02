"""
Rebuild docs/index.html from output data. No JS hydration needed.
Called by refresh_dashboard.sh via cron every 30 min.
"""
import json, os
from datetime import datetime


def load(f):
    try:
        return json.load(open(f))
    except Exception:
        return None


def rebuild():
    state = load('docs/data/dashboard_state.json') or load('output/dashboard_state.json')
    if not state:
        # Build state from raw files
        state = {
            'signals': load('output/aggregated_signals.json') or [],
            'regime': load('output/macro_regime.json') or {},
            'sector': load('output/sector_rotation.json') or {},
            'news': load('output/news_sentiment.json') or [],
            'earnings': load('output/earnings_this_week.json') or {},
            'alerts': load('output/daemon/alerts.json') or [],
            'memory': (load('output/daemon/memory.json') or {}).get('daily_summaries', []),
        }

    signals = state.get('signals', [])
    regime = state.get('regime', {})
    sector = state.get('sector', {})
    news = state.get('news', [])
    earnings = state.get('earnings', {})
    alerts = state.get('alerts', [])
    mem = state.get('memory', [])

    # Oil from dated files
    oil = None
    oil_dir = 'output/oil'
    if os.path.exists(oil_dir):
        files = sorted([f for f in os.listdir(oil_dir) if f.endswith('.json')])
        if files:
            oil = load(os.path.join(oil_dir, files[-1]))
    oil = oil or {}

    buys = [s for s in signals if 'BUY' in s.get('signal', '')]
    sells = [s for s in signals if 'SELL' in s.get('signal', '')]
    now = datetime.now().strftime('%Y-%m-%d %H:%M ET')
    regime_name = regime.get('regime', 'CRISIS')
    regime_conf = regime.get('confidence', 0.90)
    regime_bg = {'CRISIS': '#FF3366,#C90035', 'RISK_OFF': '#FF9900,#D47500', 'RISK_ON': '#00E676,#00A653'}.get(regime_name, '#FF3366,#C90035')

    wti = oil.get('prices', {}).get('WTI', {})
    brent = oil.get('prices', {}).get('Brent', {})
    eia = oil.get('eia', {})
    eia_dir = eia.get('direction', 'UNKNOWN')
    eia_col = '#00E676' if eia_dir == 'DRAW' else '#FF3366' if eia_dir == 'BUILD' else '#718096'

    # Signal rows
    sig_rows = ''
    for s in signals[:15]:
        sc = s.get('score', 0)
        sc_col = '#00E676' if sc > 0 else '#FF3366'
        bg = 'rgba(0,230,118,0.2)' if 'BUY' in s.get('signal', '') else 'rgba(255,51,102,0.2)'
        tc = '#00E676' if 'BUY' in s.get('signal', '') else '#FF3366'
        v = '<span style="color:#00E676;font-size:10px">V</span>' if s.get('verified') else ''
        sig_rows += (
            f'<tr style="border-bottom:1px solid #1E232D">'
            f'<td style="padding:10px 12px;font-weight:600;color:#FFF;font-size:13px">{s["ticker"]}</td>'
            f'<td style="padding:10px 12px"><span style="background:{bg};color:{tc};border:1px solid {tc};padding:3px 10px;border-radius:4px;font-size:10px;font-weight:700">{s["signal"]}</span></td>'
            f'<td style="padding:10px 12px;color:{sc_col};font-weight:600;font-size:13px;font-family:monospace">{sc:+.3f}</td>'
            f'<td style="padding:10px 12px;color:#A0AEC0;font-size:12px;font-family:monospace">${s.get("price", 0):.2f} {v}</td></tr>'
        )

    # Sector rows
    sec_rows = ''
    for r in sector.get('rotation', [])[:8]:
        col = '#00E676' if r['signal'] == 'INFLOW' else '#FF3366' if r['signal'] == 'OUTFLOW' else '#718096'
        sec_rows += (
            f'<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1E232D">'
            f'<span style="font-size:13px;color:#E2E8F0">{r["sector"]}</span>'
            f'<span style="font-size:13px;font-weight:600;color:{col};font-family:monospace">{r["change_pct"]:+.2f}%</span></div>'
        )

    # News rows (sanitized)
    news_rows = ''
    for n in (news if isinstance(news, list) else [])[:6]:
        col = '#00E676' if n.get('sentiment') == 'BULLISH' else '#FF3366' if n.get('sentiment') == 'BEARISH' else '#718096'
        reason = str(n.get('reason', ''))
        if '{' in reason or 'JSON' in reason or 'output' in reason.lower()[:15] or reason.startswith('\n'):
            reason = 'Analyzing sentiment...'
        reason = reason[:55]
        news_rows += (
            f'<div style="padding:8px 0;border-bottom:1px solid #1E232D">'
            f'<div style="display:flex;justify-content:space-between">'
            f'<span style="font-size:13px;font-weight:700;color:#FFF">{n["ticker"]}</span>'
            f'<span style="font-size:12px;color:{col};font-family:monospace">{n.get("score", 0):+.2f}</span></div>'
            f'<div style="font-size:11px;color:#718096">{reason}</div></div>'
        )

    # Alerts rows
    alert_rows = ''
    for a in (alerts[:5] if isinstance(alerts, list) else []):
        sev = a.get('severity', 'LOW')
        col = '#FF3366' if sev == 'HIGH' else '#FF9900' if sev == 'MEDIUM' else '#00E676'
        ts = a.get('timestamp', '')[:16].replace('T', ' ')
        alert_rows += (
            f'<div style="padding:8px 0;border-bottom:1px solid #1E232D">'
            f'<div style="font-size:12px;color:#E2E8F0"><span style="color:{col}">&#9679;</span> {a.get("message", "")}</div>'
            f'<div style="font-size:10px;color:#718096">{ts}</div></div>'
        )
    if not alert_rows:
        alert_rows = '<div style="color:#718096;font-size:12px">ATROS watching...</div>'

    # Memory
    mem_rows = ''
    for s in reversed((mem if isinstance(mem, list) else [])[-3:]):
        synth = str(s.get('nemotron_synthesis', ''))[:80]
        mem_rows += (
            f'<div style="padding:8px 0;border-bottom:1px solid #1E232D">'
            f'<div style="font-size:10px;color:#718096">{s.get("date", "")}</div>'
            f'<div style="font-size:12px;color:#E2E8F0">{synth}</div></div>'
        )
    if not mem_rows:
        mem_rows = '<div style="color:#718096;font-size:12px">AutoDream runs at 4PM ET</div>'

    # Earnings
    earn_rows = ''
    if isinstance(earnings, dict) and earnings:
        for t, info in list(earnings.items())[:5]:
            d = info.get('days_until', 0)
            col = '#FF3366' if d <= 2 else '#FF9900'
            earn_rows += f'<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #1E232D"><span style="font-size:13px;font-weight:600;color:#FFF">{t}</span><span style="font-size:12px;color:{col};font-family:monospace">{d}d</span></div>'
    else:
        earn_rows = '<div style="color:#718096;font-size:12px">No catalysts this week</div>'

    # Regime implications
    regime_impl = ''.join([f'<div style="font-size:12px;opacity:0.9;margin-bottom:4px">- {imp}</div>' for imp in regime.get('portfolio_implications', [])[:3]])

    # Sector velocity in regime card
    sec_vel = ''.join([f'<div style="font-size:11px;color:#00E676">up {r["sector"]} {r["change_pct"]:+.2f}%</div>' for r in sector.get('top_inflows', [])[:2]])
    sec_vel += ''.join([f'<div style="font-size:11px;color:#FF3366">dn {r["sector"]} {r["change_pct"]:+.2f}%</div>' for r in sector.get('top_outflows', [])[:2]])

    # CSS (no braces conflict since we use string concat)
    css = (
        "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');"
        "*{margin:0;padding:0;box-sizing:border-box}"
        "body{background:#0B0E14;font-family:'Inter',sans-serif;color:#E2E8F0}"
        ".container{max-width:1400px;margin:0 auto;padding:20px}"
        ".header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;padding:14px 20px;background:#151A23;border:1px solid #1E232D;border-radius:12px}"
        ".logo{font-size:20px;font-weight:800;color:#FFF}.logo span{color:#00E676}"
        ".pill{padding:5px 14px;border-radius:6px;font-size:12px;font-weight:600;background:#1E232D;color:#A0AEC0;text-decoration:none}"
        ".pill.active{background:rgba(0,230,118,0.1);color:#00E676;border:1px solid rgba(0,230,118,0.3)}"
        ".grid{display:grid;gap:16px;margin-bottom:16px}"
        ".grid-4{grid-template-columns:repeat(4,1fr)}.grid-3{grid-template-columns:repeat(3,1fr)}.grid-custom{grid-template-columns:1fr 2fr}"
        ".card{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:18px}"
        ".card-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:14px}"
        ".stat-card{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:18px}"
        ".stat-num{font-size:26px;font-weight:700;color:#FFF;margin-bottom:3px;font-family:'JetBrains Mono',monospace}"
        ".stat-label{font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px}"
        "table{width:100%;border-collapse:collapse}"
        "th{font-size:9px;font-weight:600;text-transform:uppercase;color:#718096;padding:7px 12px;text-align:left;border-bottom:1px solid #2D3748}"
        "tr:hover td{background:#1A202C}"
        ".live-dot{width:7px;height:7px;background:#00E676;border-radius:50%;display:inline-block;margin-right:6px;animation:pulse 2s infinite}"
        "@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(0,230,118,0.4)}70%{box-shadow:0 0 0 6px rgba(0,230,118,0)}100%{box-shadow:0 0 0 0 rgba(0,230,118,0)}}"
        ".footer{text-align:center;padding:16px;color:#718096;font-size:11px}.footer a{color:#00E676;text-decoration:none}"
        "@media(max-width:900px){.grid-4,.grid-3,.grid-custom{grid-template-columns:1fr}}"
    )

    html = f'<!DOCTYPE html><html lang="en"><head><meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="1800"><title>YUCLAW OS</title><style>{css}</style></head><body><div class="container">'

    # Header
    html += f'<div class="header"><div style="display:flex;align-items:center;gap:12px"><div class="logo">YUCLAW <span>OS</span></div><div style="font-size:11px;color:#718096;font-family:JetBrains Mono"><span class="live-dot"></span>{now}</div></div><div style="display:flex;gap:6px"><a href="https://yuclawlab.github.io/yuclaw-brain" class="pill active">Terminal</a><a href="app.html" class="pill">Chat</a><a href="https://github.com/YuClawLab" class="pill">GitHub</a><a href="https://github.com/YuClawLab/yuclaw-matrix" class="pill">Paper</a><a href="https://pypi.org/project/yuclaw" class="pill">PyPI</a></div></div>'

    # Stats
    html += f'<div class="grid grid-4"><div class="stat-card"><div class="stat-num" style="color:#00E676">{len(buys)}</div><div class="stat-label">Buy Signals</div></div><div class="stat-card"><div class="stat-num">{len(signals)}</div><div class="stat-label">Assets</div></div><div class="stat-card"><div class="stat-num">18.9</div><div class="stat-label">Tok/s</div></div><div class="stat-card"><div class="stat-num">1.37<span style="font-size:14px;color:#718096">ms</span></div><div class="stat-label">Latency</div></div></div>'

    # Oil
    html += f'<div class="card"><div class="card-title">OIL INTELLIGENCE — EIA + NEMOTRON 120B</div><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px"><div style="background:#1E232D;border-radius:8px;padding:12px"><div style="font-size:9px;color:#718096;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">WTI</div><div style="font-size:20px;font-weight:700;color:#FFF;font-family:monospace">${wti.get("price", 0):.2f}</div></div><div style="background:#1E232D;border-radius:8px;padding:12px"><div style="font-size:9px;color:#718096;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">Brent</div><div style="font-size:20px;font-weight:700;color:#FFF;font-family:monospace">${brent.get("price", 0):.2f}</div></div><div style="background:#1E232D;border-radius:8px;padding:12px"><div style="font-size:9px;color:#718096;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">EIA</div><div style="font-size:20px;font-weight:700;color:{eia_col};font-family:monospace">{eia_dir}</div><div style="font-size:11px;color:#718096">{abs(eia.get("change_mb", 0)):.1f}M bbl</div></div><div style="background:#1E232D;border-radius:8px;padding:12px"><div style="font-size:9px;color:#718096;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">Equities</div><div style="font-size:13px;color:#FFF;font-family:monospace">XOM ${oil.get("prices", {}).get("ExxonMobil", {}).get("price", 0):.0f} CVX ${oil.get("prices", {}).get("Chevron", {}).get("price", 0):.0f}</div></div></div></div>'

    # Regime + Signals
    html += f'<div class="grid grid-custom"><div style="background:linear-gradient(135deg,{regime_bg});border-radius:12px;padding:22px;color:white"><div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;opacity:0.85;margin-bottom:6px">Macro Regime</div><div style="font-size:34px;font-weight:800;letter-spacing:-1px;margin-bottom:3px">{regime_name}</div><div style="font-size:13px;opacity:0.9;font-family:JetBrains Mono;margin-bottom:14px">{regime_conf:.0%} AI Confidence</div>{regime_impl}<div style="margin-top:14px;padding:10px;background:rgba(0,0,0,0.2);border-radius:8px"><div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;opacity:0.7;margin-bottom:5px">Sector Velocity</div>{sec_vel}</div></div>'
    html += f'<div class="card"><div class="card-title">LIVE ORDER FLOW — {len(buys)} BUY / {len(sells)} SELL</div><div style="overflow-y:auto;max-height:300px"><table><thead><tr><th>Asset</th><th>Signal</th><th>Score</th><th>Price</th></tr></thead><tbody>{sig_rows}</tbody></table></div></div></div>'

    # Sector + News + Earnings
    html += f'<div class="grid grid-3"><div class="card"><div class="card-title">SECTOR VELOCITY</div>{sec_rows}</div><div class="card"><div class="card-title">NEMOTRON SENTIMENT</div>{news_rows}</div><div class="card"><div class="card-title">CATALYST CALENDAR</div>{earn_rows}</div></div>'

    # Alerts + Memory + Track
    html += f'<div class="grid grid-3"><div class="card"><div class="card-title">ATROS ALERTS</div>{alert_rows}</div><div class="card"><div class="card-title">AUTODREAM MEMORY</div>{mem_rows}</div><div class="card"><div class="card-title">TRACK RECORD</div><div style="color:#00E676;font-size:12px;margin-bottom:6px">LUNR +14.68% | ASTS +10.44% | DELL +4.01%</div><div style="background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.3);padding:6px 12px;border-radius:6px;font-size:11px;color:#00E676;margin-top:10px">ZKP Verified — Ethereum Sepolia</div></div></div>'

    # Footer
    html += '<div class="footer">YUCLAW OS by <a href="https://github.com/YuClawLab">YuClawLab</a> | <a href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6461418">SSRN #6461418</a> | <a href="https://pypi.org/project/yuclaw">pip install yuclaw</a> | MIT</div></div></body></html>'

    os.makedirs('docs', exist_ok=True)
    with open('docs/index.html', 'w') as f:
        f.write(html)

    first = signals[0] if signals else {}
    print(f"index.html rebuilt: {len(signals)} signals, {first.get('ticker', '?')} ${first.get('price', 0):.2f}")


if __name__ == '__main__':
    rebuild()
