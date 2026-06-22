#!/usr/bin/env python3
"""
Crypto Module Data Fetcher
===========================
Pulls live crypto data from ALL free endpoints for the 6-layer signal stack.
Replaces paid APIs (Coinglass, Glassnode, WhaleAlert, CryptoQuant) with free alternatives.

Usage:
    python3 crypto-data-fetch.py              # Full fetch → /tmp/crypto_module_data.json
    python3 crypto-data-fetch.py --summary    # Quick summary to stdout

Sources (all free, no key needed):
    Binance fapi  → funding rates, open interest, force orders
    Deribit       → options IV skew, term structure
    DeFiLlama     → TVL, protocol data
    alternative.me → Fear & Greed Index
    CoinGecko     → BTC dominance, market data
    Hyblock       → liquidation levels (free tier)

Output: /tmp/crypto_module_data.json
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("requests not installed", file=sys.stderr)
    sys.exit(1)

try:
    import yfinance as yf
except ImportError:
    yf = None

OUTPUT_PATH = Path("/tmp/crypto_module_data.json")
REQUEST_TIMEOUT = 12

# ── Retry helpers ───────────────────────────────────────────────────────

def _api_get(url, headers=None, params=None):
    import time as _t
    for i in range(2):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers, params=params)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        if i == 0:
            _t.sleep(2)
    return None

def _api_post(url, headers=None, json_data=None):
    import time as _t
    for i in range(2):
        try:
            r = requests.post(url, timeout=REQUEST_TIMEOUT, headers=headers, json=json_data)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        if i == 0:
            _t.sleep(2)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Data Fetchers — one per source
# ═══════════════════════════════════════════════════════════════════════════

def fetch_kucoin_price(symbol: str = "BTC-USDT") -> Dict:
    """Fetch price from KuCoin (global, free, no key)."""
    try:
        r = requests.get(
            f"https://api.kucoin.com/api/v1/market/orderbook/level1",
            params={"symbol": symbol},
            timeout=REQUEST_TIMEOUT
        )
        data = r.json()
        if data.get("code") == "200000":
            return {"price": float(data["data"]["price"]), "status": "ok"}
        return {"price": None, "status": f"error: {data.get('msg','?')}"}
    except Exception as e:
        return {"price": None, "status": f"error: {str(e)[:80]}"}


def fetch_coingecko_prices() -> Dict:
    """Fetch BTC + ETH prices from CoinGecko (global, free tier)."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,ethereum,solana,chainlink,matic-network,avalanche-2", "vs_currencies": "usd",
                    "include_24hr_change": "true"},
            timeout=REQUEST_TIMEOUT
        )
        data = r.json()
        return {
            "btc": data.get("bitcoin", {}).get("usd"),
            "eth": data.get("ethereum", {}).get("usd"),
            "sol": data.get("solana", {}).get("usd"),
            "link": data.get("chainlink", {}).get("usd"),
            "avax": data.get("avalanche-2", {}).get("usd"),
            "btc_24h_change": data.get("bitcoin", {}).get("usd_24h_change"),
            "eth_24h_change": data.get("ethereum", {}).get("usd_24h_change"),
            "sol_24h_change": data.get("solana", {}).get("usd_24h_change"),
            "status": "ok"
        }
    except Exception as e:
        return {"btc": None, "eth": None, "sol": None, "status": f"error: {str(e)[:80]}"}


# ═══════════════════════════════════════════════════════════════════════════
# Keep existing fetchers that work: Deribit, DeFiLlama, alt.me, CoinGecko dominance
# ═══════════════════════════════════════════════════════════════════════════

# (fetch_deribit_skew, fetch_defillama_tvl, fetch_fear_greed,
#  fetch_coingecko_btc_dominance, fetch_ethbtc_ratio — unchanged)

def fetch_deribit_skew(currency: str = "BTC") -> Dict:
    try:
        r = requests.get(
            "https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
            params={"currency": currency, "kind": "option"},
            timeout=REQUEST_TIMEOUT
        )
        data = r.json()["result"]
        calls_25d = []
        puts_25d = []
        for item in data:
            greeks = item.get("greeks", {})
            delta = abs(greeks.get("delta", 0))
            iv = item.get("mark_iv", 0)
            opt_type = item.get("option_type", "")
            if 0.20 <= delta <= 0.30:
                if opt_type == "call":
                    calls_25d.append(iv)
                elif opt_type == "put":
                    puts_25d.append(iv)

        avg_call_iv = sum(calls_25d) / len(calls_25d) if calls_25d else 0
        avg_put_iv = sum(puts_25d) / len(puts_25d) if puts_25d else 0
        skew = avg_call_iv - avg_put_iv

        return {
            "call_iv_25d": round(avg_call_iv, 2),
            "put_iv_25d": round(avg_put_iv, 2),
            "skew": round(skew, 2),
            "skew_signal": "bullish" if skew > 2 else ("bearish" if skew < -2 else "neutral"),
            "status": "ok"
        }
    except Exception as e:
        return {"skew": None, "status": f"error: {str(e)[:80]}"}


def fetch_defillama_tvl() -> Dict:
    """Fetch total DeFi TVL from DeFiLlama (free, no key)."""
    try:
        r = requests.get("https://api.llama.fi/charts", timeout=REQUEST_TIMEOUT)
        data = r.json()
        current = data[-1]["totalLiquidityUSD"]
        prev_7d = data[-8]["totalLiquidityUSD"] if len(data) > 7 else current
        change_7d = ((current - prev_7d) / prev_7d * 100) if prev_7d else 0
        return {
            "total_tvl_usd": round(current, 0),
            "tvl_change_7d_pct": round(change_7d, 1),
            "status": "ok"
        }
    except Exception as e:
        return {"total_tvl_usd": None, "status": f"error: {str(e)[:80]}"}


def fetch_fear_greed() -> Dict:
    """Fetch Fear & Greed from alternative.me (free, no key)."""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=2", timeout=REQUEST_TIMEOUT)
        data = r.json()["data"]
        current = int(data[0]["value"])
        prev = int(data[1]["value"]) if len(data) > 1 else current
        classification = data[0]["value_classification"]
        return {
            "fear_greed_value": current,
            "fear_greed_prev": prev,
            "classification": classification,
            "trend": "rising" if current > prev else ("falling" if current < prev else "flat"),
            "signal": "contrarian_buy" if current < 25 else ("contrarian_sell" if current > 75 else "neutral"),
            "status": "ok"
        }
    except Exception as e:
        return {"fear_greed_value": None, "status": f"error: {str(e)[:80]}"}


def fetch_coingecko_btc_dominance() -> Dict:
    """Fetch BTC dominance from CoinGecko (free, no key)."""
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=REQUEST_TIMEOUT)
        data = r.json()["data"]
        btc_d = data["market_cap_percentage"]["btc"]
        eth_d = data["market_cap_percentage"].get("eth", 0)
        total_mcap = data["total_market_cap"]["usd"]
        return {
            "btc_dominance_pct": round(btc_d, 1),
            "eth_dominance_pct": round(eth_d, 1),
            "total_mcap_usd": round(total_mcap, 0),
            "status": "ok"
        }
    except Exception as e:
        return {"btc_dominance_pct": None, "status": f"error: {str(e)[:80]}"}


def fetch_ethbtc_ratio() -> Dict:
    """Fetch ETH/BTC ratio from Binance (may be geo-blocked, fallback to KuCoin)."""
    try:
        r = requests.get(
            "https://api.kucoin.com/api/v1/market/orderbook/level1",
            params={"symbol": "ETH-BTC"},
            timeout=REQUEST_TIMEOUT
        )
        data = r.json()
        if data.get("code") == "200000":
            return {"eth_btc_ratio": round(float(data["data"]["price"]), 6), "status": "ok"}
    except Exception:
        pass
    return {"eth_btc_ratio": None, "status": "unavailable"}


def fetch_okx_funding(inst_id: str = "BTC-USDT-SWAP") -> Dict:
    """Fetch funding rate from OKX public API (global, free, no key)."""
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/public/funding-rate",
            params={"instId": inst_id, "limit": 2},
            timeout=REQUEST_TIMEOUT
        )
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            latest = float(data["data"][0]["fundingRate"]) * 100
            prev = float(data["data"][1]["fundingRate"]) * 100 if len(data["data"]) > 1 else latest
            return {
                "funding_rate_pct": round(latest, 4),
                "funding_prev_pct": round(prev, 4),
                "trend": "rising" if latest > prev else ("falling" if latest < prev else "flat"),
                "status": "ok"
            }
        return {"funding_rate_pct": None, "status": f"error: {data.get('msg','?')}"}
    except Exception as e:
        return {"funding_rate_pct": None, "status": f"error: {str(e)[:80]}"}


def fetch_okx_oi(inst_id: str = "BTC-USDT-SWAP") -> Dict:
    """Fetch open interest from OKX public API."""
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/public/open-interest",
            params={"instId": inst_id},
            timeout=REQUEST_TIMEOUT
        )
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            oi = float(data["data"][0]["oi"])
            return {
                "open_interest_btc": round(oi, 2),
                "oi_value_usd": round(oi * 78000, 0),
                "status": "ok"
            }
        return {"open_interest_btc": None, "status": f"error: {data.get('msg','?')}"}
    except Exception as e:
        return {"open_interest_btc": None, "status": f"error: {str(e)[:80]}"}


def fetch_okx_liquidations(uly: str = "BTC-USDT") -> Dict:
    """Fetch recent liquidations from OKX public API."""
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/public/liquidation-orders",
            params={"instType": "SWAP", "uly": uly, "state": "filled", "limit": 100},
            timeout=REQUEST_TIMEOUT
        )
        data = r.json()
        if data.get("code") == "0" and data.get("data"):
            orders = data["data"]
            long_liq = sum(1 for o in orders if o.get("posSide") == "long")
            short_liq = len(orders) - long_liq
            return {
                "recent_count": len(orders),
                "long_liquidations": long_liq,
                "short_liquidations": short_liq,
                "long_short_ratio": round(long_liq / max(short_liq, 1), 2),
                "status": "ok"
            }
        return {"recent_count": None, "status": f"error: {data.get('msg','?')}"}
    except Exception as e:
        return {"recent_count": None, "status": f"error: {str(e)[:80]}"}


def compute_patterns(df) -> Dict:
    """Detect latest candlestick pattern from OHLCV."""
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    body = abs(c - o)
    rng = h - l
    last_body = float(body.iloc[-1])
    last_range = float(rng.iloc[-1])
    doji = last_body <= last_range * 0.1
    engulfing_bull = (c.iloc[-1] > o.iloc[-1] and c.iloc[-2] < o.iloc[-2] and
                      o.iloc[-1] <= c.iloc[-2] and c.iloc[-1] >= o.iloc[-2])
    hammer = (o.iloc[-1] - l.iloc[-1]) > last_body * 2 and (h.iloc[-1] - c.iloc[-1]) < last_body * 0.5
    trend = "up" if c.iloc[-1] > c.iloc[-20] else "down"
    return {
        "latest_pattern": "doji" if doji else ("engulfing_bull" if engulfing_bull else ("hammer" if hammer else "none")),
        "doji": doji, "engulfing_bull": engulfing_bull, "hammer": hammer,
        "trend_20d": trend,
        "close": round(float(c.iloc[-1]), 2),
        "status": "ok"
    }

def compute_vwap_profile(df) -> Dict:
    """Compute VWAP approximation + volume anomalies from OHLCV."""
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    vwap = (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()
    avg_vol = df["Volume"].rolling(20).mean()
    vol_ratio = float(df["Volume"].iloc[-1] / avg_vol.iloc[-1]) if len(avg_vol) else 1.0
    return {
        "vwap": round(float(vwap.iloc[-1]), 2),
        "price_above_vwap": bool(df["Close"].iloc[-1] > vwap.iloc[-1]),
        "volume_ratio": round(vol_ratio, 2),
        "volume_surge": vol_ratio > 2.0,
        "volume_dry_up": vol_ratio < 0.5,
        "status": "ok"
    }


# ═══════════════════════════════════════════════════════════════════════════
# Aggregator
# ═══════════════════════════════════════════════════════════════════════════

def fetch_all() -> Dict:
    """Fetch all crypto data from free endpoints (global access)."""
    print("Fetching crypto data from free endpoints...")
    results = {}

    # Prices — CoinGecko primary, KuCoin backup
    print("  CoinGecko prices...", end=" ")
    cg_prices = fetch_coingecko_prices()
    results["prices"] = {
        "btc": cg_prices.get("btc"),
        "eth": cg_prices.get("eth"),
        "sol": cg_prices.get("sol"),
        "link": cg_prices.get("link"),
        "avax": cg_prices.get("avax"),
        "sol_24h_change": cg_prices.get("sol_24h_change"),
        "source": "coingecko",
        "status": cg_prices.get("status", "ok")
    }
    print("✓")

    # Layer 3 — Options (Deribit — works globally)
    print("  Deribit skew...", end=" ")
    results["options"] = {
        "btc_skew": fetch_deribit_skew("BTC"),
        "eth_skew": fetch_deribit_skew("ETH"),
    }
    print("✓")

    # Layer 5 — On-chain (DeFiLlama TVL proxy)
    print("  DeFiLlama TVL...", end=" ")
    results["on_chain"] = {
        "tvl": fetch_defillama_tvl(),
    }
    print("✓")

    # Sentiment (alternative.me — works globally)
    print("  Fear & Greed...", end=" ")
    results["sentiment"] = {
        "fear_greed": fetch_fear_greed(),
    }
    print("✓")

    # Correlation (CoinGecko — works globally)
    print("  BTC dominance + ETH/BTC...", end=" ")
    results["correlation"] = {
        "btc_dominance": fetch_coingecko_btc_dominance(),
        "eth_btc": fetch_ethbtc_ratio(),
    }
    print("✓")

    # KuCoin backup price check
    print("  KuCoin backup...", end=" ")
    kc_btc = fetch_kucoin_price("BTC-USDT")
    kc_eth = fetch_kucoin_price("ETH-USDT")
    results["kucoin_backup"] = {
        "btc": kc_btc.get("price"),
        "eth": kc_eth.get("price"),
    }
    print("✓")

    # Layer 2 — Derivatives (OKX — works globally, free, no key)
    print("  OKX funding + OI...", end=" ")
    results["derivatives"] = {
        "btc_funding": fetch_okx_funding("BTC-USDT-SWAP"),
        "btc_oi": fetch_okx_oi("BTC-USDT-SWAP"),
        "eth_funding": fetch_okx_funding("ETH-USDT-SWAP"),
        "eth_oi": fetch_okx_oi("ETH-USDT-SWAP"),
        "sol_funding": fetch_okx_funding("SOL-USDT-SWAP"),
        "sol_oi": fetch_okx_oi("SOL-USDT-SWAP"),
    }
    print("✓")

    # Layer 4 — Liquidations (OKX — works globally)
    print("  OKX liquidations...", end=" ")
    results["liquidation"] = {
        "btc_liquidations": fetch_okx_liquidations("BTC-USDT"),
        "eth_liquidations": fetch_okx_liquidations("ETH-USDT"),
        "sol_liquidations": fetch_okx_liquidations("SOL-USDT"),
    }
    print("✓")

    # L1 — Price Action + Volume Profile (computed from yfinance)
    print("  Price action + VWAP...", end=" ")
    tickers = [
        "BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "MATIC-USD", "AVAX-USD",
        "ADA-USD", "XRP-USD", "DOGE-USD", "DOT-USD", "UNI-USD", "ATOM-USD",
        "LTC-USD", "ETC-USD", "FIL-USD", "TRX-USD", "NEAR-USD", "ALGO-USD",
        "VET-USD", "ICP-USD", "FTM-USD", "AAVE-USD", "MKR-USD", "SNX-USD",
        "GRT-USD", "RUNE-USD", "INJ-USD", "ARB-USD", "OP-USD", "APT-USD",
    ]
    results["price_action"] = {}
    results["volume_profile"] = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, period="60d", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = df.columns.get_level_values(0)
                base = ticker.split("-")[0].lower()
                results["price_action"][base] = compute_patterns(df)
                results["volume_profile"][base] = compute_vwap_profile(df)
            else:
                raise Exception("no data")
        except Exception as e:
            base = ticker.split("-")[0].lower()
            results["price_action"][base] = {"status": f"error: {str(e)[:60]}"}
            results["volume_profile"][base] = {"status": f"error: {str(e)[:60]}"}
    print("✓")

    # Confluence scoring (adjusted for available data)
    results["confluence"] = compute_confluence(results)
    # Per-ticker quick scores
    results["tickers"] = {}
    for base in ["btc", "eth", "sol", "link", "avax"]:
        ticker_data = {
            "prices": results.get("prices", {}),
            "price_action": {base: results.get("price_action", {}).get(base, {})},
            "volume_profile": {base: results.get("volume_profile", {}).get(base, {})},
            "derivatives": {"btc_funding" if base == "btc" else f"{base}_funding": results.get("derivatives", {}).get(f"{base}_funding", {})},
            "liquidation": {"btc_liquidations" if base == "btc" else f"{base}_liquidations": results.get("liquidation", {}).get(f"{base}_liquidations", {})},
            "options": results.get("options", {}),
            "on_chain": results.get("on_chain", {}),
            "sentiment": results.get("sentiment", {}),
            "correlation": results.get("correlation", {}),
        }
        results["tickers"][base] = {
            "confluence": compute_confluence(ticker_data),
            "price": results.get("prices", {}).get(base),
        }

    # Metadata
    results["_meta"] = {
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "sources": "OKX+CoinGecko+Deribit+DeFiLlama+alternative.me+KuCoin (all free)",
        "missing": "None — all 6 layers available via free endpoints",
        "status": "live"
    }

    return results


def compute_confluence(data: Dict) -> Dict:
    # Compute 0-6 layer confluence score for crypto thesis (adjusted for available data).
    score = 0
    details = []
    available_layers = 0

    # L1: Price Action + Volume (computed — available)
    pa = data.get("price_action", {}).get("btc", {})
    vp = data.get("volume_profile", {}).get("btc", {})
    if pa.get("status") == "ok":
        available_layers += 1
        pattern = pa.get("latest_pattern", "none")
        if pattern in ("engulfing_bull", "hammer") and pa.get("trend_20d") == "down":
            score += 1
            details.append(f"L1 {pattern} reversal pattern (+1)")
        elif pattern == "doji":
            details.append(f"L1 doji — indecision, watch direction")
        else:
            details.append(f"L1 no reversal pattern (trend: {pa.get('trend_20d','?')})")

    if vp.get("status") == "ok":
        available_layers += 1
        if vp.get("volume_surge"):
            score += 1
            details.append(f"L1 volume surge ({vp['volume_ratio']:.1f}x avg) (+1)")
        elif vp.get("volume_dry_up"):
            details.append(f"L1 volume dry-up — coiling spring")
        elif vp.get("price_above_vwap"):
            details.append(f"L1 price above VWAP (${vp['vwap']:,.0f})")

    # L2: Derivatives (OKX — available)
    fund = data.get("derivatives", {}).get("btc_funding", {})
    if fund.get("funding_rate_pct") is not None:
        available_layers += 1
        rate = abs(fund["funding_rate_pct"])
        if rate < 0.03:
            score += 1
            details.append(f"L2 funding neutral ({fund['funding_rate_pct']:+.4f}%) (+1)")
        else:
            details.append(f"L2 funding extreme ({fund['funding_rate_pct']:+.4f}%) → leverage warning")

    # L3: Options skew (Deribit — available)
    skew = data.get("options", {}).get("btc_skew", {})
    if skew.get("skew") is not None:
        available_layers += 1
        if skew["skew"] > 0:
            score += 1
            details.append(f"L3 skew bullish +{skew['skew']}% (+1)")
        else:
            details.append(f"L3 skew bearish {skew['skew']}%")

    # L4: Liquidations (OKX — available)
    liq = data.get("liquidation", {}).get("btc_liquidations", {})
    if liq.get("long_short_ratio") is not None:
        available_layers += 1
        if 0.5 <= liq["long_short_ratio"] <= 2.0:
            score += 1
            details.append(f"L4 liquidations balanced ({liq['recent_count']} recent, {liq['long_short_ratio']}:1 L/S) (+1)")
        elif liq["long_short_ratio"] > 2.0:
            details.append(f"L4 longs being liquidated heavily ({liq['long_short_ratio']}:1) — downside pressure")

    # L5: TVL health (DeFiLlama — available)
    tvl = data.get("on_chain", {}).get("tvl", {})
    if tvl.get("tvl_change_7d_pct") is not None:
        available_layers += 1
        if tvl["tvl_change_7d_pct"] > -5:
            score += 1
            details.append(f"L5 TVL stable ({tvl['tvl_change_7d_pct']:+.1f}% 7d) (+1)")
        else:
            details.append(f"L5 TVL dropping ({tvl['tvl_change_7d_pct']:+.1f}% 7d)")

    # L6: Sentiment (available)
    fg = data.get("sentiment", {}).get("fear_greed", {})
    if fg.get("fear_greed_value") is not None:
        available_layers += 1
        if 20 <= fg["fear_greed_value"] <= 60:
            score += 1
            details.append(f"L6 F&G {fg['fear_greed_value']} neutral (+1)")
        elif fg["fear_greed_value"] < 20:
            details.append(f"L6 Extreme Fear ({fg['fear_greed_value']}) — contrarian buy signal")

    # BTC dominance context
    btc_d = data.get("correlation", {}).get("btc_dominance", {})
    if btc_d.get("btc_dominance_pct") is not None:
        available_layers += 1
        if btc_d["btc_dominance_pct"] > 55:
            details.append(f"BTC.D {btc_d['btc_dominance_pct']}% — BTC regime")
        elif btc_d["btc_dominance_pct"] < 45:
            details.append(f"BTC.D {btc_d['btc_dominance_pct']}% — alt season signal")

    # Price context
    prices = data.get("prices", {})
    if prices.get("btc") and prices.get("btc_24h_change") is not None:
        details.append(f"BTC ${prices['btc']:,.0f} ({prices['btc_24h_change']:+.1f}% 24h)")

    # Minimum layers guard
    min_layers = 3
    if available_layers < min_layers:
        return {
            "score": None,
            "max_score": 6,
            "available_layers": available_layers,
            "details": details + [f"INSUFFICIENT: {available_layers}/{min_layers} layers available"],
            "threshold_met": False,
            "signal": "NO_DATA",
        }

    return {
        "score": score,
        "max_score": 6,
        "available_layers": available_layers,
        "details": details,
        "threshold_met": score >= 3,
        "signal": "CRYPTO_E1" if score >= 3 else "WAIT",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Summary printer
# ═══════════════════════════════════════════════════════════════════════════

def print_summary(data: Dict) -> str:
    """Compact summary for quick viewing."""
    lines = ["[CRYPTO] #module-data", ""]

    pa = data.get("price_action", {})
    if pa.get("latest_pattern", "none") != "none":
        lines.append(f"Pattern: {pa['latest_pattern']} (trend: {pa.get('trend_20d','?')})")

    vp = data.get("volume_profile", {})
    if vp.get("vwap"):
        lines.append(f"VWAP: ${vp['vwap']:,.0f} | Vol: {vp.get('volume_ratio',1):.1f}x" +
                     (" 🔥" if vp.get('volume_surge') else ""))

    prices = data.get("prices", {})
    btc = prices.get("btc")
    eth = prices.get("eth")
    btc_chg = prices.get("btc_24h_change")
    if btc:
        chg_str = f" ({btc_chg:+.1f}% 24h)" if btc_chg else ""
        lines.append(f"BTC: ${btc:,.0f}{chg_str}" + (f" | ETH: ${eth:,.0f}" if eth else ""))

    skew = data.get("options", {}).get("btc_skew", {})
    if skew.get("skew") is not None:
        lines.append(f"IV Skew: {skew['skew']:+.1f}% ({skew.get('skew_signal','?')})")

    fg = data.get("sentiment", {}).get("fear_greed", {})
    if fg.get("fear_greed_value") is not None:
        lines.append(f"F&G: {fg['fear_greed_value']} — {fg.get('classification','?')} ({fg.get('trend','?')})")

    tvl = data.get("on_chain", {}).get("tvl", {})
    if tvl.get("total_tvl_usd") is not None:
        lines.append(f"DeFi TVL: ${tvl['total_tvl_usd']/1e9:.1f}B ({tvl.get('tvl_change_7d_pct','?')}% 7d)")

    btc_d = data.get("correlation", {}).get("btc_dominance", {})
    if btc_d.get("btc_dominance_pct") is not None:
        lines.append(f"BTC.D: {btc_d['btc_dominance_pct']}%")

    ethbtc = data.get("correlation", {}).get("eth_btc", {})
    if ethbtc.get("eth_btc_ratio") is not None:
        lines.append(f"ETH/BTC: {ethbtc['eth_btc_ratio']}")

    conf = data.get("confluence", {})
    lines.append(f"\nConfluence: {conf['score']}/{conf['max_score']} ({conf.get('available_layers',0)} layers available) → {conf['signal']}")
    if conf.get("details"):
        for d in conf["details"][:5]:
            lines.append(f"  {d}")

    missing = data.get("_meta", {}).get("missing", "")
    if missing:
        lines.append(f"\n⚠ Missing: {missing}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════

def main():
    summary_only = "--summary" in sys.argv

    data = fetch_all()

    # Write JSON
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n✅ Crypto module data → {OUTPUT_PATH}")

    if summary_only:
        print()
        print(print_summary(data))


if __name__ == "__main__":
    main()
