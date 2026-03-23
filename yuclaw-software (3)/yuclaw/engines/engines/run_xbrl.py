#!/usr/bin/env python3
"""XBRL engine — pulls real financials from SEC for 25 companies."""
import sys, json, os, asyncio
sys.path.insert(0, os.path.expanduser("~/yuclaw"))
os.makedirs("output", exist_ok=True)

from yuclaw.data.parsers.xbrl_parser import XBRLParser

TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AMD",
           "JPM", "GS", "LLY", "NVO", "MRNA", "XOM", "CVX", "ARM", "PLTR",
           "SMCI", "MU", "AMAT", "V", "MA", "COST", "WMT", "NKE"]

async def main():
    p = XBRLParser()
    results = []
    for t in TICKERS:
        try:
            f = await p.get_financials(t)
            if f.revenue:
                gm = f.gross_profit / f.revenue if f.gross_profit and f.revenue else None
                results.append({
                    "ticker": t, "revenue": f.revenue, "net_income": f.net_income,
                    "gross_margin": round(gm, 3) if gm else None,
                    "eps": f.eps_diluted, "total_assets": f.total_assets, "real": True,
                })
                print(f"{t:6}: Rev=${f.revenue/1e9:.1f}B" + (f" GM={gm:.1%}" if gm else ""))
        except Exception as e:
            print(f"{t:6}: error {e}")
    json.dump(results, open("output/xbrl_financials.json", "w"), indent=2)
    print(f"\nXBRL: {len(results)} companies with real SEC data")

asyncio.run(main())
