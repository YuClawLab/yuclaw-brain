"""
Expand signal universe from 39 to 200 tickers.
More signals = more track record = more institutional credibility.
"""
UNIVERSE_200 = [
    # Mega cap
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "BRK.B", "JPM", "V",
    # AI/Semis
    "AMD", "INTC", "QCOM", "AVGO", "MRVL", "KLAC", "AMAT", "LRCX", "ASML", "TSM",
    "MU", "SMCI", "ARM", "DELL", "HPE", "CRDO", "AMBA", "MPWR", "WOLF", "ON",
    # Biotech/Pharma
    "MRNA", "BNTX", "NVAX", "ALNY", "REGN", "VRTX", "GILD", "BIIB", "BMY",
    "PFE", "MRK", "ABBV", "LLY", "JNJ", "AMGN", "INCY", "IONS", "EXAS",
    # Space/Defense
    "LUNR", "ASTS", "RKLB", "PL", "SPCE", "BA", "LMT", "RTX", "NOC", "GD",
    "HII", "LDOS", "SAIC", "TDG", "HEI", "KTOS",
    # Energy
    "XOM", "CVX", "COP", "EOG", "PXD", "SLB", "HAL", "BKR", "DVN", "MPC",
    "PSX", "VLO", "OXY", "APA", "FANG", "MTDR", "CTRA", "SM",
    # Financials
    "GS", "MS", "BAC", "C", "WFC", "BLK", "SCHW", "AXP", "COF", "DFS",
    # Healthcare
    "UNH", "CVS", "MCK", "ABC", "CAH", "HCA", "THC", "CNC", "MOH", "ELV",
    # Tech/Cloud
    "CRM", "SNOW", "DDOG", "NET", "ZS", "CRWD", "PANW", "FTNT", "OKTA",
    "MDB", "CFLT", "GTLB", "PATH", "VEEV", "NOW", "WDAY", "ADSK",
    # Consumer
    "SHOP", "MELI", "SE", "BABA", "JD", "PDD", "ETSY", "EBAY", "W",
    # REITs/Utils
    "AMT", "CCI", "EQIX", "PLD", "O", "SPG", "AVB", "EQR", "PSA", "DLR",
    # ETFs for regime
    "SPY", "QQQ", "IWM", "TLT", "GLD", "SLV", "USO", "HYG", "LQD",
    # Crypto-adjacent
    "COIN", "MSTR", "MARA", "RIOT", "HOOD",
    # Nuclear
    "CCJ", "NNE", "OKLO", "SMR",
    # Misc growth
    "HIMS", "SOFI", "NU", "APP", "CRCL", "NVO", "CRSP", "NTLA", "RXRX",
    "SOXL", "XBI",
]

# Deduplicate
UNIVERSE_200 = list(dict.fromkeys(UNIVERSE_200))

if __name__ == '__main__':
    print(f"Universe: {len(UNIVERSE_200)} tickers")
    print("Saving universe...")
    import json, os
    os.makedirs('output', exist_ok=True)
    with open('output/universe_200.json', 'w') as f:
        json.dump(UNIVERSE_200, f, indent=2)
    print("Done")
