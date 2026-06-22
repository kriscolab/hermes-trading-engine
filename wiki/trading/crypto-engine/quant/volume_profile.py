#!/usr/bin/env python3
"""Volume Profile Module — v12.0 quant layer.

Computes volume-based support/resistance from OHLCV data:
- Volume-at-Price (VAP): where did most volume occur?
- Point of Control (POC): price with highest volume
- Value Area: 70% of volume around POC
- VWAP bands: ±1σ, ±2σ around VWAP

Data: Computed from OKX OHLCV (free, no extra API needed beyond existing fetch).

Output: edge score (-100 to +100) and key levels (POC, VAH, VAL, VWAP).
"""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple, List, Optional
from collections import defaultdict

IST = timezone(timedelta(hours=5, minutes=30))
OKX_CANDLE_URL = "https://www.okx.com/api/v5/market/candles?instId={inst}&bar=5m&limit=200"

OUTPUT_PATH = Path("/tmp/volume_profile_signals.json")


def fetch_candles(inst_id: str) -> list:
    """Fetch last 200 5-min candles from OKX. Returns list of [ts, open, high, low, close, vol]."""
    try:
        url = OKX_CANDLE_URL.format(inst=inst_id)
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", [])
    except Exception:
        return []


def compute_vap(candles: list, num_bins: int = 20) -> dict:
    """Compute Volume-at-Price from candle data.
    
    Distributes volume across price bins. Returns:
    {poc, vah, val, bins: [{price, volume}]}
    """
    if not candles:
        return {"poc": 0, "vah": 0, "val": 0, "bins": []}
    
    # Get price range
    prices = []
    for c in candles:
        prices.extend([float(c[2]), float(c[3])])  # high, low
    
    min_p, max_p = min(prices), max(prices)
    if min_p == max_p:
        return {"poc": min_p, "vah": min_p, "val": min_p, "bins": []}
    
    bin_size = (max_p - min_p) / num_bins
    
    # Distribute volume across bins
    volume_bins = defaultdict(float)
    for c in candles:
        vol = float(c[5])
        high, low = float(c[2]), float(c[3])
        price_range = high - low if high != low else 1
        
        # Distribute volume proportionally across price range
        for i in range(num_bins):
            bin_price = min_p + i * bin_size
            bin_high = bin_price + bin_size
            # Overlap of candle with this bin
            overlap_low = max(low, bin_price)
            overlap_high = min(high, bin_high)
            if overlap_high > overlap_low:
                overlap_pct = (overlap_high - overlap_low) / price_range
                volume_bins[round(bin_price, 2)] += vol * overlap_pct
    
    bins = sorted([{"price": p, "volume": v} for p, v in volume_bins.items()], key=lambda x: x["price"])
    
    # POC = highest volume bin
    poc_bin = max(bins, key=lambda x: x["volume"]) if bins else {"price": min_p, "volume": 0}
    poc = poc_bin["price"]
    
    # Value area = 70% of volume around POC
    total_vol = sum(b["volume"] for b in bins)
    target = total_vol * 0.7
    accumulated = 0
    
    vah = val = poc
    # Start from POC and expand outward
    sorted_by_dist = sorted(bins, key=lambda x: abs(x["price"] - poc))
    for b in sorted_by_dist:
        accumulated += b["volume"]
        if b["price"] > vah:
            vah = b["price"]
        if b["price"] < val or val == poc:
            val = b["price"]
        if accumulated >= target:
            break
    
    return {"poc": poc, "vah": vah, "val": val, "bins": bins}


def compute_vwap(candles: list) -> Tuple[float, float]:
    """Compute VWAP and standard deviation band.
    Returns: (vwap, vwap_std)
    """
    if not candles:
        return (0.0, 0.0)
    
    cumulative_pv = 0.0
    cumulative_vol = 0.0
    prices_vol_weighted = []
    
    for c in candles:
        typical = (float(c[2]) + float(c[3]) + float(c[4])) / 3  # (high+low+close)/3
        vol = float(c[5])
        cumulative_pv += typical * vol
        cumulative_vol += vol
        prices_vol_weighted.append(typical)
    
    vwap = cumulative_pv / cumulative_vol if cumulative_vol > 0 else 0
    
    # Weighted std dev
    if len(prices_vol_weighted) > 1:
        mean = sum(prices_vol_weighted) / len(prices_vol_weighted)
        variance = sum((p - mean) ** 2 for p in prices_vol_weighted) / len(prices_vol_weighted)
        vwap_std = variance ** 0.5
    else:
        vwap_std = 0.0
    
    return (vwap, vwap_std)


def volume_profile_edge(ticker: str, current_price: float = 0) -> Tuple[float, str, dict]:
    """Compute volume profile edge score.
    
    Edge logic:
    - Price near POC (within value area) = neutral (consolidation)
    - Price breaking above VAH with volume = bullish (acceptance above value)
    - Price breaking below VAL with volume = bearish (acceptance below value)
    - Price near VWAP with tight bands = low edge (chop)
    - Price outside VWAP ±2σ = extreme (mean-reversion signal)
    
    Returns: (edge, direction, levels_dict)
    """
    inst_id = f"{ticker}-USDT-SWAP"
    candles = fetch_candles(inst_id)
    
    if len(candles) < 50:
        return (0.0, "NEUTRAL", {})
    
    vap = compute_vap(candles)
    vwap, vwap_std = compute_vwap(candles)
    
    poc, vah, val = vap["poc"], vap["vah"], vap["val"]
    
    # Use last close as current price if not provided
    if current_price <= 0:
        current_price = float(candles[0][4]) if candles else 0
    
    if current_price <= 0:
        return (0.0, "NEUTRAL", {})
    
    edge = 0.0
    direction = "NEUTRAL"
    
    # Price relative to value area
    if val <= current_price <= vah:
        edge = 0.0  # Inside value area = neutral
    elif current_price > vah:
        # Break above value area = bullish if supported by volume
        above_pct = (current_price - vah) / vah * 100 if vah > 0 else 0
        edge = min(50, above_pct * 10)  # Scale: 1% above = 10 edge
        direction = "BULLISH"
    elif current_price < val:
        # Break below value area = bearish
        below_pct = (val - current_price) / val * 100 if val > 0 else 0
        edge = min(50, below_pct * 10)
        direction = "BEARISH"
    
    # VWAP overlay
    if vwap_std > 0:
        bands_from_vwap = (current_price - vwap) / vwap_std
        if abs(bands_from_vwap) > 2.0:
            # Outside ±2σ = mean-reversion signal
            edge += 20
            direction = "BEARISH" if bands_from_vwap > 0 else "BULLISH"
    
    edge = max(-100, min(100, edge))
    
    levels = {
        "poc": round(poc, 2),
        "vah": round(vah, 2),
        "val": round(val, 2),
        "vwap": round(vwap, 2),
        "vwap_upper": round(vwap + vwap_std * 2, 2),
        "vwap_lower": round(vwap - vwap_std * 2, 2),
    }
    
    return (edge, direction, levels)


def run(tickers: list = None):
    """Run volume profile analysis."""
    if tickers is None:
        tickers = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE"]
    
    results = {}
    for ticker in tickers:
        edge, direction, levels = volume_profile_edge(ticker)
        results[ticker] = {"edge": round(edge, 2), "direction": direction, "levels": levels}
    
    output = {
        "generated_at": datetime.now(IST).isoformat(),
        "signals": results,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    return results


if __name__ == "__main__":
    import sys
    if "--json" in sys.argv:
        tickers = None
        if "--all" in sys.argv:
            tickers = ["BTC","ETH","SOL","AVAX","LINK","DOGE","ADA","XRP",
                       "HYPE","SUI","NEAR","APT","ARB","OP","INJ","TIA",
                       "SEI","RUNE","FET","RNDR","TAO","WLD","STRK","JUP",
                       "JTO","PENDLE","LDO","AAVE","UNI","EIGEN","ONDO","WIF"]
        results = run(tickers)
        output = []
        for ticker, data in results.items():
            output.append({"symbol": ticker, "edge_score": data.get("edge",0),
                          "direction": data.get("direction","NEUTRAL")})
        print(json.dumps(output))
    else:
        run()
