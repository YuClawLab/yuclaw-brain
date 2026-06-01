"""
Advanced factor library — 8 new factors for better signals.
More factors = better signal quality = better track record.
"""
import numpy as np


def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    gains = deltas[deltas > 0].mean() if len(deltas[deltas > 0]) > 0 else 0
    losses = abs(deltas[deltas < 0].mean()) if len(deltas[deltas < 0]) > 0 else 0
    if losses == 0:
        return 100
    rs = gains / losses
    return 100 - (100 / (1 + rs))


def calculate_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow:
        return 0, 0
    ema_fast = np.convolve(prices[-fast:], np.ones(fast) / fast, mode='valid')[-1]
    ema_slow = np.convolve(prices[-slow:], np.ones(slow) / slow, mode='valid')[-1]
    return float(ema_fast - ema_slow), float(ema_fast)


def calculate_bollinger(prices, period=20):
    if len(prices) < period:
        return 0, 0, 0
    recent = prices[-period:]
    mean = np.mean(recent)
    std = np.std(recent)
    return float(mean + 2 * std), float(mean), float(mean - 2 * std)


def calculate_volume_score(volumes):
    if len(volumes) < 5:
        return 0
    avg = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
    recent = np.mean(volumes[-5:])
    return float((recent - avg) / avg) if avg > 0 else 0


def calculate_advanced_score(prices, volumes=None):
    if len(prices) < 30:
        return {'score': 0, 'factors': {}}

    prices = np.array(prices, dtype=float)
    factors = {}

    # RSI
    rsi = calculate_rsi(prices)
    factors['rsi'] = float(rsi)
    factors['rsi_score'] = (50 - abs(rsi - 50)) / 50

    # MACD
    macd, signal = calculate_macd(prices)
    factors['macd'] = macd
    factors['macd_score'] = 1.0 if macd > 0 else -1.0

    # Bollinger
    upper, mid, lower = calculate_bollinger(prices)
    current = prices[-1]
    if current < lower:
        factors['bollinger_score'] = 1.0
    elif current > upper:
        factors['bollinger_score'] = -1.0
    else:
        factors['bollinger_score'] = 0.0

    # Momentum 5d, 20d, 60d
    factors['mom_5d'] = float((prices[-1] - prices[-5]) / prices[-5]) if len(prices) >= 5 else 0
    factors['mom_20d'] = float((prices[-1] - prices[-20]) / prices[-20]) if len(prices) >= 20 else 0
    factors['mom_60d'] = float((prices[-1] - prices[-60]) / prices[-60]) if len(prices) >= 60 else 0

    # Volume factor
    if volumes is not None:
        factors['volume_score'] = calculate_volume_score(np.array(volumes))
    else:
        factors['volume_score'] = 0

    # Composite score
    score = (
        factors['rsi_score'] * 0.15 +
        factors['macd_score'] * 0.20 +
        factors['bollinger_score'] * 0.15 +
        np.sign(factors['mom_5d']) * 0.15 +
        np.sign(factors['mom_20d']) * 0.20 +
        np.sign(factors['mom_60d']) * 0.15
    )

    return {'score': float(score), 'factors': factors}


if __name__ == '__main__':
    import random
    prices = [100 + random.gauss(0, 2) for _ in range(100)]
    result = calculate_advanced_score(prices)
    print(f"Advanced score: {result['score']:+.3f}")
    print("Factors:", {k: f"{v:.3f}" for k, v in result['factors'].items()})
