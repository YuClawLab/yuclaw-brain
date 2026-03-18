#!/usr/bin/env python3
"""daily.py — Run YUCLAW daily workflow on specified tickers.

Usage: python daily.py AAPL NVDA AMD
"""
import asyncio
import sys
import os

# Load .env
from dotenv import load_dotenv
load_dotenv()

from yuclaw.engine import YUCLAW


async def main():
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["AAPL", "NVDA", "MSFT"]
    print(f"\n{'='*60}")
    print(f"  YUCLAW DAILY WORKFLOW — {', '.join(tickers)}")
    print(f"{'='*60}\n")

    yuclaw = YUCLAW()
    await yuclaw.initialize()

    for ticker in tickers:
        try:
            print(f"\n{'─'*60}")
            print(f"  Processing: {ticker}")
            print(f"{'─'*60}")

            # Research
            result = await yuclaw.research(ticker, f"Full investment analysis: thesis, margins, moat, risks, catalysts")
            bull = result.get("thesis", {}).get("bull", "N/A")
            bear = result.get("thesis", {}).get("bear", "N/A")
            print(f"  Bull: {bull[:80]}")
            print(f"  Bear: {bear[:80]}")

        except Exception as e:
            print(f"  ERROR on {ticker}: {e}")

    # Show outputs
    print(f"\n{'='*60}")
    print(f"  DAILY WORKFLOW COMPLETE")
    print(f"{'='*60}")
    print(f"\nOutput files:")
    for f in sorted(os.listdir("output")):
        if f.endswith(".xlsx"):
            print(f"  {f}")

    await yuclaw.close()


if __name__ == "__main__":
    asyncio.run(main())
