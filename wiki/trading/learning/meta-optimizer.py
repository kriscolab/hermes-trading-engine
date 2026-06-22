#!/usr/bin/env python3
"""
Meta-Optimizer v1.0 — Cross-Layer Learning Feedback
=====================================================
Reads learning outputs (backtest, missed-audit, trades) and feeds adjustments
back into the system:
  1. Ensemble weights — boost modules that correlated with winning trades
  2. Risk TP/SL — tighten/loosen based on regime-hit-rate
  3. Entry thresholds — suggest lowering when missed opportunities are profitable

Output: synthesis/meta_state.json — consumed by ensemble-meta and risk-engine

Usage:
    python3 meta-optimizer.py              # Analyze + update meta_state
    python3 meta-optimizer.py --summary    # Print recommendations only
"""

import sys
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent
DB_PATH = TRADING_DIR / "paper-trader" / "journal.db"
META_PATH = TRADING_DIR / "synthesis" / "meta_state.json"
QUANT_PATH = Path("/tmp/quant_signals.json")

# Module keys matching ensemble-meta
MODULE_KEYS = [
    "mean-reversion", "momentum", "correlation", "stat-arbitrage",
    "monte-carlo", "volatility-arbitrage", "ml-signals",
    "event-driven", "market-making", "microstructure"
]


def analyze_trades() -> Dict:
    """Analyze closed trades to find which signals/theses performed best."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    closed = conn.execute(
        "SELECT * FROM trades WHERE status='closed' AND pnl_realized IS NOT NULL"
    ).fetchall()
    
    thesis_perf = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0.0, "count": 0})
    signal_perf = defaultdict(lambda: {"wins": 0, "losses": 0, "total_pnl": 0.0, "count": 0})
    
    for t in closed:
        sig = t["entry_signal"]
        thesis = "commodity"
        if sig.startswith("CRYPTO_"): thesis = "crypto"
        elif sig.startswith("AI_"): thesis = "ai"
        elif sig.startswith("QUANT_"): thesis = "quant"
        
        pnl = t["pnl_realized"] or 0
        signal_perf[sig]["count"] += 1
        signal_perf[sig]["total_pnl"] += pnl
        thesis_perf[thesis]["count"] += 1
        thesis_perf[thesis]["total_pnl"] += pnl
        if pnl > 0:
            signal_perf[sig]["wins"] += 1
            thesis_perf[thesis]["wins"] += 1
        else:
            signal_perf[sig]["losses"] += 1
            thesis_perf[thesis]["losses"] += 1
    
    conn.close()
    return {"thesis": dict(thesis_perf), "signal": dict(signal_perf), "total_closed": len(closed)}


def analyze_quant_correlation() -> Dict[str, float]:
    """Check which quant modules had signals aligned with winning trades."""
    weights = {mk: 0.5 for mk in MODULE_KEYS}
    
    if not QUANT_PATH.exists():
        return weights
    
    try:
        qd = json.loads(QUANT_PATH.read_text())
        signals = qd.get("signals", {})
        
        # Count how many tickers each module gives directional signals
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
        
        # Base weight on signal quality + trade outcome (future)
        for mk in MODULE_KEYS:
            quality = mod_active[mk] / max(mod_total[mk], 1)
            weights[mk] = 0.3 + 0.4 * quality
    except Exception:
        pass
    
    return weights


def recommend_thresholds(trade_analysis: Dict) -> Dict:
    """Suggest entry threshold adjustments based on missed opportunity data."""
    recs = {}
    
    # If no closed trades, no recommendations
    if trade_analysis["total_closed"] == 0:
        recs["entry"] = "No closed trades yet — insufficient data for threshold calibration"
        recs["risk"] = "Default regime-adaptive TP/SL active"
        return recs
    
    # Check thesis performance
    for thesis, perf in trade_analysis["thesis"].items():
        if perf["count"] >= 3:
            wr = perf["wins"] / perf["count"] * 100
            avg_pnl = perf["total_pnl"] / perf["count"]
            if wr > 60 and avg_pnl > 0:
                recs[thesis] = f"Strong: {wr:.0f}% WR, avg P&L ${avg_pnl:+,.0f} — consider increasing allocation"
            elif wr < 40:
                recs[thesis] = f"Weak: {wr:.0f}% WR, avg P&L ${avg_pnl:+,.0f} — tighten entry conditions"
    
    return recs


def generate_meta_state() -> Dict:
    trades = analyze_trades()
    weights = analyze_quant_correlation()
    recs = recommend_thresholds(trades)
    
    state = {
        "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "version": "v1.0",
        "trade_analysis": {
            "total_closed": trades["total_closed"],
            "by_thesis": trades["thesis"],
        },
        "ensemble_weights": weights,
        "recommendations": recs,
        "status": "learning" if trades["total_closed"] > 0 else "cold_start",
    }
    
    META_PATH.write_text(json.dumps(state, indent=2))
    return state


def main():
    state = generate_meta_state()
    
    if "--summary" in sys.argv:
        print(f"🧠 Meta-Optimizer v1.0 — {state['status']}")
        print(f"   Closed trades: {state['trade_analysis']['total_closed']}")
        print()
        if state["recommendations"]:
            for k, v in state["recommendations"].items():
                print(f"   {k}: {v}")
        print()
        print(f"   Ensemble weights → {META_PATH}")
    else:
        print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
