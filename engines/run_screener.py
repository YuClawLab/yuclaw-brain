#!/usr/bin/env python3
"""Screener engine — scores all tickers with buy/sell signals."""
import sys, json, os
import numpy as np
import yfinance as yf

sys.path.insert(0, os.path.expanduser("~/yuclaw"))
os.makedirs("output", exist_ok=True)

from yuclaw.universe import DAILY_CORE


def screen(t):
    try:
        h = yf.Ticker(t).history(period="1y")
        info = yf.Ticker(t).info
        if h.empty or len(h) < 30:
            return None
        c = h["Close"]
        r = c.pct_change().dropna()
        m1 = float(c.iloc[-1] / c.iloc[-22] - 1) if len(c) >= 22 else 0
        m3 = float(c.iloc[-1] / c.iloc[-66] - 1) if len(c) >= 66 else 0
        r90 = r.tail(90)
        sh = float(r90.mean() / r90.std() * np.sqrt(252)) if len(r90) >= 30 and r90.std() > 0 else 0
        p90 = c.tail(90)
        dd = float(((p90 - p90.cummax()) / p90.cummax()).min())
        cal = float(r90.mean() * 252 / abs(dd)) if dd != 0 else 0
        dlt = c.diff()
        g = dlt.where(dlt > 0, 0).rolling(14).mean()
        l = (-dlt.where(dlt < 0, 0)).rolling(14).mean()
        rsi = float((100 - 100 / (1 + g / l)).iloc[-1]) if not g.empty else 50

        score = (min(max(m1 * 10, -1), 1) * 0.3
                 + min(max(m3 * 5, -1), 1) * 0.2
                 + min(max(sh / 3, -1), 1) * 0.2
                 + min(max(cal / 3, -1), 1) * 0.15
                 + (1 if rsi < 30 else -1 if rsi > 70 else 0) * 0.15)

        sig = ("STRONG_BUY" if score > 0.5 else "BUY" if score > 0.2
               else "HOLD" if score > -0.2 else "SELL" if score > -0.5
               else "STRONG_SELL")

        return {"ticker": t, "signal": sig, "score": round(score, 3),
                "price": info.get("currentPrice"), "mom_1m": round(m1, 3),
                "rsi": round(rsi, 1), "calmar_90d": round(cal, 3), "is_real": True}
    except Exception:
        return None


results = [r for t in DAILY_CORE if (r := screen(t))]
results.sort(key=lambda x: x["score"], reverse=True)
json.dump(results, open("output/screener_latest.json", "w"), indent=2)

buys = [r for r in results if r["signal"] in ("STRONG_BUY", "BUY")]
print(f"Screener: {len(results)} instruments, {len(buys)} BUY signals")
for r in buys[:5]:
    print(f"  {r['ticker']:6} {r['signal']:12} {r['score']:+.3f} RSI:{r['rsi']}")
