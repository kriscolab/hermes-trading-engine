#!/usr/bin/env python3
"""
Quant Module #10 — Market Microstructure
===========================================
Order-flow proxy, Amihud illiquidity, realized spread, VWAP deviation,
trade-size analysis. Edge: detect when informed traders are active.

Without tick data, approximates microstructure from OHLCV + volume
using Park & Lee (2011) style estimators.

Usage:
    python3 microstructure.py BTC-USD
    python3 microstructure.py --all
    python3 microstructure.py --json
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
PERIOD = "90d"

# ── Fetch ───────────────────────────────────────────────────────────

def fetch(symbol):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# ── Microstructure Estimators ──────────────────────────────────────

def amihud_illiquidity(close: np.ndarray, volume: np.ndarray, window: int = 14) -> np.ndarray:
    """Amihud (2002) illiquidity: |return| / dollar_volume.
    Higher = more price impact per dollar traded = less liquid."""
    ret = np.abs(np.diff(np.log(close)))
    dv = close[1:] * volume[1:]  # dollar volume
    illiq = np.zeros(len(close))
    for i in range(window, len(close)):
        ratios = ret[i-window:i] / dv[i-window:i]
        ratios = ratios[np.isfinite(ratios)]
        illiq[i] = np.mean(ratios) * 1e8 if len(ratios) > 0 else 0
    return illiq


def vwap_deviation(df) -> float:
    """How far is close from VWAP? Positive = above VWAP."""
    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    v = df["Volume"].values
    
    typical = (h + l + c) / 3
    vwap = np.sum(typical[-20:] * v[-20:]) / np.sum(v[-20:]) if np.sum(v[-20:]) > 0 else c[-1]
    return float((c[-1] - vwap) / vwap * 100)


def order_flow_imbalance_proxy(close: np.ndarray, high: np.ndarray, low: np.ndarray, volume: np.ndarray, window: int = 14) -> np.ndarray:
    """Continuous OFI proxy using close-location within daily range.
    Close at high = +1 (buying pressure), close at low = -1 (selling pressure).
    Weighted by volume. Much better than binary direction-only."""
    ofi = np.zeros(len(close))
    for i in range(1, len(close)):
        hl_range = high[i] - low[i]
        if hl_range > 0:
            # Where did close land within today's range? 0=low, 1=high
            close_position = (close[i] - low[i]) / hl_range
            # Center around 0: -0.5 to +0.5, scale to -1 to +1
            ofi[i] = (close_position - 0.5) * 2
        # Weight by volume relative to average
        if window < i:
            avg_vol = np.mean(volume[i-window:i])
            if avg_vol > 0:
                ofi[i] *= min(2.0, volume[i] / avg_vol)
    return ofi


def realized_spread(close: np.ndarray, window: int = 20) -> float:
    """Realized spread proxy: 5-min midpoint return after trade.
    Approximated with daily close-to-close correlation with volume."""
    ret = np.diff(np.log(close))
    if len(ret) < window:
        return 0
    recent = ret[-window:]
    # Positive autocorrelation → momentum (informed traders push price directionally)
    # Negative autocorrelation → mean reversion (market makers earning spread)
    ac1 = float(np.corrcoef(recent[:-1], recent[1:])[0, 1]) if len(recent) > 1 else 0
    return ac1


def trade_size_proxy(volume: np.ndarray, window: int = 14) -> Dict:
    """Volume distribution analysis: are we seeing large blocks?"""
    recent = volume[-window:]
    mean_vol = float(np.mean(recent))
    std_vol = float(np.std(recent))
    current = float(volume[-1])
    
    z_vol = (current - mean_vol) / std_vol if std_vol > 0 else 0
    
    regime = "NORMAL"
    if z_vol > 2:
        regime = "WHALE_ACTIVE"
    elif z_vol > 1:
        regime = "ELEVATED"
    elif z_vol < -1:
        regime = "QUIET"
    
    return {
        "volume_z": round(z_vol, 2),
        "regime": regime,
        "mean_vol": round(mean_vol, 0),
    }


# ── Edge Scoring ────────────────────────────────────────────────────

def score_microstructure(df) -> Dict:
    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    v = df["Volume"].values
    
    illiq = amihud_illiquidity(c, v)
    ofi = order_flow_imbalance_proxy(c, h, l, v)
    vwap_dev = vwap_deviation(df)
    rspread = realized_spread(c)
    trade_info = trade_size_proxy(v)
    
    current_illiq = illiq[-1]
    illiq_20_avg = np.mean(illiq[-20:]) if len(illiq) >= 20 else current_illiq
    current_ofi = ofi[-1]
    ofi_5_avg = np.mean(ofi[-5:]) if len(ofi) >= 5 else 0
    
    edge = 0
    signals = []
    
    # 1. Illiquidity: rising illiquidity = more price impact = avoid
    if illiq_20_avg > 0:
        illiq_change = (current_illiq - illiq_20_avg) / illiq_20_avg
        if illiq_change > 0.5:
            edge -= 15
            signals.append("illiquidity_spike")
        elif illiq_change < -0.3:
            edge += 10
            signals.append("liquidity_improving")
    
    # 2. Order flow imbalance: strong directional flow = informed traders
    if abs(current_ofi) > 0.3:
        edge += 20
        if current_ofi > 0:
            signals.append("strong_buy_flow")
        else:
            signals.append("strong_sell_flow")
    elif abs(current_ofi) > 0.15:
        edge += 8
        signals.append("moderate_flow")
    
    # 3. VWAP deviation
    if abs(vwap_dev) > 3:
        edge += 15
        signals.append("vwap_extreme")
    elif abs(vwap_dev) > 1.5:
        edge += 5
    
    # 4. Realized spread (autocorrelation)
    if rspread < -0.3:
        edge += 15
        signals.append("mean_reverting_flow")
    elif rspread > 0.3:
        edge += 10
        signals.append("momentum_flow")
    
    # 5. Whale active
    if trade_info["regime"] == "WHALE_ACTIVE":
        edge += 15
        signals.append("whale_active")
    
    # Direction
    if current_ofi > 0.2 and vwap_dev > 0:
        direction = "BUY"
    elif current_ofi < -0.2 and vwap_dev < 0:
        direction = "SELL"
    elif current_ofi > 0.1:
        direction = "SLIGHTLY_BULLISH"
    elif current_ofi < -0.1:
        direction = "SLIGHTLY_BEARISH"
    else:
        direction = "NEUTRAL"
    
    edge = max(0, min(100, edge + 35))
    
    return {
        "edge_score": edge,
        "direction": direction,
        "recommended_size_pct": min(15, max(0, edge - 40)) if direction not in ("NEUTRAL",) else 0,
        "close": float(c[-1]),
        "amihud_illiquidity": round(float(current_illiq), 6),
        "ofi_current": round(float(current_ofi), 3),
        "ofi_5d_avg": round(float(ofi_5_avg), 3),
        "vwap_deviation_pct": round(float(vwap_dev), 2),
        "realized_spread_ac1": round(float(rspread), 3),
        "trade_size_regime": trade_info["regime"],
        "volume_z": trade_info["volume_z"],
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
        s = score_microstructure(df)
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
            print(f"  {r['symbol']:8s} | edge={r['edge_score']:3d} | {r['direction']:16s} | "
                  f"OFI={r['ofi_current']:+.2f} | vwap={r['vwap_deviation_pct']:+.1f}% | "
                  f"illiq={r['amihud_illiquidity']:.6f} | sprd_ac1={r['realized_spread_ac1']:+.2f} | "
                  f"vol={r['trade_size_regime']:14s} | size={r['recommended_size_pct']:.0f}%")


if __name__ == "__main__":
    import pandas as pd
    main()
