#!/usr/bin/env python3
"""
Quant Module #9 — Event-Driven (Hyperliquid)
===============================================
Funding rate extremes, liquidation/volume events, OI divergences.
Data: Hyperliquid public info API (no auth, one call for all assets).

Signals:
  - FUNDING_EXTREME: perp funding far from neutral → contrarian
  - VOLUME_SURGE: elevated 24h volume → event-driven opportunity
  - PREMIUM_EXTREME: large premium/discount vs oracle → dislocation
  - OI_DIVERGENCE: high OI + extreme funding = crowded positioning

Edge: React to structural events, not predict price direction.

Usage:
    python3 event-driven.py BTC-USD
    python3 event-driven.py --all
    python3 event-driven.py --json
"""

import sys
import json
import urllib.request
from typing import Dict, List, Optional

try:
    from tickers import QUANT_UNIVERSE as SYMBOLS
except Exception:
    SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD",
               "AVAX-USD", "ADA-USD", "XRP-USD", "DOGE-USD"]

HL_API = "https://api.hyperliquid.xyz/info"

# Map our symbols to Hyperliquid asset names
SYMBOL_TO_HL = {
    "BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL",
    "LINK-USD": "LINK", "AVAX-USD": "AVAX", "ADA-USD": "ADA",
    "XRP-USD": "XRP", "DOGE-USD": "DOGE",
}

# ── Hyperliquid API ────────────────────────────────────────────────────

_cache: Optional[Dict] = None

def hl_get_contexts() -> Optional[Dict]:
    """Fetch metaAndAssetCtxs — one call for all asset data.
    Returns dict mapping ticker name → context dict."""
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

    # Build name → context map
    result = {}
    for i, asset in enumerate(universe):
        name = asset.get("name", "") if isinstance(asset, dict) else str(asset)
        if i < len(ctxs):
            ctx = ctxs[i]
            impact = ctx.get("impactPxs") or [ctx.get("midPx") or 0, ctx.get("midPx") or 0]
            result[name] = {
                "funding": float(ctx.get("funding") or 0),
                "openInterest": float(ctx.get("openInterest") or 0),
                "markPx": float(ctx.get("markPx") or 0),
                "midPx": float(ctx.get("midPx") or 0),
                "oraclePx": float(ctx.get("oraclePx") or 0),
                "premium": float(ctx.get("premium") or 0),
                "dayNtlVlm": float(ctx.get("dayNtlVlm") or 0),
                "dayBaseVlm": float(ctx.get("dayBaseVlm") or 0),
                "prevDayPx": float(ctx.get("prevDayPx") or 0),
                "impactBid": float(impact[0]) if len(impact) > 0 and impact[0] is not None else 0,
                "impactAsk": float(impact[1]) if len(impact) > 1 and impact[1] is not None else 0,
            }

    _cache = result
    return result


# ── Edge Scoring ──────────────────────────────────────────────────────

def score_events(symbol: str) -> Dict:
    hl_name = SYMBOL_TO_HL.get(symbol, "BTC")
    ctxs = hl_get_contexts()

    edge = 0
    signals = []
    funding_pct = 0.0
    oi = 0.0
    volume_24h = 0.0

    if ctxs and hl_name in ctxs:
        ctx = ctxs[hl_name]
        funding = ctx["funding"]          # raw funding rate (e.g. 0.00001 = 0.001%)
        funding_pct = funding * 100        # convert to %
        oi = ctx["openInterest"]
        premium = ctx["premium"]
        mark = ctx["markPx"]
        oracle = ctx["oraclePx"]
        volume_24h = ctx["dayNtlVlm"]

        # 1. Funding rate extreme
        if abs(funding_pct) > 0.05:
            edge += 25
            direction_flag = "SHORT" if funding_pct > 0 else "LONG"
            signals.append(f"funding_extreme_{direction_flag.lower()}")
        elif abs(funding_pct) > 0.02:
            edge += 10
            signals.append("funding_elevated")
        else:
            edge += 5  # neutral funding = healthy

        # 2. Premium vs oracle — dislocation signal
        premium_pct = abs(premium) * 100
        if premium_pct > 0.5:  # > 0.5% dislocation
            edge += 20
            signals.append("premium_extreme")
        elif premium_pct > 0.2:
            edge += 10
            signals.append("premium_elevated")

        # 3. Volume surge — event-driven activity
        if volume_24h > 500_000_000:  # $500M+ daily notional
            edge += 20
            signals.append("volume_surge")
        elif volume_24h > 100_000_000:
            edge += 10
            signals.append("volume_elevated")

        # 4. OI level scoring — high OI + extreme funding = crowded
        oi_millions = oi / 1_000_000
        if oi_millions > 0:
            oi_score = min(10, int(oi_millions))
            if abs(funding_pct) > 0.03:
                oi_score += 5  # high OI with extreme funding = more signal
            edge += oi_score
    else:
        # API failure — no data available, don't fabricate signals
        signals.append("data_unavailable")

    # Direction: contrarian on funding
    if funding_pct > 0.05:
        direction = "SELL"   # positive funding = longs paying shorts = crowded long
    elif funding_pct < -0.05:
        direction = "BUY"    # negative funding = shorts paying longs = crowded short
    elif funding_pct > 0.03:
        direction = "SLIGHTLY_BEARISH"
    elif funding_pct < -0.03:
        direction = "SLIGHTLY_BULLISH"
    else:
        direction = "NEUTRAL"

    # If no data, score is 0
    if "data_unavailable" in signals:
        edge = 0
        direction = "NEUTRAL"

    edge = max(0, min(100, edge))

    return {
        "edge_score": edge,
        "direction": direction,
        "recommended_size_pct": min(15, max(0, edge - 40)) if direction != "NEUTRAL" else 0,
        "close": 0,  # aggregator fills from other modules
        "funding_rate_pct": round(funding_pct, 4),
        "open_interest_m": round(oi / 1_000_000, 2),
        "volume_24h_m": round(volume_24h / 1_000_000, 1),
        "signals": signals,
    }


# ── Main ──────────────────────────────────────────────────────────────

def main():
    json_mode = "--json" in sys.argv
    all_mode = "--all" in sys.argv
    symbols = SYMBOLS if all_mode else [sys.argv[1]] if len(sys.argv) > 1 else [SYMBOLS[0]]

    results = []
    for sym in symbols:
        s = score_events(sym)
        s["symbol"] = sym
        results.append(s)

    if json_mode:
        output = results[0] if not all_mode and len(results) == 1 else results
        print(json.dumps(output, indent=2))
    else:
        for r in results:
            print(f"  {r['symbol']:8s} | edge={r['edge_score']:3d} | {r['direction']:16s} | "
                  f"fund={r['funding_rate_pct']:+.4f}% | OI={r['open_interest_m']:.1f}M | "
                  f"vol={r['volume_24h_m']:.0f}M | size={r['recommended_size_pct']:.0f}%")
            if r["signals"]:
                print(f"         → {', '.join(r['signals'])}")


if __name__ == "__main__":
    main()
