"""Ticker universes for YUCLAW."""

DAILY_CORE = [
    "AAPL", "NVDA", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AMD", "ARM", "PLTR",
    "SMCI", "DELL", "HPE", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "QCOM", "INTC",
    "LUNR", "RKLB", "ASTS", "NNE", "OKLO", "SMR", "CCJ", "CRCL", "COIN", "MSTR",
    "HOOD", "APP", "HIMS", "LLY", "NVO", "MRNA", "BNTX", "REGN", "VRTX",
]

FACTOR_UNIVERSE = DAILY_CORE + [
    "SPY", "QQQ", "SOXL", "GLD", "SLV", "TLT", "XBI", "ARKK", "TQQQ", "IEF",
]

ETF_UNIVERSE = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "XLK", "XLF", "XLE", "XLV", "XLI",
    "XLP", "XLU", "XLY", "XLB", "XLRE", "TLT", "GLD", "SLV", "VNQ", "HYG",
    "ARKK", "SOXL", "XBI", "TQQQ", "TAN", "ICLN", "LIT",
]
