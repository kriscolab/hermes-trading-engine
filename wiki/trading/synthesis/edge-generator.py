#!/usr/bin/env python3
"""
Hermes Unified Edge Generator (v1.0)
=====================================
Combines quant module edges + thesis signal states + market regime
+ portfolio context → unified trade recommendations.

Inputs:
  /tmp/quant_signals.json       — 9 quant module edge scores per ticker
  journal.db                    — thesis signal states + open positions
  /tmp/crypto_module_data.json  — crypto confluence + prices
  /tmp/live_market_data.json    — commodity market data
  /tmp/portfolio_prices.json    — current mark-to-market prices
  synthesis/daily_state.json    — synthesizer regime + risk + thesis bias

Output:
  /tmp/edge_generator.json      — unified recommendations per ticker

Usage:
  python3 edge-generator.py           # Full run, writes JSON
  python3 edge-generator.py --json    # Print JSON to stdout
  python3 edge-generator.py --summary # Human-readable summary
"""

import sqlite3
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Paths ────────────────────────────────────────────────────────────

TRADING_DIR = Path(__file__).resolve().parent.parent
DB_PATH = TRADING_DIR / "paper-trader" / "journal.db"
QUANT_PATH = Path("/tmp/quant_signals.json")
CRYPTO_PATH = Path("/tmp/crypto_module_data.json")
MARKET_PATH = Path("/tmp/live_market_data.json")
PRICES_PATH = Path("/tmp/portfolio_prices.json")
SYNTH_PATH = Path(__file__).resolve().parent / "daily_state.json"
OUTPUT_PATH = Path("/tmp/edge_generator.json")

# ── Shared config ──
try:
    from delivery.trading_config import REGIME_THRESHOLDS, CRYPTO_TICKERS
except ImportError:
    REGIME_THRESHOLDS = {"NEUTRAL": {"t1": 0.08, "t2": 0.15, "sl": -0.12}}
    CRYPTO_TICKERS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ADA", "XRP", "DOGE"]

# Thesis signal → thesis mapping
SIGNAL_THESIS = {
    "E1": "commodity", "E2": "commodity", "E3": "commodity", "E4S": "commodity", "E4L": "commodity",
    "X1": "commodity", "X2": "commodity", "X3": "commodity", "X4": "commodity", "X5": "commodity",
    "CRYPTO_E1": "crypto", "CRYPTO_E2": "crypto", "CRYPTO_E3": "crypto", "CRYPTO_E4": "crypto",
    "CRYPTO_X1": "crypto", "CRYPTO_X2": "crypto", "CRYPTO_X3": "crypto", "CRYPTO_X4": "crypto", "CRYPTO_X5": "crypto",
    "AI_E1": "ai", "AI_E2": "ai", "AI_E3": "ai", "AI_E4": "ai", "AI_E5": "ai",
    "AI_X1": "ai", "AI_X2": "ai", "AI_X3": "ai", "AI_X4": "ai", "AI_X5": "ai",
    "INTRADAY_LONG": "intraday", "INTRADAY_SHORT": "intraday",
    "INTRADAY_X1": "intraday", "INTRADAY_X2": "intraday", "INTRADAY_X3": "intraday",
    "QUANT_E1": "quant", "QUANT_E2": "quant",
    "QUANT_X1": "quant", "QUANT_X2": "quant",
}

# Quant module short names
QUANT_NAMES = {
    "mean-reversion": "Mean Reversion", "momentum": "Momentum",
    "correlation": "Correlation", "stat_arbitrage": "Stat Arb",
    "volatility-arbitrage": "Vol Arb", "ml-signals": "ML Regime",
    "event-driven": "Event Driven", "market-making": "Market Making",
    "microstructure": "Microstructure",
}

# ── Data Loading ─────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if path.exists():
        try: return json.loads(path.read_text())
        except Exception: pass
    return {}

def load_journal() -> List:
    """Return open_positions from journal.db."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    positions = [dict(r) for r in conn.execute(
        "SELECT * FROM trades WHERE status='open'").fetchall()]
    conn.close()
    return positions


# ── Edge Scoring ─────────────────────────────────────────────────────

def score_ticker(ticker: str, quant_signals: dict, thesis_bias: dict,
                 positions: List, crypto_data: dict, market_data: dict) -> dict:
    
    # 1. QUANT EDGE — aggregate all quant module scores
    quant_edges = {}
    max_quant_edge = 0
    quant_signals_list = []
    qs = quant_signals.get(ticker, {})
    for mod_name, mod_data in qs.items():
        edge = mod_data.get("edge", mod_data.get("edge_score", mod_data.get("corr_30d", 0)))
        if isinstance(edge, (int, float)) and edge != 0:
            direction = mod_data.get("direction", mod_data.get("signal", "NEUTRAL"))
            quant_edges[mod_name] = {"edge": edge, "direction": direction}
            max_quant_edge = max(max_quant_edge, abs(edge))
            if edge >= 40:
                quant_signals_list.append(f"{QUANT_NAMES.get(mod_name, mod_name)}={edge:.0f}/{direction}")
    
    # 2. THESIS CONFLUENCE — which thesis signals are firing for this ticker
    thesis_signals = []
    thesis_score = 0
    
    # Map ticker to thesis — full universe
    ticker_thesis_map = {
        "BTC": "crypto", "ETH": "crypto", "SOL": "crypto", "LINK": "crypto",
        "AVAX": "crypto", "ADA": "crypto", "XRP": "crypto", "DOGE": "crypto",
        "GLD": "commodity", "XLE": "commodity",
        "SOXX": "ai", "IGV": "ai", "DTCR": "ai", "TAN": "ai", "XLC": "ai",
        "IBIT": "crypto", "ETHA": "crypto",
    }
    thesis = ticker_thesis_map.get(ticker, "unknown")
    
    # 2. THESIS BIAS — from synthesizer (single source of truth)
    BIAS_TO_SCORE = {
        "BULLISH": 15, "SLIGHTLY_BULLISH": 5, "NEUTRAL": 0,
        "SLIGHTLY_BEARISH": 5, "BEARISH": 15,
    }
    bias = thesis_bias.get(thesis, "NEUTRAL")
    thesis_score = BIAS_TO_SCORE.get(bias, 0)
    thesis_signals = [f"synthesizer: {bias}"] if bias != "NEUTRAL" else []
    
    # 3. POSITION CONTEXT — do we already have a position?
    has_position = False
    position_info = None
    for p in positions:
        if p["symbol"] == ticker:
            has_position = True
            position_info = {
                "direction": p["direction"],
                "entry_price": p["entry_price"],
                "shares": p["shares"],
                "entry_signal": p["entry_signal"],
                "trade_date": p.get("trade_date", "?"),
            }
            break
    
    # 4. CRYPTO CONFLUENCE — for all crypto-universe tickers
    crypto_conc = 0
    if ticker in CRYPTO_TICKERS or ticker in ("IBIT", "ETHA"):
        base = ticker.upper()
        if base in ("IBIT", "ETHA"):
            base = "BTC" if base == "IBIT" else "ETH"
        tickers = crypto_data.get("tickers", {})
        td = tickers.get(base.lower(), {})
        crypto_conc = td.get("confluence", {}).get("score", 0)
    
    # 5. UNIFIED SCORE (weighted)
    # Quant: 40%, Thesis: 35%, Crypto confluence: 25%
    quant_component = min(100, max_quant_edge) * 0.40
    thesis_component = min(100, thesis_score) * 0.35
    crypto_component = (crypto_conc / 6 * 100) * 0.25
    
    unified_score = quant_component + thesis_component + crypto_component
    unified_score = min(100, max(0, unified_score))
    
    # 6. DETERMINE DIRECTION
    # Consensus across quant modules
    directions = [v["direction"] for v in quant_edges.values()]
    buy_votes = sum(1 for d in directions if "BUY" in d or "BULL" in d or "LONG" in d)
    sell_votes = sum(1 for d in directions if "SELL" in d or "BEAR" in d or "SHORT" in d)
    
    if has_position:
        if position_info["direction"] == "short":
            recommendation = "HOLD_SHORT"
        else:
            recommendation = "HOLD_LONG"
    elif unified_score >= 50:
        if buy_votes > sell_votes:
            recommendation = "BUY"
        elif sell_votes > buy_votes:
            recommendation = "SELL"
        else:
            recommendation = "WATCH"
    elif unified_score >= 40:
        recommendation = "WATCH"
    else:
        recommendation = "WAIT"
    
    return {
        "ticker": ticker,
        "unified_score": round(unified_score, 1),
        "recommendation": recommendation,
        "quant_edge_max": max_quant_edge,
        "quant_signals": quant_signals_list,
        "thesis": thesis,
        "thesis_signals": thesis_signals,
        "crypto_confluence": crypto_conc,
        "has_position": has_position,
        "position": position_info,
        "components": {
            "quant_pct": round(quant_component, 1),
            "thesis_pct": round(thesis_component, 1),
            "crypto_pct": round(crypto_component, 1),
        }
    }


def generate() -> dict:
    """Main generation function."""
    now = datetime.now(timezone.utc)
    ist = now.strftime("%Y-%m-%d %H:%M IST")
    
    # Load data
    quant_data = load_json(QUANT_PATH)
    crypto_data = load_json(CRYPTO_PATH)
    market_data = load_json(MARKET_PATH)
    synth_data = load_json(SYNTH_PATH)
    positions = load_journal()
    
    # Extract thesis bias from synthesizer (single source of truth)
    thesis_bias = {}
    for th, rec in synth_data.get("thesis_recommendations", {}).items():
        thesis_bias[th] = rec.get("bias", "NEUTRAL")
    
    quant_signals = quant_data.get("signals", {})
    
    # Tickers to evaluate: all from quant + all with positions
    all_tickers = set(quant_signals.keys())
    for p in positions:
        sym = p["symbol"]
        if sym in ("IBIT", "ETHA", "FBTC"):
            all_tickers.add("BTC" if sym == "IBIT" else "ETH")
        else:
            all_tickers.add(sym)
    
    # Cross-thesis allocation
    deployed_total = sum(p["entry_price"] * p["shares"] for p in positions)
    remaining = 100_000 - deployed_total
    
    # Score each ticker
    recommendations = []
    for ticker in sorted(all_tickers):
        rec = score_ticker(ticker, quant_signals, thesis_bias, positions, crypto_data, market_data)
        recommendations.append(rec)
    
    # Portfolio summary
    portfolio = {
        "total_equity": 100_000,
        "deployed": round(deployed_total, 0),
        "remaining": round(remaining, 0),
        "allocation_pct": round(deployed_total / 1000, 1),
        "open_positions": len(positions),
        "positions_by_thesis": {},
    }
    for p in positions:
        thesis = SIGNAL_THESIS.get(p["entry_signal"], "other")
        portfolio["positions_by_thesis"][thesis] = portfolio["positions_by_thesis"].get(thesis, 0) + 1
    
    # Market regime — prefer synthesizer's analysis
    regime = synth_data.get("market_regime", {}).get("primary", "UNKNOWN")
    if regime == "UNKNOWN":
        # Fallback to simple VIX/DXY check
        if market_data:
            vix = market_data.get("vix", 20)
            regime = "RISK_OFF" if vix > 25 else ("RISK_ON" if vix < 15 else "NEUTRAL")
    
    # Risk factor from synthesizer
    risk = synth_data.get("primary_risk_factor", {})
    
    output = {
        "generated_at": ist,
        "generator_version": "v1.2",
        "market_regime": regime,
        "risk_factor": risk.get("factor", "N/A"),
        "risk_severity": risk.get("severity", "LOW"),
        "thesis_bias": thesis_bias,
        "portfolio": portfolio,
        "recommendations": recommendations,
        "top_picks": [r for r in recommendations if r["unified_score"] >= 50][:5],
        "top_picks_summary": "No ticker crosses 50 (BUY/SELL threshold). Best: " + 
            (f"{recommendations[0]['ticker']} ({recommendations[0]['unified_score']:.0f})" if recommendations else "N/A") +
            ". Need stronger quant edges or more thesis signals firing.",
        "data_sources": {
            "quant_signals": QUANT_PATH.exists(),
            "crypto_module": CRYPTO_PATH.exists(),
            "market_data": MARKET_PATH.exists(),
            "synthesizer": SYNTH_PATH.exists(),
        }
    }
    
    return output


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    output = generate()
    
    # Write output
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    
    if "--json" in sys.argv:
        print(json.dumps(output, indent=2))
    elif "--summary" in sys.argv:
        print("=" * 60)
        print("Hermes Unified Edge Generator — v1.0")
        print(f"Generated: {output['generated_at']}")
        print(f"Regime: {output['market_regime']}")
        print(f"Portfolio: ${output['portfolio']['deployed']:,.0f} deployed ({output['portfolio']['allocation_pct']:.0f}%), "
              f"{output['portfolio']['open_positions']} positions")
        print(f"By thesis: {output['portfolio']['positions_by_thesis']}")
        print()
        print("Top Recommendations:")
        for r in output["recommendations"]:
            pos_mark = "📊" if r["has_position"] else "  "
            rec_icon = {"BUY": "🟢", "SELL": "🔴", "WATCH": "🟡", "WAIT": "⚫", "HOLD_LONG": "🔒", "HOLD_SHORT": "🔒"}.get(r["recommendation"], "?")
            print(f"  {pos_mark} {rec_icon} {r['ticker']:6s} score={r['unified_score']:5.1f} {r['recommendation']:10s} "
                  f"quant={r['quant_edge_max']:3d} thesis={r['thesis_signals']} conc={r['crypto_confluence']}")
        print(f"\n✅ Output → {OUTPUT_PATH}")
    else:
        print(f"✅ Edge generator → {OUTPUT_PATH} ({len(output['recommendations'])} tickers scored)")


if __name__ == "__main__":
    main()
