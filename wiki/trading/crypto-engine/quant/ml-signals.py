#!/usr/bin/env python3
"""
Quant Module #7 — ML / Signal Processing
===========================================
Regime detection, anomaly scoring, feature extraction.
Answers: "Which strategy should work right now?"

Regimes detected:
  - TRENDING (ADX > 25, directional movement clear)
  - MEAN_REVERTING (price far from MA, low ADX)
  - HIGH_VOL (volatility elevated, wide stops)
  - LOW_VOL (compressed, breakout likely)
  - CHOPPY (no clear direction, whipsaw risk)
  - BREAKOUT (vol compression + sudden range expansion)

Output: regime probabilities + recommended strategy + anomaly flags.

Usage:
    python3 ml-signals.py BTC-USD
    python3 ml-signals.py --all
    python3 ml-signals.py --json
"""

import sys
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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

# ── Fetch ───────────────────────────────────────────────────────────

def fetch(symbol):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# ── Feature Engineering ─────────────────────────────────────────────

def ema(data: np.ndarray, period: int) -> np.ndarray:
    alpha = 2 / (period + 1)
    result = np.zeros_like(data)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute ADX."""
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    atr = np.zeros(len(close))
    for i in range(period, len(close)):
        atr[i] = np.mean(tr[i-period+1:i+1]) if i-period+1 >= 0 else 0
    
    up = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    
    plus_di = np.zeros(len(close))
    minus_di = np.zeros(len(close))
    for i in range(period, len(close)):
        atr_i = atr[i]
        if atr_i > 0:
            plus_di[i] = 100 * np.mean(plus_dm[i-period+1:i+1]) / atr_i
            minus_di[i] = 100 * np.mean(minus_dm[i-period+1:i+1]) / atr_i
    
    dx = np.zeros(len(close))
    for i in range(len(close)):
        denom = plus_di[i] + minus_di[i]
        dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / denom if denom > 0 else 0
    
    adx_arr = np.zeros(len(close))
    for i in range(period * 2, len(close)):
        adx_arr[i] = np.mean(dx[i-period+1:i+1])
    
    return adx_arr


def efficiency_ratio(close: np.ndarray, period: int = 10) -> np.ndarray:
    """Kaufman efficiency ratio: net change / sum of absolute changes."""
    er = np.zeros(len(close))
    for i in range(period, len(close)):
        direction = abs(close[i] - close[i - period])
        volatility = np.sum(np.abs(np.diff(close[i - period:i + 1])))
        er[i] = direction / volatility if volatility > 0 else 0
    return er


def z_score(series: np.ndarray, window: int = 20) -> np.ndarray:
    """Rolling Z-score from mean."""
    z = np.zeros(len(series))
    for i in range(window, len(series)):
        w = series[i - window:i]
        mu, std = np.mean(w), np.std(w)
        z[i] = (series[i] - mu) / std if std > 0 else 0
    return z


# ── Regime Detection ────────────────────────────────────────────────

def detect_regime(df) -> Dict:
    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    v = df["Volume"].values
    
    # Features
    adx_val = adx(h, l, c)[-1]
    er_10 = efficiency_ratio(c, 10)[-1]
    er_30 = efficiency_ratio(c, 30)[-1]
    z_20 = z_score(c, 20)[-1]
    z_50 = z_score(c, 50)[-1]
    
    # Volatility
    log_ret = np.diff(np.log(c))
    vol_14 = np.std(log_ret[-14:]) * np.sqrt(365) if len(log_ret) >= 14 else 0
    vol_60 = np.std(log_ret[-60:]) * np.sqrt(365) if len(log_ret) >= 60 else 0
    vol_ratio = vol_14 / vol_60 if vol_60 > 0 else 1
    
    # Range compression
    high_low_range = np.log(h / l)
    range_5 = np.mean(high_low_range[-5:]) if len(high_low_range) >= 5 else 0
    range_20 = np.mean(high_low_range[-20:]) if len(high_low_range) >= 20 else 0
    range_ratio = range_5 / range_20 if range_20 > 0 else 1
    
    # Volume anomaly
    vol_ma_20 = np.mean(v[-20:]) if len(v) >= 20 else v[-1]
    vol_surge = v[-1] / vol_ma_20 if vol_ma_20 > 0 else 1
    
    # Classify
    regimes = {}
    
    # TRENDING: ADX > 25, efficiency > 0.4
    if adx_val > 25 and er_10 > 0.35:
        regimes["TRENDING"] = min(90, int(adx_val + er_10 * 50))
    else:
        regimes["TRENDING"] = max(5, int(adx_val * 1.5))
    
    # MEAN_REVERTING: Z-score extreme, ADX < 20
    z_abs = abs(z_20)
    if z_abs > 1.5 and adx_val < 20:
        regimes["MEAN_REVERTING"] = min(90, int(z_abs * 30))
    else:
        regimes["MEAN_REVERTING"] = max(5, int(z_abs * 15))
    
    # HIGH_VOL: vol 2x normal
    if vol_ratio > 1.5:
        regimes["HIGH_VOL"] = min(95, int(vol_ratio * 30 + 20))
    else:
        regimes["HIGH_VOL"] = max(5, int(vol_ratio * 20))
    
    # LOW_VOL: vol < 0.6x normal, range compression
    if vol_ratio < 0.6 and range_ratio < 0.8:
        regimes["LOW_VOL"] = min(90, int((1 - vol_ratio) * 80))
    else:
        regimes["LOW_VOL"] = max(5, int((1 - min(vol_ratio, 1.5)) * 40))
    
    # CHOPPY: low ADX, low efficiency
    if adx_val < 18 and er_10 < 0.25:
        regimes["CHOPPY"] = min(90, int((1 - er_10) * 80))
    else:
        regimes["CHOPPY"] = max(5, int((1 - min(er_10, 1)) * 40))
    
    # BREAKOUT: range expansion from compression
    if range_ratio > 1.4 and range_ratio > 0:
        regimes["BREAKOUT"] = min(85, int(range_ratio * 30 + 20))
    else:
        regimes["BREAKOUT"] = max(5, int(range_ratio * 20))
    
    # Dominant regime
    dominant = max(regimes, key=regimes.get)
    dominant_score = regimes[dominant]
    
    # Recommended strategy
    strategy_map = {
        "TRENDING": ("MOMENTUM", "Trend following with trailing stops"),
        "MEAN_REVERTING": ("MEAN_REV", "Fade extremes, tight stops"),
        "HIGH_VOL": ("VOL_ARB", "Wide stops, smaller size, vol selling"),
        "LOW_VOL": ("BREAKOUT", "Anticipate expansion, straddle setup"),
        "CHOPPY": ("SIT_OUT", "No directional edge, reduce exposure"),
        "BREAKOUT": ("MOMENTUM", "Ride expansion, scale in"),
    }
    strategy, strategy_desc = strategy_map.get(dominant, ("NEUTRAL", "No clear edge"))
    
    # Edge score: confidence in dominant regime
    edge = dominant_score
    
    # Anomaly flags
    anomalies = []
    if vol_surge > 2.5:
        anomalies.append("VOLUME_SURGE")
    if z_abs > 2.5:
        anomalies.append("PRICE_EXTREME")
    if range_ratio > 2.0:
        anomalies.append("RANGE_EXPANSION")
    
    if dominant == "CHOPPY" or dominant == "HIGH_VOL":
        direction = "NEUTRAL"
    elif dominant == "MEAN_REVERTING":
        direction = "BUY" if z_20 < -1 else "SELL" if z_20 > 1 else "NEUTRAL"
    elif dominant in ("TRENDING", "BREAKOUT"):
        # Use EMA slope + short-term momentum to detect trend direction.
        # EMA crossover alone lags badly (3-5 days after a turn).
        # EMA slope catches the turn 1-2 days earlier.
        # Short-term momentum (3-day) overrides EMA on recovery rallies.
        ema20 = ema(c, 20)
        ema_slope = (ema20[-1] - ema20[-5]) / ema20[-5] if len(ema20) >= 5 and ema20[-5] > 0 else 0
        price_vs_ema = c[-1] / ema20[-1] - 1 if ema20[-1] > 0 else 0
        
        # Short-term momentum: 3-day price change
        st_momentum = (c[-1] - c[-4]) / c[-4] if len(c) >= 4 and c[-4] > 0 else 0
        
        # Strong short-term momentum (>2% in 3 days) overrides EMA slope
        if st_momentum > 0.02:
            direction = "BUY"
        elif st_momentum < -0.02:
            direction = "SELL"
        elif ema_slope > 0.0005:       # EMA turning up
            direction = "BUY"
        elif ema_slope < -0.0005:      # EMA turning down
            direction = "SELL"
        else:
            # Flat EMA → fall back to crossover
            direction = "BUY" if price_vs_ema > 0 else "SELL"
    else:
        direction = "NEUTRAL"
    
    return {
        "edge_score": edge,
        "direction": direction,
        "recommended_size_pct": min(15, max(0, edge - 25)) if direction != "NEUTRAL" else 0,
        "close": float(c[-1]),
        "dominant_regime": dominant,
        "dominant_score": dominant_score,
        "regime_probs": regimes,
        "recommended_strategy": strategy,
        "strategy_description": strategy_desc,
        "anomalies": anomalies,
        "features": {
            "adx_14": round(float(adx_val), 1),
            "efficiency_10": round(float(er_10), 3),
            "efficiency_30": round(float(er_30), 3),
            "z_score_20": round(float(z_20), 2),
            "z_score_50": round(float(z_50), 2),
            "vol_ratio": round(float(vol_ratio), 2),
            "range_ratio": round(float(range_ratio), 2),
            "volume_surge": round(float(vol_surge), 1),
        },
    }


# ── Main ────────────────────────────────────────────────────────────

def main():
    json_mode = "--json" in sys.argv
    all_mode = "--all" in sys.argv
    symbols = SYMBOLS if all_mode else [sys.argv[1]] if len(sys.argv) > 1 else [SYMBOLS[0]]

    results = []
    for sym in symbols:
        df = fetch(sym)
        if df is None:
            results.append({"symbol": sym, "error": "no data"})
            continue
        s = detect_regime(df)
        s["symbol"] = sym
        results.append(s)

    if json_mode:
        output = results[0] if not all_mode and len(results) == 1 else results
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            if "error" in r:
                print(f"  {r['symbol']}: ❌ {r['error']}")
                continue
            print(f"  {r['symbol']:8s} | regime={r['dominant_regime']:16s} ({r['dominant_score']:2d}%) | "
                  f"strat={r['recommended_strategy']:10s} | edge={r['edge_score']:3d} | "
                  f"dir={r['direction']:8s} | adx={r['features']['adx_14']:.0f} | "
                  f"z20={r['features']['z_score_20']:+.1f}")
            if r["anomalies"]:
                print(f"         ⚠️  {', '.join(r['anomalies'])}")


if __name__ == "__main__":
    import pandas as pd
    main()
