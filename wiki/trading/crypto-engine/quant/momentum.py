#!/usr/bin/env python3
"""
Quant Module #3 — Momentum / Trend Following
===============================================
MA crossovers (9/21 EMA, 50/200 SMA), ADX trend strength,
Donchian channel breakouts, MACD histogram acceleration.

Edge: Trend-following in strong regimes. ADX > 25 = trade in direction.
      EMA cross + volume confirmation = high-conviction entry.

Usage:
    python3 momentum.py BTC-USD
    python3 momentum.py --all
    python3 momentum.py --json
"""

import sys
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

try:
    import yfinance as yf
except ImportError:
    print("yfinance required", file=sys.stderr)
    sys.exit(1)

try:
    from tickers import QUANT_UNIVERSE as SYMBOLS
except Exception:
    SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD"]
PERIOD = "120d"

# ── Compute ───────────────────────────────────────────────────────────

def fetch(symbol):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Kalman-smooth close prices
    try:
        from kalman_filter import kalman_smooth
        raw = df["Close"].values.astype(float)
        df["Close"] = kalman_smooth(raw)
    except Exception:
        pass
    
    return df

def ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average."""
    alpha = 2 / (period + 1)
    result = np.zeros_like(data)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
    return result

def sma(data: np.ndarray, period: int) -> np.ndarray:
    return np.convolve(data, np.ones(period)/period, mode='same')

def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14):
    """Compute ADX (trend strength)."""
    n = len(close)
    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        plus_dm[i] = up if up > down and up > 0 else 0
        minus_dm[i] = down if down > up and down > 0 else 0

    # Wilder smoothing
    atr = np.zeros(n)
    plus_di = np.zeros(n)
    minus_di = np.zeros(n)
    for i in range(period, n):
        atr[i] = np.mean(tr[i-period+1:i+1])
        plus_di[i] = 100 * np.mean(plus_dm[i-period+1:i+1]) / max(atr[i], 1e-10)
        minus_di[i] = 100 * np.mean(minus_dm[i-period+1:i+1]) / max(atr[i], 1e-10)

    dx = np.where((plus_di + minus_di) > 0, abs(plus_di - minus_di) / (plus_di + minus_di) * 100, 0)
    adx_val = np.zeros(n)
    for i in range(period*2, n):
        adx_val[i] = np.mean(dx[i-period+1:i+1])

    return adx_val, plus_di, minus_di

def macd(close: np.ndarray, fast=12, slow=26, signal=9):
    """MACD line, signal line, histogram."""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def donchian(high: np.ndarray, low: np.ndarray, period: int = 20):
    """Donchian channel (highest high, lowest low)."""
    upper = np.zeros_like(high)
    lower = np.zeros_like(low)
    mid = np.zeros_like(high)
    for i in range(period, len(high)):
        upper[i] = np.max(high[i-period:i])
        lower[i] = np.min(low[i-period:i])
        mid[i] = (upper[i] + lower[i]) / 2
    return upper, lower, mid


def score_momentum(close, high, low, volume) -> Dict:
    i = -1
    price = close[i]

    # EMA crosses
    ema9 = ema(close, 9)
    ema21 = ema(close, 21)
    ema50 = sma(close, 50)
    ema200 = sma(close, 200)

    ema9_21_cross = ema9[i] > ema21[i] and ema9[i-1] <= ema21[i-1]  # bullish cross
    ema9_21_cross_bear = ema9[i] < ema21[i] and ema9[i-1] >= ema21[i-1]

    # ADX
    adx_val, plus_di, minus_di = adx(high, low, close)
    adx_now = adx_val[i] if not np.isnan(adx_val[i]) else 15
    adx_bull = plus_di[i] > minus_di[i]

    # MACD
    macd_line, signal_line, hist = macd(close)
    macd_bull = hist[i] > 0
    macd_accel = hist[i] > hist[i-1] if i > 0 else False

    # Donchian
    dc_upper, dc_lower, dc_mid = donchian(high, low)
    dc_breakout = close[i] > dc_upper[i-1]  # broke above channel
    dc_breakdown = close[i] < dc_lower[i-1]

    # Volume
    avg_vol = np.mean(volume[-20:])
    vol_ratio = volume[i] / avg_vol if avg_vol > 0 else 1.0

    # Score
    score = 50  # baseline

    if ema9_21_cross:
        score += 15 if vol_ratio > 1.2 else 8
    if ema9_21_cross_bear:
        score -= 10

    if adx_now > 25:
        if adx_bull:
            score += 10
        else:
            score -= 10
    elif adx_now > 20:
        score += 0  # transitional

    if macd_bull and macd_accel:
        score += 10
    elif not macd_bull:
        score -= 5

    if dc_breakout:
        score += 15 if vol_ratio > 1.5 else 8
    if dc_breakdown:
        score -= 10

    if price > ema200[i]:
        score += 10  # above 200 SMA — bull regime
    elif price < ema200[i]:
        score -= 10  # below 200 SMA — bear regime

    score = max(0, min(100, score))

    if score >= 70:
        direction = "BULLISH" if adx_bull else "BEARISH_TREND"
        size = 25
    elif score >= 55:
        direction = "SLIGHTLY_BULLISH"
        size = 15
    elif score <= 30:
        direction = "BEARISH"
        size = 0
    else:
        direction = "NEUTRAL"
        size = 0

    return {
        "symbol": None,
        "close": round(float(price), 2),
        "edge_score": score,
        "direction": direction,
        "recommended_size_pct": size,
        "stop_level": round(float(dc_lower[i]), 2) if direction == "BULLISH" else round(float(dc_upper[i]), 2),
        "metrics": {
            "ema9_21_cross": "bullish" if ema9_21_cross else ("bearish" if ema9_21_cross_bear else "none"),
            "adx": round(float(adx_now), 1),
            "adx_bias": "bull" if adx_bull else "bear",
            "macd_bull": bool(macd_bull),
            "macd_accel": bool(macd_accel),
            "donchian_breakout": bool(dc_breakout),
            "price_vs_200sma": "above" if price > ema200[i] else "below",
            "volume_ratio": round(float(vol_ratio), 2),
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
    }


def analyze(symbol):
    df = fetch(symbol)
    if df is None:
        return None
    close = df["Close"].values.astype(float)
    high = df["High"].values.astype(float)
    low = df["Low"].values.astype(float)
    volume = df["Volume"].values.astype(float)
    r = score_momentum(close, high, low, volume)
    r["symbol"] = symbol
    return r


def main():
    json_mode = "--json" in sys.argv
    all_mode = "--all" in sys.argv
    symbols = SYMBOLS if all_mode else [sys.argv[1]] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ["BTC-USD"]

    results = [analyze(s) for s in symbols if analyze(s)]
    if json_mode:
        print(json.dumps(results if all_mode else results[0] if results else {}, indent=2))
    else:
        for r in results:
            icon = {"BULLISH": "🟢", "SLIGHTLY_BULLISH": "🟡", "NEUTRAL": "⚫", "BEARISH": "🔴", "BEARISH_TREND": "🔴"}[r["direction"]]
            print(f"{icon} {r['symbol']:10s} | Edge={r['edge_score']:3d}/100 | {r['direction']:15s} | "
                  f"Size={r['recommended_size_pct']}% | ADX={r['metrics']['adx']:.0f} "
                  f"EMA9/21={r['metrics']['ema9_21_cross']} "
                  f"MACD={'🟢' if r['metrics']['macd_bull'] else '🔴'} "
                  f"200SMA={r['metrics']['price_vs_200sma']}")


if __name__ == "__main__":
    import pandas as pd
    main()
