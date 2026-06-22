#!/usr/bin/env python3
"""
Fetch Live Market Data — Trading Module
=========================================
Pulls precise prices from yfinance (free, real-time/15min-delayed).
Writes engine-compatible JSON to /tmp/live_market_data.json
Also outputs portfolio prices for --prices flag.

Usage:
    python3 fetch-prices.py                  # Writes market data JSON
    python3 fetch-prices.py --portfolio      # Outputs --prices JSON for engine.py
    python3 fetch-prices.py --all            # Both

Sources: Yahoo Finance (yfinance) — free, no API key needed.
Limitations: Commodities 15-min delayed. Crypto not included (use ccxt).
"""

import json
import sys
import os
import time
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print("yfinance required", file=sys.stderr)
    sys.exit(1)

# ── Retry helper ────────────────────────────────────────────────────

def retry_api(fn, max_attempts=2, delay=2):
    """Call fn with retry on failure. Returns None after exhausting attempts."""
    for attempt in range(max_attempts):
        try:
            result = fn()
            if result is not None:
                return result
        except Exception:
            pass
        if attempt < max_attempts - 1:
            time.sleep(delay)
    return None

# ── Symbol Map ───────────────────────────────────────────────────────────

# Engine market data symbols
MARKET_SYMBOLS = {
    "BZ=F":    "brent_close",      # Brent Crude
    "GC=F":    "gold_spot",        # Gold Futures (spot proxy)
    "GLD":     "gld_price",        # SPDR Gold Shares
    "XLE":     "xle_price",        # Energy Select SPDR
    "XLK":     "xlk_price",        # Technology Select SPDR
    "DX-Y.NYB": "dxy",             # US Dollar Index
    "^VIX":    "vix",              # CBOE Volatility Index
}

# Additional tracker instruments (weekly tracker uses these)
TRACKER_SYMBOLS = {
    # Munificent 7
    "XOM":  "XOM",
    "CVX":  "CVX",
    "COP":  "COP",
    "SHEL": "SHEL",
    "TTE":  "TTE",
    "BP":   "BP",
    "EQNR": "EQNR",
    # Magnificent 7
    "AAPL":  "AAPL",
    "MSFT":  "MSFT",
    "GOOGL": "GOOGL",
    "AMZN":  "AMZN",
    "NVDA":  "NVDA",
    "META":  "META",
    "TSLA":  "TSLA",
    # Benchmarks
    "SPY": "SPY",
    "QQQ": "QQQ",
}

# AI Supercycle thesis tracker instruments
AI_TRACKER_SYMBOLS = {
    # 5 Layer ETFs
    "SOXX": "SOXX",
    "IGV":  "IGV",
    "DTCR": "DTCR",
    "TAN":  "TAN",
    "XLC":  "XLC",
    # Conviction stocks
    "INTC": "INTC",
    "CRWV": "CRWV",
    "BE":   "BE",
    "CORZ": "CORZ",
    # AI Benchmarks
    "XLK": "XLK",
}

# Portfolio position symbols (for --prices output)
PORTFOLIO_SYMBOLS = ["GLD", "XLE", "IBIT", "ETHA", "SOXX", "IGV", "DTCR", "TAN", "XLC"]


def _yf_download(*args, **kwargs):
    """yfinance download with single retry on failure."""
    for attempt in range(2):
        try:
            data = yf.download(*args, **kwargs)
            if not data.empty:
                return data
        except Exception:
            pass
        if attempt == 0:
            time.sleep(2)
    return yf.download(*args, **kwargs)  # last attempt, let it fail naturally


def fetch_prices(symbols: dict, period: str = "5d") -> dict:
    """Fetch latest close prices for given symbols. Returns {key: price}."""
    tickers = list(symbols.keys())
    result = {}

    try:
        data = _yf_download(tickers, period=period, progress=False, auto_adjust=True)

        for ticker in tickers:
            key = symbols[ticker]
            try:
                if len(tickers) == 1:
                    close = data["Close"].iloc[-1]
                else:
                    close = data["Close"][ticker].dropna().iloc[-1]
                result[key] = round(float(close), 2)
            except (IndexError, KeyError):
                result[key] = None
    except Exception as e:
        print(f"⚠ yfinance fetch error: {e}", file=sys.stderr)
        for key in symbols.values():
            result[key] = None

    return result


def compute_sma(symbol: str, window: int = 50) -> float:
    """Compute simple moving average."""
    try:
        data = _yf_download(symbol, period=f"{window+10}d", progress=False, auto_adjust=True)
        closes = data["Close"].dropna()
        if len(closes) >= window:
            return round(float(closes.iloc[-window:].mean()), 2)
    except Exception:
        pass
    return None


def build_market_data(prices: dict) -> dict:
    """Build the full market_data dict that engine.py expects.
    
    When yfinance fails, prices dict contains None values — we propagate
    them as None so consumers can detect stale data."""
    
    brent = prices.get("brent_close")
    gold_spot = prices.get("gold_spot")
    xle = prices.get("xle_price")
    xlk = prices.get("xlk_price")
    dxy = prices.get("dxy")
    vix = prices.get("vix")
    gld = prices.get("gld_price")

    # Flag stale data — consumers should check this before trading
    stale_fields = [k for k, v in prices.items() if v is None]
    if stale_fields:
        print(f"WARNING: {len(stale_fields)} price fields are None (yfinance failure): {stale_fields[:5]}...")

    # Compute Brent 50-day SMA
    brent_sma = compute_sma("BZ=F", 50)

    # Compute XLE/XLK ratio — null-safe
    xle_xlk_ratio = round(xle / xlk, 4) if (xle and xlk and xlk > 0) else None

    # DXY direction (check last 5 sessions)
    dxy_rising = False
    dxy_falling = False
    try:
        dxy_data = yf.download("DX-Y.NYB", period="10d", progress=False, auto_adjust=True)
        closes = dxy_data["Close"].dropna()
        if len(closes) >= 6:
            recent = closes.iloc[-5:].mean()
            prior = closes.iloc[-10:-5].mean()
            if recent > prior * 1.001:
                dxy_rising = True
            elif recent < prior * 0.999:
                dxy_falling = True
    except Exception:
        pass

    # Real rates direction (approximate via TIP ETF vs nominal bonds)
    real_rates = "unknown"
    try:
        tip_data = yf.download("TIP", period="5d", progress=False, auto_adjust=True)
        if len(tip_data["Close"].dropna()) >= 2:
            tip_close = tip_data["Close"].dropna()
            if tip_close.iloc[-1] < tip_close.iloc[-2]:
                real_rates = "rising"  # TIPS price falling = real yield rising
            elif tip_close.iloc[-1] > tip_close.iloc[-2]:
                real_rates = "falling"
    except Exception:
        pass

    # Energy sector weight — not easily derivable from price alone.
    # Correct value: ~4.1% of S&P 500 (from Slickcharts, updated quarterly).
    # Using fixed estimate. Override via web_search if precision needed.
    energy_weight = 0.041  # Current: ~4.1% (May 2026)

    # Mun7 FCF yield (approximate — would need actual earnings data)
    # Using Currie's estimate of ~15.5% at $105 oil
    mun7_fcf = 0.155
    if brent and brent > 0:
        mun7_fcf = round(0.155 * (brent / 105), 4)  # Scale with oil price

    return {
        "brent_close": brent,
        "brent_50sma": brent_sma,
        "mun7_fcf_yield": mun7_fcf,
        "xle_xlk_ratio_higher_low": False,  # Needs weekly comparison
        "xle_xlk_ratio": xle_xlk_ratio,
        "energy_weight": energy_weight,
        "gold": gold_spot,
        "dxy": dxy,
        "dxy_rising": dxy_rising,
        "dxy_falling": dxy_falling,
        "real_rates": real_rates,
        "vix": vix,
        "cb_dovish": False,
        "hormuz_reopen_news": False,
        "mag7_capex_drop": 0.0,
        "brent_contango_4w": False,
        "brent_volume_surge": False,
        "mun7_price": xle,
        "xle_price": xle,
        # Tracker extras
        "gld_price": gld,
        "gold_spot": gold_spot,
        "_fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
    }


def build_portfolio_prices(market_prices: dict) -> dict:
    """Build prices dict for engine.py --prices flag.
    Fetches prices for all portfolio symbols and returns {symbol: price}."""
    # Fetch portfolio-specific symbols not in MARKET_SYMBOLS
    extra_symbols = {
        "IBIT": "IBIT",
        "ETHA": "ETHA",
        "SOXX": "SOXX",
        "IGV":  "IGV",
        "DTCR": "DTCR",
        "TAN":  "TAN",
        "XLC":  "XLC",
    }
    extra_prices = fetch_prices(extra_symbols, period="5d")
    
    result = {}
    # From market data
    if market_prices.get("gld_price"):
        result["GLD"] = market_prices["gld_price"]
    if market_prices.get("xle_price"):
        result["XLE"] = market_prices["xle_price"]
    
    # From extra fetch
    for sym in PORTFOLIO_SYMBOLS:
        if sym in ("GLD", "XLE"):
            continue
        px = extra_prices.get(sym)
        if px and px > 0:
            result[sym] = px
    
    return result


def fetch_tracker_prices() -> dict:
    """Fetch all tracker instrument prices for weekly report."""
    prices = fetch_prices(TRACKER_SYMBOLS, period="5d")
    return prices


# ── Main ──

def main():
    do_all = "--all" in sys.argv
    portfolio_only = "--portfolio" in sys.argv

    # Fetch core market data
    market_prices = fetch_prices(MARKET_SYMBOLS, period="5d")
    market_data = build_market_data(market_prices)

    # Write market data JSON
    output_path = "/tmp/live_market_data.json"
    with open(output_path, "w") as f:
        json.dump(market_data, f, indent=2)
    print(f"✅ Market data written to {output_path}")

    # Print summary
    print(f"   Brent: ${market_data['brent_close']} (50-SMA: ${market_data['brent_50sma']})")
    print(f"   Gold:  ${market_data['gold']:,} | GLD: ${market_prices.get('gld_price', '?')}")
    print(f"   DXY:   {market_data['dxy']} ({'↑' if market_data['dxy_rising'] else '↓' if market_data['dxy_falling'] else '→'})")
    print(f"   VIX:   {market_data['vix']}")
    print(f"   XLE:   ${market_data['xle_price']} | XLK: ${market_prices.get('xlk_price', '?')}")
    print(f"   Real rates: {market_data['real_rates']}")

    if portfolio_only or do_all:
        port_prices = build_portfolio_prices(market_prices)
        price_json = json.dumps(port_prices)
        print(f"\n📊 Portfolio prices: {price_json}")
        # Also write to a file for cron use
        with open("/tmp/portfolio_prices.json", "w") as f:
            f.write(price_json)

    if do_all:
        tracker = fetch_tracker_prices()
        tracker_path = "/tmp/tracker_prices.json"
        with open(tracker_path, "w") as f:
            json.dump(tracker, f, indent=2)
        print(f"\n✅ Tracker prices written to {tracker_path}")
        print(f"   Mun7: XOM ${tracker.get('XOM','?')} CVX ${tracker.get('CVX','?')} ...")
        print(f"   Mag7: AAPL ${tracker.get('AAPL','?')} MSFT ${tracker.get('MSFT','?')} ...")

        # AI thesis tracker
        ai_tracker = fetch_prices(AI_TRACKER_SYMBOLS, period="5d")
        ai_path = "/tmp/ai_tracker_prices.json"
        with open(ai_path, "w") as f:
            json.dump(ai_tracker, f, indent=2)
        print(f"\n✅ AI Tracker prices written to {ai_path}")
        print(f"   ETFs: SOXX ${ai_tracker.get('SOXX','?')} IGV ${ai_tracker.get('IGV','?')} DTCR ${ai_tracker.get('DTCR','?')}")
        print(f"   Conviction: INTC ${ai_tracker.get('INTC','?')} BE ${ai_tracker.get('BE','?')} CORZ ${ai_tracker.get('CORZ','?')}")


if __name__ == "__main__":
    main()
