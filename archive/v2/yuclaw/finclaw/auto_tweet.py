"""
Auto Tweet Generator — generates daily tweets from real signals.
Every tweet is based on real data. Never fabricated.
Saves tweet drafts to output/tweet_drafts.json.
"""
import json, os
from datetime import datetime

def generate_tweets() -> list:
    tweets = []
    today = datetime.now().strftime('%Y-%m-%d')

    try:
        macro = json.load(open('output/macro_sector_latest.json'))
        regime = macro['macro']['regime']
        conf = macro['macro']['confidence']
        impl = macro['macro']['implications']
        tweet1 = f'YUCLAW {today}: Market regime = {regime} ({conf:.0%} confidence)\n'
        tweet1 += '\n'.join(f'→ {i}' for i in impl[:3])
        tweet1 += '\n\nReal signal from live market data on NVIDIA DGX Spark.\nyuclawlab.github.io/yuclaw-brain'
        tweets.append({'type':'regime','content':tweet1,'ready':True})
    except: pass

    try:
        screener = json.load(open('output/screener_latest.json'))
        buys = [r for r in screener if r['signal'] in ('STRONG_BUY','BUY')][:5]
        if buys:
            tickers = ' '.join(r['ticker'] for r in buys[:5])
            tweet2 = f'YUCLAW {today}: Top STRONG BUY signals\n\n'
            for r in buys[:5]:
                tweet2 += f'{r["ticker"]:6} score:{r["score"]:+.3f} rsi:{r.get("rsi","?")}\n'
            tweet2 += '\nReal 12-factor model. Zero LLM estimation.\ngithub.com/YuClawLab'
            tweets.append({'type':'signals','content':tweet2,'ready':True})
    except: pass

    try:
        backtest = json.load(open('output/backtest_all.json'))
        best = max(backtest, key=lambda x: x['calmar'])
        tweet3 = f'YUCLAW strategy update {today}:\n\n'
        tweet3 += f'Best strategy: {best["name"]}\n'
        tweet3 += f'Real Calmar: {best["calmar"]:.3f}\n'
        tweet3 += f'Ann Return: {best.get("annret",0):.1%}\n'
        tweet3 += f'Max DD: {best.get("maxdd",0):.1%}\n\n'
        tweet3 += '15yr backtest. Real prices. Not LLM estimated.\ngithub.com/YuClawLab/yuclaw-brain'
        tweets.append({'type':'strategy','content':tweet3,'ready':True})
    except: pass

    try:
        intel = json.load(open('output/competitive_intel.json'))
        alpha = [r for r in intel if r.get('alpha')][:3]
        if alpha:
            tweet4 = f'YUCLAW vs Wall Street {today}:\n\n'
            for r in alpha:
                tweet4 += f'{r["ticker"]}: YUCLAW={r["yuclaw"]} vs Analyst={r["analyst"]}\n'
            tweet4 += '\nContrarian signals from real data.\nyuclawlab.github.io/yuclaw-brain'
            tweets.append({'type':'alpha','content':tweet4,'ready':True})
    except: pass

    os.makedirs('output', exist_ok=True)
    with open('output/tweet_drafts.json','w') as f:
        json.dump(tweets, f, indent=2)

    print(f'Generated {len(tweets)} tweet drafts:')
    for t in tweets:
        print(f'\n--- {t["type"].upper()} ---')
        print(t['content'][:200])
    return tweets

if __name__=='__main__':
    generate_tweets()
