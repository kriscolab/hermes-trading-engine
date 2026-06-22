#!/usr/bin/env python3
"""Orderflow Module — v12.0 quant layer.

Computes orderflow edge scores from market microstructure:
- Cumulative Volume Delta (CVD): net buying/selling pressure
- Delta divergence: price up but CVD flat = hidden selling
- Footprint: bid/ask volume at price levels

Data: OKX order book snapshots (free, public REST API).

Output: edge score (-100 to +100) and direction (BULLISH/BEARISH/NEUTRAL).
"""

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

IST = timezone(timedelta(hours=5, minutes=30))
OKX_BOOK_URL = "https://www.okx.com/api/v5/market/books?instId={inst}&sz=10"
OKX_TRADES_URL = "https://www.okx.com/api/v5/market/trades?instId={inst}&limit=100"

OUTPUT_PATH = Path("/tmp/orderflow_signals.json")


def fetch_orderbook(inst_id: str) -> dict:
    """Fetch top 10 levels of OKX order book."""
    try:
        url = OKX_BOOK_URL.format(inst=inst_id)
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def fetch_recent_trades(inst_id: str) -> dict:
    """Fetch last 100 trades from OKX."""
    try:
        url = OKX_TRADES_URL.format(inst=inst_id)
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def compute_cvd(trades: list) -> float:
    """Cumulative Volume Delta: sum of (buy_vol - sell_vol) / total_vol.
    Positive = buying pressure, negative = selling pressure.
    """
    buy_vol = 0.0
    sell_vol = 0.0
    for t in trades:
        sz = float(t.get("sz", 0))
        side = t.get("side", "")
        if side == "buy":
            buy_vol += sz
        elif side == "sell":
            sell_vol += sz
    total = buy_vol + sell_vol
    if total == 0:
        return 0.0
    return (buy_vol - sell_vol) / total  # -1 to +1


def compute_orderbook_imbalance(bids: list, asks: list) -> float:
    """Order book imbalance: (bid_vol - ask_vol) / (bid_vol + ask_vol).
    Range: -1 (heavy sell pressure) to +1 (heavy buy pressure).
    """
    bid_vol = sum(float(b[1]) for b in bids[:5])
    ask_vol = sum(float(a[1]) for a in asks[:5])
    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return (bid_vol - ask_vol) / total


def compute_delta_divergence(price_change_1h: float, cvd: float) -> float:
    """Delta divergence: price up but CVD flat/negative = hidden selling.
    
    Returns a divergence score. Negative = bearish divergence.
    """
    # If price is up AND CVD is negative = bearish divergence
    if price_change_1h > 0 and cvd < -0.1:
        return -0.5  # Strong bearish divergence
    # If price is down AND CVD is positive = bullish divergence
    if price_change_1h < 0 and cvd > 0.1:
        return 0.5
    return 0.0


def orderflow_edge(ticker: str, price_change_1h: float = 0.0) -> Tuple[float, str]:
    """Compute orderflow edge score and direction for a ticker.
    
    Args:
        ticker: Upper-case ticker (e.g., 'BTC', 'ETH')
        price_change_1h: Optional 1-hour price change for divergence calc
    
    Returns:
        (edge_score, direction) where direction is BULLISH/BEARISH/NEUTRAL
    """
    inst_id = f"{ticker}-USDT-SWAP"
    
    # Fetch data
    book_data = fetch_orderbook(inst_id)
    trades_data = fetch_recent_trades(inst_id)
    
    # Extract
    data = book_data.get("data", [{}])
    bids = data[0].get("bids", []) if data else []
    asks = data[0].get("asks", []) if data else []
    
    trade_list = trades_data.get("data", [])
    
    if not bids or not asks:
        return (0.0, "NEUTRAL")
    
    # Compute metrics
    cvd = compute_cvd(trade_list)
    ob_imbalance = compute_orderbook_imbalance(bids, asks)
    divergence = compute_delta_divergence(price_change_1h, cvd)
    
    # Edge score: combine CVD (40%) + order book imbalance (30%) + divergence (30%)
    raw_score = (cvd * 40) + (ob_imbalance * 30) + (divergence * 30)
    
    # Clamp to -100/+100
    edge = max(-100, min(100, raw_score))
    
    direction = "NEUTRAL"
    if edge > 15:
        direction = "BULLISH"
    elif edge < -15:
        direction = "BEARISH"
    
    return (edge, direction)


def run(tickers: list = None):
    """Run orderflow analysis for list of tickers, write to /tmp/orderflow_signals.json."""
    if tickers is None:
        tickers = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE"]
    
    results = {}
    for ticker in tickers:
        edge, direction = orderflow_edge(ticker)
        results[ticker] = {"edge": round(edge, 2), "direction": direction}
    
    output = {
        "generated_at": datetime.now(IST).isoformat(),
        "signals": results,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    return results


if __name__ == "__main__":
    import sys
    if "--json" in sys.argv:
        # CLI mode — return JSON for aggregator
        tickers = None
        if "--all" in sys.argv:
            tickers = ["BTC","ETH","SOL","AVAX","LINK","DOGE","ADA","XRP",
                       "HYPE","SUI","NEAR","APT","ARB","OP","INJ","TIA",
                       "SEI","RUNE","FET","RNDR","TAO","WLD","STRK","JUP",
                       "JTO","PENDLE","LDO","AAVE","UNI","EIGEN","ONDO","WIF"]
        results = run(tickers)
        # Convert to list format for aggregator
        output = []
        for ticker, data in results.items():
            output.append({"symbol": ticker, "edge_score": data.get("edge",0),
                          "direction": data.get("direction","NEUTRAL")})
        print(json.dumps(output))
    else:
        run()
