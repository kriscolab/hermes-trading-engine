#!/usr/bin/env python3
"""Tape Reading Module — v12.0 quant layer.

Analyzes time & sales data for large trades and absorption patterns:
- Large trade detection: trades > $100K notional
- Absorption: large seller met by passive buyer = bullish
- Trade sequencing: are buys lifting offers or hitting bids?

Data: OKX recent trades endpoint (free, public).

Output: edge score (-100 to +100) and anomaly flags.
"""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple, List
from collections import defaultdict

IST = timezone(timedelta(hours=5, minutes=30))
OKX_TRADES_URL = "https://www.okx.com/api/v5/market/trades?instId={inst}&limit=500"

OUTPUT_PATH = Path("/tmp/tape_signals.json")
LARGE_TRADE_THRESHOLD = 100_000  # $100K notional


def fetch_trades(inst_id: str) -> list:
    """Fetch last 500 trades from OKX."""
    try:
        url = OKX_TRADES_URL.format(inst=inst_id)
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", [])
    except Exception:
        return []


def detect_large_trades(trades: list) -> dict:
    """Identify trades exceeding $100K notional.
    
    Returns: {count, total_notional, largest, buy_count, sell_count}
    """
    large = []
    buy_count = 0
    sell_count = 0
    
    for t in trades:
        size = float(t.get("sz", 0))
        price = float(t.get("px", 0))
        notional = size * price
        side = t.get("side", "")
        
        if notional >= LARGE_TRADE_THRESHOLD:
            large.append({"side": side, "notional": notional, "price": price, "size": size,
                         "ts": t.get("ts", "")})
            if side == "buy":
                buy_count += 1
            else:
                sell_count += 1
    
    return {
        "count": len(large),
        "total_notional": sum(l["notional"] for l in large),
        "largest": max(large, key=lambda x: x["notional"]) if large else None,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "trades": large[-10:],  # Last 10 large trades
    }


def detect_absorption(trades: list, large_trades: dict) -> float:
    """Detect absorption: large seller met by passive buyer = bullish divergence.
    
    Absorption score:
    - Large sell trades followed by price recovery = + (bullish absorption)
    - Large buy trades followed by price decline = - (bearish distribution)
    
    Returns: absorption score (-1 to +1)
    """
    if not trades or not large_trades.get("trades"):
        return 0.0
    
    large_list = large_trades["trades"]
    
    # Compare first trade price vs last trade price
    if len(trades) > 1:
        first_price = float(trades[-1].get("px", 0))
        last_price = float(trades[0].get("px", 0))
        price_change = (last_price - first_price) / first_price if first_price > 0 else 0
        
        # Large sells + price up = absorption
        if large_trades.get("sell_count", 0) > large_trades.get("buy_count", 0) and price_change > 0:
            return min(1.0, price_change * 100)
        
        # Large buys + price down = distribution
        if large_trades.get("buy_count", 0) > large_trades.get("sell_count", 0) and price_change < 0:
            return max(-1.0, price_change * 100)
    
    return 0.0


def compute_buy_sell_pressure(trades: list) -> float:
    """Ratio of aggressive buys vs aggressive sells.
    
    Aggressive buy = taker buy (lifts offer)
    Aggressive sell = taker sell (hits bid)
    
    Returns: pressure ratio (-1 to +1)
    """
    buy_vol = sum(float(t.get("sz", 0)) for t in trades if t.get("side") == "buy")
    sell_vol = sum(float(t.get("sz", 0)) for t in trades if t.get("side") == "sell")
    total = buy_vol + sell_vol
    if total == 0:
        return 0.0
    return (buy_vol - sell_vol) / total


def tape_edge(ticker: str) -> Tuple[float, str, dict]:
    """Compute tape reading edge score.
    
    Combines:
    - Large trade imbalance (40%)
    - Absorption detection (30%)
    - Buy/sell pressure (30%)
    
    Returns: (edge, direction, flags)
    """
    inst_id = f"{ticker}-USDT-SWAP"
    trades = fetch_trades(inst_id)
    
    if len(trades) < 50:
        return (0.0, "NEUTRAL", {})
    
    large = detect_large_trades(trades)
    absorption = detect_absorption(trades, large)
    pressure = compute_buy_sell_pressure(trades)
    
    # Large trade imbalance
    lt_total = large["buy_count"] + large["sell_count"]
    lt_imbalance = 0.0
    if lt_total > 0:
        lt_imbalance = (large["buy_count"] - large["sell_count"]) / lt_total
    
    # Edge score
    raw = (lt_imbalance * 40) + (absorption * 30) + (pressure * 30)
    edge = max(-100, min(100, raw))
    
    direction = "NEUTRAL"
    if edge > 15:
        direction = "BULLISH"
    elif edge < -15:
        direction = "BEARISH"
    
    flags = {
        "large_trade_count": large["count"],
        "large_trade_notional": round(large["total_notional"], 2),
        "absorption": round(absorption, 3),
        "pressure_ratio": round(pressure, 3),
    }
    
    return (edge, direction, flags)


def run(tickers: list = None):
    """Run tape reading analysis."""
    if tickers is None:
        tickers = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE"]
    
    results = {}
    for ticker in tickers:
        edge, direction, flags = tape_edge(ticker)
        results[ticker] = {"edge": round(edge, 2), "direction": direction, "flags": flags}
    
    output = {
        "generated_at": datetime.now(IST).isoformat(),
        "signals": results,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    return results


if __name__ == "__main__":
    run()
