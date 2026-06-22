#!/usr/bin/env python3
"""
Quant Module #6 — Volatility Arbitrage
=========================================
Realized vs implied vol gap, vol-of-vol, vol regime classifier,
and vol term structure steepness. Edge: fade vol spikes, ride vol
expansions with trend, avoid vol collapse.

Without live options data, uses Parkinson range-based volatility
as a high-frequency vol estimator plus Garman-Klass OHLC vol.

Usage:
    python3 volatility-arbitrage.py BTC-USD
    python3 volatility-arbitrage.py --all
    python3 volatility-arbitrage.py --json
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

# ── Fetch ───────────────────────────────────────────────────────────

def fetch(symbol):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# ── Volatility Estimators ───────────────────────────────────────────

def close_close_vol(close: np.ndarray, window: int = 14) -> np.ndarray:
    """Annualized close-to-close (standard) volatility."""
    log_ret = np.diff(np.log(close))
    vol = np.zeros(len(close))
    for i in range(window, len(close)):
        vol[i] = np.std(log_ret[i-window:i]) * np.sqrt(365)
    return vol


def parkinson_vol(high: np.ndarray, low: np.ndarray, window: int = 14) -> np.ndarray:
    """Parkinson range-based volatility (more efficient estimator)."""
    log_hl = np.log(high / low)
    vol = np.zeros(len(high))
    k = 1.0 / (4.0 * np.log(2.0))
    for i in range(window, len(high)):
        vol[i] = np.sqrt(k * np.mean(log_hl[i-window:i]**2)) * np.sqrt(365)
    return vol


def vol_of_vol(vol: np.ndarray, window: int = 30) -> float:
    """Volatility of volatility — how unstable is vol right now."""
    if len(vol) < window + 2:
        return 0
    recent = vol[-window:]
    recent = recent[recent > 0]
    if len(recent) < 10:
        return 0
    return float(np.std(np.diff(recent)) / (np.mean(recent) + 1e-10))


def vol_regime(vol: np.ndarray, short: int = 7, long: int = 30) -> str:
    """Classify vol regime: EXPANDING, CONTRACTING, or STABLE."""
    if len(vol) < long + 1:
        return "STABLE"
    short_vol = np.mean(vol[-short:])
    long_vol = np.mean(vol[-long:-short])
    if long_vol == 0:
        return "STABLE"
    ratio = short_vol / long_vol
    if ratio > 1.3:
        return "EXPANDING"
    elif ratio < 0.7:
        return "CONTRACTING"
    return "STABLE"


# ── Edge Scoring ────────────────────────────────────────────────────

def score_volatility(df) -> Dict:
    """Score vol-based edges. Higher vol = more opportunity + more risk."""
    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    
    cc_vol = close_close_vol(c)
    pk_vol = parkinson_vol(h, l)
    
    current_cc = cc_vol[-1]
    current_pk = pk_vol[-1]
    vol_30d_avg = np.mean(cc_vol[-30:][cc_vol[-30:] > 0]) if any(cc_vol[-30:] > 0) else 0.5
    
    vov = vol_of_vol(pk_vol)
    regime = vol_regime(pk_vol)
    
    # Gap between Parkinson and close-close (range > close = intraday volatility)
    vol_gap = (current_pk - current_cc) / (current_cc + 1e-10)
    
    # Edge scoring
    edge = 0
    signals = []
    
    # 1. Vol regime edge: EXPANDING = trend opportunity (+), CONTRACTING = avoid (-)
    if regime == "EXPANDING":
        edge += 20
        signals.append("vol_expanding")
    elif regime == "CONTRACTING":
        edge -= 15
        signals.append("vol_contracting")
    
    # 2. Vol vs historical: elevated vol = opportunity with caution
    if vol_30d_avg > 0:
        vol_ratio = current_cc / vol_30d_avg
        if vol_ratio > 1.5:
            edge += 10
            signals.append("vol_elevated")
        elif vol_ratio < 0.5:
            edge -= 10
            signals.append("vol_collapsed")
    
    # 3. Range vol gap: large intraday range vs close = information flow
    if abs(vol_gap) > 0.3:
        edge += 15
        signals.append("high_intraday_range")
    
    # 4. Vol-of-vol: high vov = unstable environment
    if vov > 0.5:
        edge -= 20
        signals.append("volatile_vol")
    elif vov < 0.2:
        edge += 10
        signals.append("stable_vol")
    
    # Direction
    if regime == "EXPANDING" and vol_gap > 0:
        direction = "VOL_LONG"  # long vol exposure
    elif regime == "CONTRACTING":
        direction = "VOL_SHORT"  # short vol / sell premium
    else:
        direction = "NEUTRAL"
    
    # Normalize edge to 0-100
    edge = max(0, min(100, edge + 40))
    
    return {
        "edge_score": edge,
        "direction": direction,
        "recommended_size_pct": min(15, max(0, edge - 40)) if direction != "NEUTRAL" else 0,
        "close": float(df["Close"].iloc[-1]),
        "realized_vol_14d": round(float(current_cc), 3),
        "parkinson_vol_14d": round(float(current_pk), 3),
        "vol_of_vol_30d": round(float(vov), 3),
        "vol_regime": regime,
        "vol_gap_pct": round(float(vol_gap * 100), 1),
        "signals": signals,
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
        s = score_volatility(df)
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
            print(f"  {r['symbol']:8s} | edge={r['edge_score']:3d} | {r['direction']:10s} | "
                  f"regime={r['vol_regime']:12s} | rv={r['realized_vol_14d']:.2f} | "
                  f"vov={r['vol_of_vol_30d']:.3f} | size={r['recommended_size_pct']:.0f}%")


if __name__ == "__main__":
    import pandas as pd
    main()
