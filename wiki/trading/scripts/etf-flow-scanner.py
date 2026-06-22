#!/usr/bin/env python3
"""ETF Flow Scanner — tracks weekly BTC/ETH ETF net flows for crypto thesis v2.

Computes: aggregate weekly net flows from IBIT, FBTC, GBTC, ETHA, etc.
Normalizes to % of BTC market cap for regime-aware threshold (0.03%).

Output: /tmp/etf_flows.json
  { btc_mcap, weekly_flows_m, flows_pct_mcap, consecutive_weeks_positive,
    signals: {E1_firing, X1_firing}, checked_at }

Run: daily at 8:50 AM IST (before thesis check).
"""

import json
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Install: pip install yfinance --break-system-packages")
    sys.exit(1)

IST = timezone(timedelta(hours=5, minutes=30))

# ETF tickers for BTC
BTC_ETFS = ["IBIT", "FBTC", "GBTC", "BITB", "ARKB", "BTCO", "EZBC", "BRRR", "HODL", "BTCW"]
ETH_ETFS = ["ETHA", "FETH", "ETHW", "CETH", "ETHV", "QETH"]

OUTPUT_PATH = Path("/tmp/etf_flows.json")
HISTORY_PATH = Path("/tmp/etf_flows_history.json")


def now_ist():
    return datetime.now(IST)


def load_history():
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return {"weeks": []}


def save_history(data):
    HISTORY_PATH.write_text(json.dumps(data, indent=2, default=str))


def get_weekly_volume(ticker):
    """Get trailing 5-day volume × avg price for a ticker."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            return 0.0, 0.0
        
        avg_price = hist["Close"].mean()
        total_volume = hist["Volume"].sum()
        flow = avg_price * total_volume  # rough net flow estimate
        return flow, avg_price
    except Exception:
        return 0.0, 0.0


def get_btc_market_cap():
    """Get BTC market cap from CoinGecko free API."""
    try:
        import urllib.request
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_market_cap=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("bitcoin", {}).get("usd_market_cap", 0) or 0
    except Exception as e:
        print(f"  ⚠ CoinGecko API failed: {e}")
        return 0


def main():
    print("ETF Flow Scanner — Crypto Thesis v2")
    print(f"  {now_ist().strftime('%Y-%m-%d %H:%M IST')}")
    
    # Get BTC market cap
    btc_mcap = get_btc_market_cap()
    print(f"  BTC market cap: ${btc_mcap:,.0f}" if btc_mcap else "  BTC market cap: UNAVAILABLE")
    
    # Compute weekly flows for BTC ETFs
    total_flows = 0.0
    for ticker in BTC_ETFS:
        flow, _ = get_weekly_volume(ticker)
        total_flows += flow
    
    print(f"  Weekly BTC ETF flows: ${total_flows:,.0f}")
    
    # Normalize to % of BTC mcap
    flows_pct = (total_flows / btc_mcap * 100) if btc_mcap > 0 else None
    if flows_pct is not None:
        print(f"  As % of BTC mcap: {flows_pct:.4f}%")
    
    # Determine threshold
    threshold_pct = 0.03
    threshold_dollars = btc_mcap * threshold_pct / 100 if btc_mcap > 0 else 0
    print(f"  Threshold (0.03%): ${threshold_dollars:,.0f}")
    
    # Load history
    history = load_history()
    
    # Determine if E1 fires
    e1_firing = (flows_pct is not None and flows_pct > threshold_pct)
    
    # Track consecutive weeks
    if e1_firing:
        history["consecutive_positive_weeks"] = history.get("consecutive_positive_weeks", 0) + 1
    else:
        history["consecutive_positive_weeks"] = 0
    
    # E1 requires 2 consecutive weeks
    e1_confirmed = history["consecutive_positive_weeks"] >= 2
    
    # X1 fires if outflows > threshold for 2 weeks
    x1_firing = not e1_firing and history.get("consecutive_negative_weeks", 0) >= 1
    if not e1_firing:
        history["consecutive_negative_weeks"] = history.get("consecutive_negative_weeks", 0) + 1
    else:
        history["consecutive_negative_weeks"] = 0
    
    # Build output
    result = {
        "checked_at": now_ist().isoformat(),
        "btc_market_cap": btc_mcap,
        "weekly_flows_usd": round(total_flows, 2),
        "flows_pct_mcap": round(flows_pct, 6) if flows_pct else None,
        "threshold_pct": threshold_pct,
        "threshold_usd": round(threshold_dollars, 2),
        "signals": {
            "E1_firing": e1_confirmed,  # requires 2 consecutive weeks
            "E1_this_week": e1_firing,
            "X1_firing": x1_firing,
        },
        "consecutive_weeks": history["consecutive_positive_weeks"],
    }
    
    # Write output
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, default=str))
    print(f"  Output: {OUTPUT_PATH}")
    
    # Update history
    week_id = now_ist().strftime("%Y-W%W")
    history["weeks"].append({
        "week": week_id,
        "flows_usd": round(total_flows, 2),
        "flows_pct": round(flows_pct, 6) if flows_pct else None,
        "e1_firing": e1_firing,
    })
    # Keep last 52 weeks
    history["weeks"] = history["weeks"][-52:]
    save_history(history)
    
    # Signal summary
    print(f"\n  E1 (Accumulation): {'🔥 FIRING' if e1_confirmed else ('⚡ this week' if e1_firing else '— idle')}")
    print(f"  X1 (Retreat):      {'🚨 FIRING' if x1_firing else '— idle'}")
    
    return result


if __name__ == "__main__":
    main()
