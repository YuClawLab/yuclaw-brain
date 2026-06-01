"""Ticker universes for YUCLAW."""

DAILY_CORE = [
    "AAPL", "NVDA", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AMD", "ARM", "PLTR",
    "SMCI", "DELL", "HPE", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "QCOM", "INTC",
    "LUNR", "RKLB", "ASTS", "NNE", "OKLO", "SMR", "CCJ", "CRCL", "COIN", "MSTR",
    "HOOD", "APP", "HIMS", "LLY", "NVO", "MRNA", "BNTX", "REGN", "VRTX",
]

# 2x/3x leveraged + inverse ETFs. These distort momentum-weighted composites
# (e.g. SOXL = 3x daily semis, can post 100%+ monthly returns) and don't represent
# independent trade ideas. Excluded from FACTOR_UNIVERSE / ETF_UNIVERSE below.
# Raw lists kept intact so a reader can see what's being filtered.
LEVERAGED_ETFS = {
    'SOXL', 'SOXS', 'TQQQ', 'SQQQ', 'UPRO', 'SPXU', 'FNGU', 'FNGD',
    'BOIL', 'KOLD', 'NUGT', 'DUST', 'LABU', 'LABD', 'TNA', 'TZA',
}

FACTOR_UNIVERSE = [t for t in DAILY_CORE + [
    "SPY", "QQQ", "SOXL", "GLD", "SLV", "TLT", "XBI", "ARKK", "TQQQ", "IEF",
] if t not in LEVERAGED_ETFS]

ETF_UNIVERSE = [t for t in [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "XLK", "XLF", "XLE", "XLV", "XLI",
    "XLP", "XLU", "XLY", "XLB", "XLRE", "TLT", "GLD", "SLV", "VNQ", "HYG",
    "ARKK", "SOXL", "XBI", "TQQQ", "TAN", "ICLN", "LIT",
] if t not in LEVERAGED_ETFS]
