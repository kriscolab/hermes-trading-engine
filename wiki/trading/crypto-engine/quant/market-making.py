#!/usr/bin/env python3
"""
Quant Module #8 — Market Making (Hyperliquid)
================================================
Spread analysis, depth proxy, inventory risk.
Uses Hyperliquid metaAndAssetCtxs for spread/depth data.

Usage:
    python3 market-making.py BTC-USD
    python3 market-making.py --all
    python3 market-making.py --json
"""

import sys
import json
import urllib.request
import numpy as np
from typing import Dict, Optional

try:
    import yfinance as yf
except ImportError:
    print("yfinance required", file=sys.stderr)
    sys.exit(1)

try:
    from tickers import QUANT_UNIVERSE as SYMBOLS
except Exception:
    SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD",
               "AVAX-USD", "ADA-USD", "XRP-USD", "DOGE-USD"]

PERIOD = "60d"
HL_API = "https://api.hyperliquid.xyz/info"

SYMBOL_TO_HL = {
    "BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL",
    "LINK-USD": "LINK", "AVAX-USD": "AVAX", "ADA-USD": "ADA",
    "XRP-USD": "XRP", "DOGE-USD": "DOGE",
}

_cache: Optional[Dict] = None


def _safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def hl_get_contexts() -> Optional[Dict]:
    global _cache
    if _cache is not None:
        return _cache
    payload = json.dumps({"type": "metaAndAssetCtxs"}).encode()
    try:
        req = urllib.request.Request(HL_API, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    if not isinstance(data, list) or len(data) < 2:
        return None
    universe = data[0].get("universe", []) if isinstance(data[0], dict) else data[0]
    ctxs = data[1]
    result = {}
    for i, asset in enumerate(universe):
        name = asset.get("name", "") if isinstance(asset, dict) else str(asset)
        if i < len(ctxs):
            ctx = ctxs[i]
            impact = ctx.get("impactPxs") or [0, 0]
            result[name] = {
                "midPx": _safe_float(ctx.get("midPx")),
                "markPx": _safe_float(ctx.get("markPx")),
                "oraclePx": _safe_float(ctx.get("oraclePx")),
                "premium": _safe_float(ctx.get("premium")),
                "funding": _safe_float(ctx.get("funding")),
                "dayNtlVlm": _safe_float(ctx.get("dayNtlVlm")),
                "impactBid": _safe_float(impact[0]) if len(impact) > 0 else 0,
                "impactAsk": _safe_float(impact[1]) if len(impact) > 1 else 0,
            }
    _cache = result
    return result


def fetch(symbol):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def score_market_making(symbol: str, df) -> Dict:
    hl_name = SYMBOL_TO_HL.get(symbol, "BTC")
    ctxs = hl_get_contexts()
    c = df["Close"].values
    v = df["Volume"].values

    log_ret = np.diff(np.log(c))
    vol_14 = float(np.std(log_ret[-14:]) * np.sqrt(365 * 24)) if len(log_ret) >= 14 else 0

    if ctxs and hl_name in ctxs:
        ctx = ctxs[hl_name]
        mid = ctx["midPx"]
        spread_bps = (ctx["impactAsk"] - ctx["impactBid"]) / mid * 10000 if mid > 0 else 1
        if spread_bps <= 0:
            spread_bps = abs(ctx["premium"]) * 10000 * 0.5 or 1
        vol_24h = ctx["dayNtlVlm"]
        last = mid
    else:
        spread_bps = 5
        last = float(c[-1])
        vol_24h = 0

    avg_vol_20 = float(np.mean(v[-20:])) if len(v) >= 20 else float(v[-1])
    vol_ratio = float(v[-1]) / avg_vol_20 if avg_vol_20 > 0 else 1

    edge = 0
    signals = []
    hourly_vol_bps = vol_14 * 100

    if spread_bps > 0 and hourly_vol_bps > 0:
        spread_vol_ratio = spread_bps / hourly_vol_bps
        if spread_vol_ratio > 1.5:
            edge += 30; signals.append("wide_spread")
        elif spread_vol_ratio > 0.8:
            edge += 15; signals.append("fair_spread")
        elif spread_vol_ratio < 0.3:
            edge -= 10; signals.append("tight_spread")
    else:
        spread_vol_ratio = 1

    if vol_ratio > 1.5:
        edge += 10; signals.append("high_volume")
    elif vol_ratio < 0.5:
        edge -= 10; signals.append("low_volume")

    if last < 100:
        edge += 10; signals.append("small_tick")
    elif last > 10000:
        edge -= 5

    if vol_24h > 100_000_000:
        edge += 15; signals.append("deep_market")
    elif vol_24h > 10_000_000:
        edge += 5
    elif 0 < vol_24h < 1_000_000:
        edge -= 10; signals.append("thin_market")

    direction = "PROVIDE_LIQUIDITY" if edge > 50 else ("NEUTRAL" if edge > 30 else "TAKE_LIQUIDITY")
    edge = max(0, min(100, edge + 30))

    return {
        "edge_score": edge,
        "direction": direction,
        "recommended_size_pct": min(10, max(0, edge - 30)) if direction == "PROVIDE_LIQUIDITY" else 0,
        "close": float(last),
        "spread_bps": round(float(spread_bps), 2),
        "spread_vol_ratio": round(float(spread_vol_ratio), 2),
        "hourly_vol_bps": round(float(hourly_vol_bps), 2),
        "volume_24h_m": round(float(vol_24h) / 1_000_000, 2),
        "signals": signals,
    }


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
        s = score_market_making(sym, df)
        s["symbol"] = sym
        results.append(s)
    if json_mode:
        output = results[0] if not all_mode and len(results) == 1 else results
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            if "error" in r:
                print(f"  {r['symbol']}: error")
                continue
            print(f"  {r['symbol']:8s} | edge={r['edge_score']:3d} | {r['direction']:18s} | "
                  f"spread={r['spread_bps']:.1f}bps | s/v={r['spread_vol_ratio']:.1f}x | "
                  f"vol24h=${r['volume_24h_m']:.1f}M | size={r['recommended_size_pct']:.0f}%")


if __name__ == "__main__":
    import pandas as pd
    main()
