#!/bin/bash
# YUCLAW Dashboard Refresh — runs every 30 minutes via cron
# 1. Fetch prices  2. Build state  3. Rebuild HTML  4. Push

export PATH=/usr/bin:/usr/local/bin:$PATH
source ~/.yuclaw_env 2>/dev/null
export FINNHUB_KEY=$(grep FINNHUB_KEY ~/.yuclaw_env 2>/dev/null | tail -1 | cut -d= -f2)
export EIA_KEY=$(grep EIA_KEY ~/.yuclaw_env 2>/dev/null | tail -1 | cut -d= -f2)

cd /home/zhangd2/yuclaw

# Step 1: Fetch fresh prices
FINNHUB_KEY=$FINNHUB_KEY python3 yuclaw/data/price_verifier.py >> /tmp/dashboard_refresh.log 2>&1

# Step 2: Build dashboard_state.json
python3 -c "
import json, os
from datetime import datetime

def load(f):
    try: return json.load(open(f))
    except: return None

signals = load('output/aggregated_signals.json') or []
regime = load('output/macro_regime.json') or {}
risk = load('output/risk_analysis.json') or []
sector = load('output/sector_rotation.json') or {}
news = load('output/news_sentiment.json') or []
alerts = load('output/daemon/alerts.json') or []
memory = load('output/daemon/memory.json') or {}

state = {
    'last_updated': datetime.utcnow().isoformat(),
    'signals': [s for s in signals[:20] if s.get('price',0) > 0],
    'regime': regime,
    'risk': risk[:4] if isinstance(risk, list) else [],
    'sector': sector,
    'news': news[:8] if isinstance(news, list) else [],
    'earnings': load('output/earnings_this_week.json') or {},
    'alerts': sorted(alerts, key=lambda x: x.get('timestamp',''), reverse=True)[:5] if alerts else [],
    'memory': memory.get('daily_summaries', [])[-3:],
    'stats': {
        'total_signals': len([s for s in signals if s.get('price',0) > 0]),
        'buy_signals': len([s for s in signals if 'BUY' in s.get('signal','') and s.get('price',0) > 0]),
        'sell_signals': len([s for s in signals if 'SELL' in s.get('signal','') and s.get('price',0) > 0]),
        'verified_prices': len([s for s in signals if s.get('verified')]),
    }
}
os.makedirs('docs/data', exist_ok=True)
with open('docs/data/dashboard_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print('State: {} signals'.format(state['stats']['total_signals']))
" >> /tmp/dashboard_refresh.log 2>&1

# Step 3: Rebuild index.html from data — no JS hydration needed
python3 rebuild_html.py >> /tmp/dashboard_refresh.log 2>&1

# Step 4: Push
git add docs/index.html docs/data/dashboard_state.json output/aggregated_signals.json 2>/dev/null
git diff --cached --quiet || {
    git commit -m "auto: refresh $(date +%H:%M)" 2>/dev/null
    git push origin main 2>/dev/null
}

echo "$(date): Done" >> /tmp/dashboard_refresh.log
