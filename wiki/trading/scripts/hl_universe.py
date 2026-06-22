#!/usr/bin/env python3
"""Hyperliquid Universe Fetcher — v12.0

Fetches all perpetual markets from Hyperliquid API.
Filters: active (non-delisted), sorted by 24h volume.
Output: /tmp/hl_universe.json

Data from Hyperliquid: POST https://api.hyperliquid.xyz/info {"type":"metaAndAssetCtxs"}

Usage:
    python3 scripts/hl_universe.py          # Fetch + write JSON
    python3 scripts/hl_universe.py --count  # Just print instrument count
"""

import json, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
OUTPUT = Path("/tmp/hl_universe.json")
API_URL = "https://api.hyperliquid.xyz/info"

# Top instruments (hardcoded fallback if API unavailable)
# Source: hyperliquidguide.com/markets — June 2026
TOP_NATIVE = [
    "BTC", "ETH", "SOL", "HYPE", "XRP", "DOGE", "AVAX", "LINK", "ADA",
    "NEAR", "TON", "SUI", "APT", "ARB", "OP", "MATIC", "DOT", "ATOM",
    "WIF", "BONK", "PEPE", "SHIB", "SEI", "INJ", "TIA", "RUNE", "FET",
    "RNDR", "TAO", "WLD", "STRK", "JUP", "PYTH", "JTO", "ENA", "PENDLE",
    "LDO", "AAVE", "UNI", "CRV", "SNX", "GMX", "DYDX", "MKR", "COMP",
    "LTC", "BCH", "ETC", "FIL", "ICP", "QNT", "ZEC", "LIT", "ZRO",
    "EIGEN", "OM", "ONDO", "BEAM", "AKT", "GALA", "SAND", "MANA",
    "AXS", "IMX", "APE", "BLUR", "ORDI", "SATS", "RATS",
]

TOP_HIP3 = [
    "NVDA", "INTC", "SP500", "Nasdaq", "WTI", "Brent", "Silver",
    "MU", "PLTR", "SMSN", "SKHX", "RKLB", "SPCX", "WesternDigital",
    "Cerebras", "DRAM", "Wheat", "Aluminium", "VOL", "USAR",
]


def fetch_hl_universe():
    """Fetch full universe from Hyperliquid API. Returns list of dicts."""
    try:
        body = json.dumps({"type": "metaAndAssetCtxs"}).encode()
        req = urllib.request.Request(API_URL, data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "Hermes/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            meta = data[0]
            contexts = data[1]
            universe = meta.get("universe", [])
            
            # Merge with asset contexts (funding, OI, volume, mark price)
            for i, asset in enumerate(universe):
                if i < len(contexts):
                    ctx = contexts[i]
                    asset["markPx"] = ctx.get("markPx", "0")
                    asset["funding"] = ctx.get("funding", "0")
                    asset["openInterest"] = ctx.get("openInterest", "0")
                    asset["dayNtlVlm"] = ctx.get("dayNtlVlm", "0")
                    asset["prevDayPx"] = ctx.get("prevDayPx", "0")
            
            return universe
    except Exception as e:
        print(f"⚠️ HL API unavailable: {e}", file=sys.stderr)
        return None


def build_universe():
    """Build filtered, sorted universe. Falls back to hardcoded list."""
    assets = fetch_hl_universe()
    
    if assets:
        # Filter: active, non-delisted
        active = [a for a in assets if not a.get("isDelisted", False)]
        
        # Sort by 24h volume (native), descending
        active.sort(key=lambda a: float(a.get("dayNtlVlm", 0)), reverse=True)
        
        # Categorize: native vs HIP-3
        native = [a for a in active if not a["name"].startswith("0x") and ":" not in a["name"]]
        hip3 = [a for a in active if ":" in a["name"] or a["name"] in TOP_HIP3]
        
        output = {
            "fetched_at": datetime.now(IST).isoformat(),
            "total": len(assets),
            "active": len(active),
            "native_count": len(native),
            "hip3_count": len(hip3),
            "native": [{"name": a["name"], "markPx": float(a.get("markPx", 0)),
                        "funding": float(a.get("funding", 0)),
                        "openInterest": float(a.get("openInterest", 0)),
                        "volume24h": float(a.get("dayNtlVlm", 0)),
                        "maxLeverage": a.get("maxLeverage", 10)}
                       for a in native[:100]],
            "hip3": [{"name": a["name"], "markPx": float(a.get("markPx", 0)),
                      "funding": float(a.get("funding", 0)),
                      "volume24h": float(a.get("dayNtlVlm", 0))}
                     for a in hip3[:50]],
        }
    else:
        # Fallback: hardcoded top instruments
        output = {
            "fetched_at": datetime.now(IST).isoformat(),
            "source": "hardcoded-fallback",
            "total": len(TOP_NATIVE) + len(TOP_HIP3),
            "active": len(TOP_NATIVE) + len(TOP_HIP3),
            "native_count": len(TOP_NATIVE),
            "hip3_count": len(TOP_HIP3),
            "native": [{"name": n, "markPx": 0, "funding": 0, "openInterest": 0,
                        "volume24h": 0, "maxLeverage": 10}
                       for n in TOP_NATIVE],
            "hip3": [{"name": n, "markPx": 0, "funding": 0, "volume24h": 0}
                     for n in TOP_HIP3],
        }
    
    OUTPUT.write_text(json.dumps(output, indent=2))
    return output


def main():
    if "--count" in sys.argv:
        if OUTPUT.exists():
            data = json.loads(OUTPUT.read_text())
            print(f"Hyperliquid instruments: {data['active']} active ({data['native_count']} native + {data['hip3_count']} HIP-3)")
        else:
            print("No cached universe. Run without --count first.")
        return
    
    data = build_universe()
    print(f"Hyperliquid Universe: {data['active']} active instruments")
    print(f"  Native: {data['native_count']} (top 100 saved)")
    print(f"  HIP-3:  {data['hip3_count']} (top 50 saved)")
    print(f"  Output: {OUTPUT}")
    
    # Show top 10 by volume
    print("\nTop 10 by 24h volume:")
    for i, a in enumerate(data["native"][:10]):
        vol = a.get("volume24h", 0)
        mark = a.get("markPx", 0)
        fund = a.get("funding", 0)
        print(f"  {i+1}. {a['name']:8s}  mark=${mark:,.2f}  vol=${vol:,.0f}  fund={fund*100:.4f}%")


if __name__ == "__main__":
    main()
