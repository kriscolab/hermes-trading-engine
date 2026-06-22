#!/usr/bin/env python3
"""
Quant Module #1 — Mean Reversion
==================================
Bollinger Bands, RSI, Z-score, volume confirmation.
All computed from OHLCV (yfinance — free, no key).

Edge scoring: 0-100 based on:
  - Distance from mean (Z-score or BB position)
  - Oscillator confirmation (RSI)
  - Volume confirmation (above/below average)
  - Regime filter (trending = fade mean-reversion signals)

Usage:
    python3 mean-reversion.py BTC-USD           # Single symbol
    python3 mean-reversion.py --all             # All crypto pairs
    python3 mean-reversion.py --json            # JSON output for engine

Output: edge_score + signal + recommended_size + stop_level
"""

import sys
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import yfinance as yf
except ImportError:
    print("yfinance required: pip install yfinance", file=sys.stderr)
    sys.exit(1)

# ── Default symbols ──
try:
    from tickers import QUANT_UNIVERSE as SYMBOLS
except ImportError:
    SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD"]
EQUITY_SYMBOLS = ["XLE", "GLD", "SOXX"]
PERIOD = "90d"
INTERVAL = "1d"

# ── Compute ───────────────────────────────────────────────────────────

def fetch_ohlcv(symbol: str) -> Optional[np.ndarray]:
    """Fetch OHLCV, return DataFrame. Price data is Kalman-smoothed."""
    df = yf.download(symbol, period=PERIOD, interval=INTERVAL,
                     progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Kalman-smooth the close prices to reduce noise
    try:
        from kalman_filter import kalman_smooth
        raw_close = df["Close"].values.astype(float)
        smoothed = kalman_smooth(raw_close)
        df["Close"] = smoothed
    except Exception:
        pass  # graceful fallback if kalman_filter unavailable
    
    return df

def bollinger_bands(close: np.ndarray, period: int = 20, std_dev: float = 2.0):
    """Compute Bollinger Bands. Returns (middle, upper, lower, position_pct, width)."""
    sma = np.convolve(close, np.ones(period)/period, mode='valid')
    # Pad to match length
    sma_full = np.zeros_like(close) * np.nan
    sma_full[period-1:] = sma

    std = np.array([np.std(close[i-period+1:i+1]) for i in range(period-1, len(close))])
    std_full = np.zeros_like(close) * np.nan
    std_full[period-1:] = std

    upper = sma_full + std_dev * std_full
    lower = sma_full - std_dev * std_full

    # Position: 0 = at lower band, 100 = at upper band, 50 = at middle
    band_range = upper - lower
    position = np.where(band_range > 0, (close - lower) / band_range * 100, 50)

    # Width: band width as % of middle
    width = np.where(sma_full > 0, (upper - lower) / sma_full * 100, 0)

    return sma_full, upper, lower, position, width

def compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute RSI."""
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = np.zeros_like(close)
    avg_loss = np.zeros_like(close)

    for i in range(period, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (period-1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i-1] * (period-1) + loss[i]) / period

    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def z_score(close: np.ndarray, period: int = 20) -> np.ndarray:
    """Compute rolling Z-score of returns."""
    returns = np.diff(close, prepend=close[0]) / close
    ret = returns[1:]  # skip first

    z = np.zeros_like(close) * np.nan
    for i in range(period, len(close)):
        window = ret[i-period:i]
        mu = np.mean(window)
        sigma = np.std(window) or 1e-10
        z[i] = (ret[i-1] - mu) / sigma
    return z

def volume_ratio(volume: np.ndarray, period: int = 20) -> np.ndarray:
    """Volume ratio vs 20-period average."""
    avg_vol = np.zeros_like(volume)
    for i in range(period, len(volume)):
        avg_vol[i] = np.mean(volume[i-period:i])
    return np.where(avg_vol > 0, volume / avg_vol, 1.0)

# ── Edge Scoring ──────────────────────────────────────────────────────

def score_edge(close: np.ndarray, position: np.ndarray, rsi: np.ndarray,
               z: np.ndarray, vol_ratio: float, width: float) -> Dict:
    """Score the mean-reversion edge (0-100)."""
    i = -1  # latest bar
    score = 0

    # 1. Band position (0-30 points)
    pos = position[i]
    if pos < 20:  # near lower band — potential buy
        score += int((20 - pos) / 20 * 30)
    elif pos > 80:  # near upper band — potential sell
        score += int((pos - 80) / 20 * 30)

    # 2. RSI confirmation (0-25 points)
    r = rsi[i]
    if r < 30:
        score += int((30 - r) / 30 * 25)
    elif r > 70:
        score += int((r - 70) / 30 * 25)

    # 3. Z-score extremity (0-20 points)
    z_val = abs(z[i]) if not np.isnan(z[i]) else 0
    if z_val > 1.5:
        score += min(int(z_val * 5), 20)

    # 4. Volume confirmation (0-15 points)
    if vol_ratio > 1.5:
        score += 15
    elif vol_ratio > 1.0:
        score += 8

    # 5. Band width penalty (narrow bands = low edge)
    if width < 5:
        score = int(score * 0.5)  # squeeze — wait
    elif width > 15:
        score = min(score + 10, 100)  # wide bands — good reversion opportunity

    score = min(score, 100)

    # Direction
    if pos < 20 and r < 35:
        direction = "BUY"
    elif pos > 80 and r > 65:
        direction = "SELL"
    else:
        direction = "NEUTRAL"

    # Stop level (ATR-based estimate)
    recent_high = np.max(close[-20:])
    recent_low = np.min(close[-20:])
    atr_est = (recent_high - recent_low) / 5
    stop = close[i] - atr_est * 1.5 if direction == "BUY" else close[i] + atr_est * 1.5

    # Recommended size (Kelly-inspired, capped)
    if score >= 70:
        size_pct = 25
    elif score >= 50:
        size_pct = 15
    elif score >= 30:
        size_pct = 10
    else:
        size_pct = 0

    return {
        "symbol": None,  # filled by caller
        "close": round(float(close[i]), 2),
        "edge_score": score,
        "direction": direction,
        "recommended_size_pct": size_pct,
        "stop_level": round(float(stop), 2),
        "metrics": {
            "bb_position": round(float(pos), 1),
            "bb_width_pct": round(float(width), 1),
            "rsi": round(float(r), 1),
            "z_score": round(float(z_val), 2),
            "volume_ratio": round(float(vol_ratio), 2),
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
    }


# ── Main ──────────────────────────────────────────────────────────────

def analyze(symbol: str) -> Optional[Dict]:
    """Full analysis for one symbol."""
    df = fetch_ohlcv(symbol)
    if df is None:
        return None

    close = df["Close"].values.astype(float)
    high = df["High"].values.astype(float)
    low = df["Low"].values.astype(float)
    volume = df["Volume"].values.astype(float)

    sma, upper, lower, position, width = bollinger_bands(close)
    rsi = compute_rsi(close)
    z = z_score(close)
    vol_ratio_arr = volume_ratio(volume)
    vol_r = vol_ratio_arr[-1] if not np.isnan(vol_ratio_arr[-1]) else 1.0
    w = width[-1] if not np.isnan(width[-1]) else 10.0

    result = score_edge(close, position, rsi, z, vol_r, w)
    result["symbol"] = symbol
    return result


def main():
    json_mode = "--json" in sys.argv
    all_mode = "--all" in sys.argv

    symbols = SYMBOLS if all_mode else [sys.argv[1]] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ["BTC-USD"]

    results = []
    for sym in symbols:
        r = analyze(sym)
        if r:
            results.append(r)

    if json_mode:
        print(json.dumps(results if all_mode else results[0] if results else {}, indent=2))
    else:
        for r in results:
            d = r["direction"]
            icon = "🟢" if d == "BUY" else ("🔴" if d == "SELL" else "⚫")
            s = r["edge_score"]
            size = r["recommended_size_pct"]
            print(f"{icon} {r['symbol']:10s} | Edge={s:3d}/100 | {d:7s} | "
                  f"Size={size}% | Stop=${r['stop_level']:,.2f} | "
                  f"RSI={r['metrics']['rsi']:.0f} BB={r['metrics']['bb_position']:.0f}% "
                  f"Z={r['metrics']['z_score']:.1f}σ Vol={r['metrics']['volume_ratio']:.1f}x")


if __name__ == "__main__":
    import pandas as pd  # yfinance needs it
    main()
