"""
YUCLAW Campus Learn — educational finance concepts.
"""

CONCEPTS = {
    'regime': {'title': 'Macro Regime', 'simple': 'Market weather. CRISIS = storms ahead. RISK_ON = sunny skies.'},
    'calmar': {'title': 'Calmar Ratio', 'simple': 'Annual Return / Maximum Drawdown. Higher = safer. Above 2.0 is excellent.'},
    'var': {'title': 'Value at Risk (VaR)', 'simple': 'Max you should expect to lose on a terrible day. VaR 95% = 95th percentile worst case.'},
    'kelly': {'title': 'Kelly Criterion', 'simple': 'Math formula for optimal bet size. Tells you exactly what % to risk per trade.'},
    'zkp': {'title': 'Zero Knowledge Proof', 'simple': 'Cryptographic proof that a decision happened at a specific time. Cannot be faked.'},
    'sharpe': {'title': 'Sharpe Ratio', 'simple': 'Risk-adjusted return. Above 1.0 is good, above 2.0 is excellent.'},
    'momentum': {'title': 'Momentum Factor', 'simple': 'Stocks that went up recently tend to keep going up. Most persistent market anomaly.'},
    'drawdown': {'title': 'Maximum Drawdown', 'simple': 'Largest peak-to-trough decline. The worst pain you would have experienced.'},
}


def explain(concept: str) -> str:
    concept = concept.lower()
    if concept in CONCEPTS:
        c = CONCEPTS[concept]
        return f"\n  {c['title']}\n  {c['simple']}\n"
    return f"Concept '{concept}' not found. Try: " + ', '.join(CONCEPTS.keys())


def list_concepts():
    print("\nYUCLAW Learn — Core Concepts")
    print("=" * 50)
    for key, val in CONCEPTS.items():
        print(f"  yuclaw learn {key:10} — {val['title']}")
