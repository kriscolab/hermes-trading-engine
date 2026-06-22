#!/usr/bin/env python3
"""
Risk Engine v1.1 — Position-Level Risk Management with Auto-Execute
====================================================================
Reads open positions + live prices → computes risk metrics per position.
Implements rules.md philosophy:
  - Take profit in thirds (50% at T1, 30% at T2, 20% runner)
  - No hard stops for long-duration theses (commodity, AI)
  - Crypto thesis: hard stops at -15% drawdown
  - Short positions: 80/20 rule at target

Output: /tmp/risk_alerts.json — consumed by dashboard + polling daemon
        --execute flag auto-closes positions when TP/SL thresholds breached.

Usage:
    python3 risk-engine.py              # Compute + print alerts
    python3 risk-engine.py --execute    # Auto-close breached positions
    python3 risk-engine.py --json       # JSON output only
"""

import sys
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent
DB_PATH = TRADING_DIR / "paper-trader" / "journal.db"
PRICES_PATH = Path("/tmp/portfolio_prices.json")
CRYPTO_PATH = Path("/tmp/crypto_module_data.json")
ALERT_PATH = Path("/tmp/risk_alerts.json")

# ── Risk Parameters (base defaults — overridden by regime) ──
TP_T1 = 0.10    # T1 at +10% — exit 50%
TP_T2 = 0.20    # T2 at +20% — exit 30% of original (60% of remaining)
EXIT_T1_PCT = 50  # Close 50% at T1
EXIT_T2_PCT = 60  # Close 60% of remaining at T2
SHORT_TP = 0.10   # Cover shorts at 10% gain
SHORT_COVER = 80  # Cover 80% at target (80/20 rule)
CRITICAL_DD = -0.15  # Hard stop at -15%

# ── Regime-Adaptive Overrides ──
# Read synthesizer's daily_state.json for current regime
SYNTH_PATH = Path("/home/hermes-pilot/vault/wiki/trading/synthesis/daily_state.json")

REGIME_PARAMS = {
    "RISK_ON":    {"tp1": 0.15, "tp2": 0.25, "sl": -0.18},  # let winners run
    "TRENDING":   {"tp1": 0.10, "tp2": 0.20, "sl": -0.15},  # momentum carries
    "NEUTRAL":    {"tp1": 0.08, "tp2": 0.15, "sl": -0.12},  # standard
    "CAUTIOUS":   {"tp1": 0.05, "tp2": 0.10, "sl": -0.08},  # tight, defensive
    "RISK_OFF":   {"tp1": 0.03, "tp2": 0.06, "sl": -0.05},  # capital preservation
}

def get_regime_params():
    """Read current regime from synthesizer and return adapted TP/SL params."""
    try:
        if SYNTH_PATH.exists():
            synth = json.loads(SYNTH_PATH.read_text())
            regime = synth.get("market_regime", {}).get("primary", "NEUTRAL")
            return REGIME_PARAMS.get(regime, REGIME_PARAMS["NEUTRAL"]), regime
    except Exception: pass
    return REGIME_PARAMS["NEUTRAL"], "NEUTRAL"

# Long-duration theses: no hard stops
NO_STOP_THESES = {"commodity", "ai"}


def get_db():
    """Get a JournalDB-like connection for position operations."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_positions() -> List[Dict]:
    conn = get_db()
    positions = [dict(r) for r in conn.execute(
        "SELECT * FROM trades WHERE status='open'"
    ).fetchall()]
    conn.close()
    return positions


def load_prices() -> Dict[str, float]:
    prices = {}
    if PRICES_PATH.exists():
        try: prices = json.loads(PRICES_PATH.read_text())
        except Exception: pass
    if CRYPTO_PATH.exists():
        try:
            crypto = json.loads(CRYPTO_PATH.read_text())
            sbtc = crypto.get("prices", {}).get("btc", 0)
            seth = crypto.get("prices", {}).get("eth", 0)
            if sbtc: prices["IBIT"] = sbtc
            if seth: prices["ETHA"] = seth
        except Exception: pass
    return prices


def get_thesis(signal_id: str) -> str:
    if signal_id.startswith("CRYPTO_"): return "crypto"
    if signal_id.startswith("AI_"): return "ai"
    return "commodity"


def close_position(conn, trade_id: int, exit_price: float, 
                   exit_signal: str, notes: str = ""):
    """Close a position fully, computing P&L."""
    trade = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if not trade:
        return
    direction = trade["direction"]
    entry = trade["entry_price"]
    shares = trade["shares"]
    pnl = (exit_price - entry) * shares if direction == "long" else (entry - exit_price) * shares
    
    conn.execute(
        """UPDATE trades SET exit_date = ?, exit_price = ?, exit_signal = ?,
           pnl_realized = ?, status = 'closed', notes = notes || ?
           WHERE id = ?""",
        (datetime.now(IST).strftime("%Y-%m-%d"), exit_price, exit_signal,
         round(pnl, 2), f"\n{notes}" if notes else "", trade_id))
    conn.commit()
    return round(pnl, 2)


def reduce_position(conn, trade_id: int, exit_price: float, exit_pct: float,
                    exit_signal: str, notes: str = "") -> Optional[int]:
    """Reduce position by exit_pct%. Returns new trade_id for remaining portion."""
    trade = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if not trade:
        return None
    
    direction = trade["direction"]
    entry = trade["entry_price"]
    shares = trade["shares"]
    
    exit_shares = shares * (exit_pct / 100.0)
    remain = shares - exit_shares
    
    pnl = (exit_price - entry) * exit_shares if direction == "long" else (entry - exit_price) * exit_shares
    
    if remain <= 0.001:
        # Full close
        close_position(conn, trade_id, exit_price, exit_signal, notes)
        return None
    
    # Close original
    conn.execute(
        """UPDATE trades SET exit_date = ?, exit_price = ?, exit_signal = ?,
           pnl_realized = ?, status = 'closed', notes = notes || ?
           WHERE id = ?""",
        (datetime.now(IST).strftime("%Y-%m-%d"), exit_price, exit_signal,
         round(pnl, 2), f"\n{notes}", trade_id))
    
    # Open runner
    cursor = conn.execute(
        """INSERT INTO trades (trade_date, symbol, direction, entry_price,
           shares, entry_signal, status, notes, thesis_id)
           VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
        (datetime.now(IST).strftime("%Y-%m-%d"), trade["symbol"], direction,
         entry, round(remain, 4), trade["entry_signal"],
         f"Runner from {exit_signal} — {remain:.4f} shares @ ${entry:,.2f}",
         trade["thesis_id"]))
    conn.commit()
    return cursor.lastrowid


def compute_risk(pos: Dict, live_price: float, rp: dict) -> Dict:
    sym = pos["symbol"]
    direction = pos["direction"]
    entry = float(pos["entry_price"])
    shares = float(pos["shares"])
    signal = pos["entry_signal"]
    thesis = get_thesis(signal)
    
    tp1_pct = rp["tp1"]
    tp2_pct = rp["tp2"]
    sl_pct = rp["sl"]
    
    if direction == "short":
        pnl_pct = (entry - live_price) / entry
        pnl_abs = (entry - live_price) * shares
        tp_t1 = entry * (1 - tp1_pct)
        tp_t2 = entry * (1 - tp2_pct)
    else:
        pnl_pct = (live_price - entry) / entry
        pnl_abs = (live_price - entry) * shares
        tp_t1 = entry * (1 + tp1_pct)
        tp_t2 = entry * (1 + tp2_pct)
    
    has_stop = thesis not in NO_STOP_THESES
    
    risk = {
        "trade_id": pos["id"],
        "symbol": sym, "direction": direction, "thesis": thesis, "signal": signal,
        "entry_price": entry, "live_price": live_price, "shares": shares,
        "cost_basis": round(entry * shares, 2),
        "mkt_value": round(live_price * shares, 2),
        "pnl_abs": round(pnl_abs, 2), "pnl_pct": round(pnl_pct * 100, 2),
        "tp_t1": round(tp_t1, 2), "tp_t2": round(tp_t2, 2),
        "has_hard_stop": has_stop,
        "distance_to_t1_pct": round((tp_t1 - live_price) / live_price * 100, 2),
        "distance_to_t2_pct": round((tp_t2 - live_price) / live_price * 100, 2),
        "regime": rp.get("_regime", "NEUTRAL"),
    }
    
    if pnl_pct >= tp2_pct:
        risk["status"] = "TP2_HIT"
        risk["action"] = f"Exit {EXIT_T2_PCT}% of remaining — T2 at {pnl_pct*100:.1f}% gain"
    elif pnl_pct >= tp1_pct:
        risk["status"] = "TP1_HIT"
        risk["action"] = f"Exit {EXIT_T1_PCT}% — T1 at {pnl_pct*100:.1f}% gain"
    elif pnl_pct <= sl_pct and has_stop:
        risk["status"] = "CRITICAL"
        risk["action"] = f"HARD STOP: {pnl_pct*100:.1f}% drawdown — exit all"
    elif pnl_pct <= sl_pct * 0.5:
        risk["status"] = "WARN"
        risk["action"] = f"Warning: {pnl_pct*100:.1f}% drawdown"
    elif pnl_pct > 0:
        risk["status"] = "PROFIT"
        risk["action"] = f"In profit: {pnl_pct*100:.1f}% — {round((tp_t1-live_price)/live_price*100,1):.1f}% to T1"
    else:
        risk["status"] = "OK"
        risk["action"] = "Within risk parameters"
    
    return risk


def generate_alerts() -> Dict:
    positions = load_positions()
    prices = load_prices()
    rp, regime = get_regime_params()
    rp["_regime"] = regime  # tag for display
    
    alerts = []
    summary = {
        "total_positions": len(positions),
        "tp1_hit": 0, "tp2_hit": 0, "warnings": 0, "critical": 0,
        "total_pnl": 0.0,
        "regime": regime,
        "tp1_pct": rp["tp1"]*100, "tp2_pct": rp["tp2"]*100, "sl_pct": rp["sl"]*100,
        "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
    }
    
    for pos in positions:
        sym = pos["symbol"]
        live = prices.get(sym, pos["entry_price"])
        risk = compute_risk(pos, live, rp)
        alerts.append(risk)
        
        summary["total_pnl"] += risk["pnl_abs"]
        if risk["status"] == "TP2_HIT": summary["tp2_hit"] += 1
        elif risk["status"] == "TP1_HIT": summary["tp1_hit"] += 1
        elif risk["status"] == "WARN": summary["warnings"] += 1
        elif risk["status"] == "CRITICAL": summary["critical"] += 1
    
    result = {"summary": summary, "alerts": alerts}
    ALERT_PATH.write_text(json.dumps(result, indent=2))
    return result


def execute_risk_actions(alerts: Dict):
    """Auto-close positions that breached TP/SL thresholds."""
    conn = get_db()
    executed = []
    
    for a in alerts["alerts"]:
        status = a["status"]
        trade_id = a["trade_id"]
        live = a["live_price"]
        sym = a["symbol"]
        
        if status == "TP1_HIT":
            # Exit 50% at T1
            new_id = reduce_position(conn, trade_id, live, EXIT_T1_PCT, 
                                     "RISK_TP1", f"T1 hit: {a['pnl_pct']:.1f}% gain on {sym}")
            print(f"  🎯 {sym}: TP1 — exited {EXIT_T1_PCT}% (new runner #{new_id})" if new_id else
                  f"  🎯 {sym}: TP1 — fully closed")
            executed.append(f"{sym}:RISK_TP1")
            
        elif status == "TP2_HIT":
            # Exit 60% of remaining at T2
            new_id = reduce_position(conn, trade_id, live, EXIT_T2_PCT,
                                     "RISK_TP2", f"T2 hit: {a['pnl_pct']:.1f}% gain on {sym}")
            print(f"  🎯 {sym}: TP2 — exited {EXIT_T2_PCT}% of remaining (new runner #{new_id})" if new_id else
                  f"  🎯 {sym}: TP2 — fully closed")
            executed.append(f"{sym}:RISK_TP2")
            
        elif status == "CRITICAL":
            # Hard stop — close 100%
            pnl = close_position(conn, trade_id, live, "RISK_SL",
                                 f"STOP LOSS: {a['pnl_pct']:.1f}% drawdown on {sym}")
            pnl_str = f"${pnl:+,.0f}" if pnl else "?"
            print(f"  🚨 {sym}: HARD STOP — fully closed, P&L {pnl_str}")
            executed.append(f"{sym}:RISK_SL")
    
    conn.close()
    
    if executed:
        # Re-generate alerts after execution
        generate_alerts()
    
    return executed


def main():
    alerts = generate_alerts()
    summary = alerts["summary"]
    
    if "--json" in sys.argv:
        print(json.dumps(alerts, indent=2))
        return
    
    print(f"🛡️ Risk Engine v1.2 — Regime: {summary.get('regime','?')}")
    print(f"   TP: T1={summary.get('tp1_pct',10):.0f}% / T2={summary.get('tp2_pct',20):.0f}% | SL: {summary.get('sl_pct',-15):.0f}%")
    print(f"   {summary['total_positions']} positions | Total UPNL: ${summary['total_pnl']:+,.0f}")
    print()
    
    status_icons = {
        "TP2_HIT": "🎯", "TP1_HIT": "📈", "WARN": "⚠️",
        "CRITICAL": "🚨", "PROFIT": "🟢", "OK": "⚪"
    }
    
    for a in alerts["alerts"]:
        icon = status_icons.get(a["status"], "?")
        print(f"   {icon} {a['symbol']:6s} {a['direction']:5s} | "
              f"PnL: {a['pnl_pct']:+.1f}% (${a['pnl_abs']:+,.0f}) | "
              f"T1: ${a['tp_t1']:,.2f} ({a['distance_to_t1_pct']:+.1f}% away) | "
              f"T2: ${a['tp_t2']:,.2f} | "
              f"{'[NO STOP]' if not a['has_hard_stop'] else '[HARD STOP]'} | "
              f"{a['action']}")
    
    if summary["tp2_hit"] or summary["tp1_hit"]:
        print(f"\n🎯 TAKE PROFIT: {summary['tp1_hit']} T1, {summary['tp2_hit']} T2")
    if summary["critical"]:
        print(f"\n🚨 CRITICAL: {summary['critical']} positions at hard stop")
    if summary["warnings"]:
        print(f"\n⚠️  WARNINGS: {summary['warnings']} positions approaching risk limits")
    
    if "--execute" in sys.argv:
        executable = [t for t in ["TP1_HIT", "TP2_HIT", "CRITICAL"] 
                      if any(a["status"] == t for a in alerts["alerts"])]
        if executable:
            print(f"\n🔧 AUTO-EXECUTING: {', '.join(executable)}")
            executed = execute_risk_actions(alerts)
            print(f"\n✅ Executed {len(executed)} risk actions")
        else:
            print("\n✅ No positions breached thresholds — no actions needed")


if __name__ == "__main__":
    main()
