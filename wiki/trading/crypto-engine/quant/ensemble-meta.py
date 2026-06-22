#!/usr/bin/env python3
"""
Quant Module #10 — Ensemble Meta-Model  v1.0
==============================================
Reads all 9 quant module outputs from /tmp/quant_signals.json.
Learns module weights from journal.db trade outcomes.
Produces a weighted ensemble score per ticker — the "last mile" signal.

Design:
  - No external training — learns weights from live P&L data in journal.db
  - Fallback: equal weights when no trade history exists
  - Outputs summary + updates /tmp/quant_signals.json with "ensemble" key

Usage:
    python3 ensemble-meta.py              # Compute + print summary
    python3 ensemble-meta.py --json       # Output JSON to stdout
    python3 ensemble-meta.py --no-write   # Don't update quant_signals.json
"""

import sys
import json
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = TRADING_DIR / "paper-trader" / "journal.db"
QUANT_PATH = Path("/tmp/quant_signals.json")

# Module names as they appear in quant_signals.json signals dict keys
MODULE_KEYS = [
    "mean-reversion", "momentum", "correlation", "stat-arbitrage",
    "monte-carlo", "volatility-arbitrage", "ml-signals",
    "event-driven", "market-making", "microstructure",
    "orderflow", "tape-reading", "volume-profile",
]

# Map module key → human-readable name
MODULE_NAMES = {
    "mean-reversion": "Mean Reversion",
    "momentum": "Momentum",
    "correlation": "Correlation",
    "stat-arbitrage": "Stat Arb",
    "monte-carlo": "Monte Carlo",
    "volatility-arbitrage": "Vol Arb",
    "ml-signals": "ML Signals",
    "event-driven": "Event Driven",
    "market-making": "Market Making",
    "microstructure": "Microstructure",
    "orderflow": "Orderflow",
    "tape-reading": "Tape Reading",
    "volume-profile": "Volume Profile",
}


def normalize_score(val, module_name: str) -> float:
    """Normalize a module's output to a -1..+1 scale for ensemble blending."""
    if val is None:
        return 0.0
    
    if module_name == "monte-carlo":
        # MC now uses graduated confidence (0-100). Map: 50→0 (neutral), 0→-1, 100→+1
        return max(-1.0, min(1.0, (float(val) - 50) / 50))
    
    if module_name in ("momentum", "mean-reversion", "stat-arbitrage", "orderflow", "tape-reading", "volume-profile"):
        # These output edge_scores roughly -100..+100
        return max(-1.0, min(1.0, float(val) / 100.0))
    
    if module_name == "correlation":
        # Correlation score 0..1 (higher = stronger relationship)
        return float(val)
    
    if module_name in ("volatility-arbitrage", "event-driven"):
        # These output numeric edge scores (0-100 scale, 50=neutral) or string signals.
        # Fixed: was max(-1.0, min(1.0, float(val))) — capped at +1.0 for all val > 1,
        # making these ALWAYS bullish regardless of actual signal.
        if isinstance(val, str):
            return 1.0 if val == "LONG" else (-1.0 if val == "SHORT" else 0.0)
        return max(-1.0, min(1.0, (float(val) - 50) / 50))
    
    if module_name == "ml-signals":
        # ML edge is a confidence % (0-100), NOT a directional score.
        # Direction is encoded separately in the 'direction' field and flipped
        # by get_ticker_scores. Here we just extract magnitude: edge/100.
        if isinstance(val, str):
            return 0.0
        return float(val) / 100.0  # 53 → 0.53, 85 → 0.85
    
    if module_name in ("market-making", "microstructure"):
        # These output numeric edge scores (0-100 scale, 50=neutral).
        # Fixed: was max(-1.0, min(1.0, float(val))) — capped at +1.0 for all val > 1.
        if isinstance(val, str):
            return 0.0
        return max(-1.0, min(1.0, (float(val) - 50) / 50))
    
    return 0.0


def get_ticker_scores(quant_data: dict, ticker: str) -> Dict[str, float]:
    """Extract normalized scores for a ticker from all modules."""
    scores = {}
    
    # Main signals dict: signals.<ticker>.<module> → {edge, direction, ...}
    signals = quant_data.get("signals", {})
    ticker_data = signals.get(ticker, {})
    
    if not isinstance(ticker_data, dict):
        return scores
    
    for mod_key in MODULE_KEYS:
        mod_data = ticker_data.get(mod_key)
        if isinstance(mod_data, dict):
            edge = mod_data.get("edge", mod_data.get("corr_30d", 0))
            score = normalize_score(edge, mod_key)
            # Flip sign for bearish directions: SELL/SHORT/BEAR = negative contribution
            direction = str(mod_data.get("direction", mod_data.get("signal", ""))).upper()
            if any(d in direction for d in ("SELL", "SHORT", "BEAR")) and "BULL" not in direction:
                score = -abs(score)
            scores[mod_key] = score
    
    # Also check ml-signals at top level for per-ticker regime
    ml = quant_data.get("ml-signals", {})
    if isinstance(ml, dict):
        # ml-signals may have per-ticker entries
        pass  # already covered via ticker_data if included
    
    return scores


def learn_weights_from_trades() -> Dict[str, float]:
    """
    Learn module weights. Priority order:
    1. Closed trade P&L — module directional accuracy on realized trades
    2. Module signal quality — % of non-neutral signals (cold-start fallback)
    3. Equal weights (last resort)
    """
    weights = {k: 0.5 for k in MODULE_KEYS}
    
    # ── Priority 1: closed trade P&L → module accuracy ──
    pnl_weight = None
    closed = []
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            
            # Get closed quant trades
            closed = conn.execute(
                "SELECT * FROM trades WHERE status='closed' AND entry_signal LIKE 'QUANT_%'"
            ).fetchall()
            conn.close()
            
            if closed and len(closed) >= 1:
                # Read current quant signals to map module directions
                qd = json.loads(QUANT_PATH.read_text()) if QUANT_PATH.exists() else {}
                signals = qd.get("signals", {})
                
                # Per-module: count correct/incorrect directional signals
                mod_correct = {mk: 0.0 for mk in MODULE_KEYS}
                mod_total = {mk: 0.0 for mk in MODULE_KEYS}
                
                for trade in closed:
                    ticker = "BTC" if trade["symbol"] in ("IBIT",) else "ETH"
                    ts = signals.get(ticker, {})
                    trade_dir = trade["direction"]
                    trade_won = trade["pnl_realized"] > 0
                    
                    for mk in MODULE_KEYS:
                        md = ts.get(mk, {})
                        if not isinstance(md, dict):
                            continue
                        mod_dir = str(md.get("direction", "")).upper()
                        # Map module direction to trade direction
                        mod_is_long = any(d in mod_dir for d in ("BUY", "BULL", "LONG"))
                        mod_is_short = any(d in mod_dir for d in ("SELL", "BEAR", "SHORT"))
                        
                        if trade_dir == "long" and mod_is_long:
                            mod_total[mk] += 1
                            if trade_won:
                                mod_correct[mk] += 1
                        elif trade_dir == "short" and mod_is_short:
                            mod_total[mk] += 1
                            if trade_won:
                                mod_correct[mk] += 1
                        elif mod_dir not in ("NEUTRAL", "UNCORRELATED", ""):
                            # Module took a stance, trade went opposite way
                            mod_total[mk] += 0.5  # half-weight for wrong direction
                
                # Convert to accuracy scores
                accuracy = {}
                for mk in MODULE_KEYS:
                    if mod_total[mk] > 0:
                        accuracy[mk] = mod_correct[mk] / mod_total[mk]
                    else:
                        accuracy[mk] = 0.5  # neutral if no data
                
                # PnL weight = 0.3 + 0.4 * accuracy (range 0.3–0.7, same as signal quality)
                pnl_weight = {mk: 0.3 + 0.4 * accuracy[mk] for mk in MODULE_KEYS}
        except Exception:
            pass
    
    # ── Priority 2: signal quality from live quant output ──
    sq_weight = None
    if QUANT_PATH.exists():
        try:
            qd = json.loads(QUANT_PATH.read_text())
            signals = qd.get("signals", {})
            
            mod_active = {mk: 0 for mk in MODULE_KEYS}
            mod_total = {mk: 0 for mk in MODULE_KEYS}
            
            for ticker, mods in signals.items():
                for mk in MODULE_KEYS:
                    data = mods.get(mk, {})
                    if isinstance(data, dict):
                        mod_total[mk] += 1
                        direction = data.get("direction", data.get("signal", ""))
                        if direction and direction not in ("NEUTRAL", "UNCORRELATED"):
                            mod_active[mk] += 1
            
            sq_weight = {}
            for mk in MODULE_KEYS:
                quality = mod_active[mk] / max(mod_total[mk], 1)
                sq_weight[mk] = 0.3 + 0.4 * quality
        except Exception:
            pass
    
    # ── Blend ──
    closed_count = len(closed)
    if closed_count >= 3:
        blend_pnl = 0.6; blend_sq = 0.4
    elif closed_count >= 1:
        blend_pnl = 0.3; blend_sq = 0.7
    else:
        blend_pnl = 0.0; blend_sq = 1.0
    
    for mk in MODULE_KEYS:
        p = pnl_weight.get(mk, 0.5) if pnl_weight else 0.5
        q = sq_weight.get(mk, 0.5) if sq_weight else 0.5
        weights[mk] = round(blend_pnl * p + blend_sq * q, 3)
    
    return weights


def compute_ensemble(quant_data: dict, weights: dict) -> dict:
    """
    Compute weighted ensemble score for all tickers.
    Returns dict with per-ticker scores and metadata.
    """
    # Collect all tickers from the signals dict
    all_tickers = set(quant_data.get("signals", {}).keys())
    
    # Also check ml-signals at top level for additional tickers
    ml = quant_data.get("ml-signals", {})
    if isinstance(ml, dict):
        for k, v in ml.items():
            if isinstance(v, dict) and "regime_score" in v:
                all_tickers.add(k)
    
    results = {}
    for ticker in sorted(all_tickers):
        scores = get_ticker_scores(quant_data, ticker)
        if not scores:
            continue
        
        # Weighted average
        total_weight = sum(weights.get(mk, 0.5) for mk in scores)
        if total_weight == 0:
            ensemble_score = 0.0
        else:
            ensemble_score = sum(
                scores[mk] * weights.get(mk, 0.5) for mk in scores
            ) / total_weight
        
        # ── MC Gatekeeper haircut/boost ──
        mc_score = scores.get("monte-carlo", 0)
        if mc_score < 0:
            ensemble_score *= 0.5   # MC failed → 50% haircut
        elif mc_score > 0.5:
            ensemble_score *= 1.1   # MC passed → 10% boost
            ensemble_score = min(ensemble_score, 1.0)  # cap at 1.0
        
        # Direction: module majority voting (not weighted score threshold)
        # Each module with |score| > 0.15 gets one vote. Direction follows the majority.
        # Higher threshold (0.15 vs 0.1) filters out noise — many modules output
        # marginally positive scores that aren't genuine directional signals.
        long_signals = sum(1 for mk, v in scores.items() if v > 0.15)
        short_signals = sum(1 for mk, v in scores.items() if v < -0.15)
        
        # ── Majority voting ──
        # ML-signals gets 3x vote weight — it's the only module trained for explicit direction
        ml_score = abs(scores.get("ml-signals", 0))
        ml_dir = "BULLISH" if scores.get("ml-signals", 0) > 0.15 else ("BEARISH" if scores.get("ml-signals", 0) < -0.15 else "NEUTRAL")
        effective_long = long_signals + (2 if ml_dir == "BULLISH" else 0)
        effective_short = short_signals + (2 if ml_dir == "BEARISH" else 0)
        
        # MC gatekeeper applies a haircut for MC < 0 (already applied above),
        # but does NOT force direction to NEUTRAL — direction follows module majority.
        # This prevents blocking valid BEARISH signals when MC is marginally negative.
        # Direction: majority with 2-vote margin required (prevents marginal coin-flips)
        if effective_short > effective_long + 1 and short_signals >= 2:
            direction = "BEARISH"
        elif effective_long > effective_short + 1 and long_signals >= 2:
            direction = "BULLISH"
        elif ensemble_score > 0.35:
            direction = "BULLISH"
        elif ensemble_score < -0.35:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"
        
        confidence = abs(ensemble_score)  # 0..1
        
        results[ticker] = {
            "ensemble_score": round(ensemble_score, 3),
            "direction": direction,
            "confidence": round(confidence, 3),
            "module_count": len(scores),
            "long_modules": long_signals,
            "short_modules": short_signals,
            "module_scores": {mk: round(v, 3) for mk, v in scores.items()},
        }
    
    return results


def main():
    weights = learn_weights_from_trades()
    
    if not QUANT_PATH.exists():
        print("⚠ /tmp/quant_signals.json not found. Run quant-aggregator.py first.")
        sys.exit(1)
    
    quant_data = json.loads(QUANT_PATH.read_text())
    ensemble = compute_ensemble(quant_data, weights)
    
    # Write back to quant_signals.json
    if "--no-write" not in sys.argv:
        quant_data["ensemble"] = {
            "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
            "module_weights": {MODULE_NAMES.get(k, k): round(w, 2) for k, w in weights.items()},
            "signals": ensemble,
        }
        QUANT_PATH.write_text(json.dumps(quant_data, indent=2))
    
    # Output
    if "--json" in sys.argv:
        print(json.dumps(ensemble, indent=2))
    else:
        print(f"🧠 Ensemble Meta-Model v1.0")
        print(f"   Modules: {len(MODULE_KEYS)} | Tickers scored: {len(ensemble)}")
        print()
        for ticker, meta in sorted(ensemble.items(),
                                    key=lambda x: abs(x[1]["ensemble_score"]),
                                    reverse=True):
            icon = "🟢" if meta["direction"] == "BULLISH" else ("🔴" if meta["direction"] == "BEARISH" else "⚪")
            print(f"   {icon} {ticker:8s}  "
                  f"score={meta['ensemble_score']:+.3f}  "
                  f"{meta['direction']:7s}  "
                  f"conf={meta['confidence']:.2f}  "
                  f"↑{meta['long_modules']} ↓{meta['short_modules']}")
        
        # Weight table
        print()
        print("   Module Weights (learned from trades):")
        for mk in MODULE_KEYS:
            name = MODULE_NAMES.get(mk, mk)
            bar = "█" * int(weights.get(mk, 0.5) * 20)
            print(f"     {name:20s} {weights.get(mk, 0.5):.2f} {bar}")


if __name__ == "__main__":
    main()
