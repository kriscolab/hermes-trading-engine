#!/usr/bin/env python3
"""
Quant Engine — $25K Ensemble-Driven (Hyperliquid)
===================================================
Standalone paper trading engine. Reads 10-module ensemble from quant-aggregator.
MC-gated entries, ensemble-score exits. Edge-generator confirmation gate.

Usage:
  python3 engines/quant_engine.py          # Check only (full output)
  python3 engines/quant_engine.py --execute # Cron mode (silent unless trade)
  python3 engines/quant_engine.py --summary # Portfolio summary
"""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, List
from base import BaseEngine, Signal, SignalType

ENSEMBLE_PATH = Path("/tmp/quant_signals.json")
EDGE_PATH = Path("/tmp/edge_generator.json")


class QuantEngine(BaseEngine):
    name = "quant"
    initial_cash = 25_000.0

    @property
    def entry_signals(self) -> Dict:
        return {
            "QUANT_E1": Signal("QUANT_E1", "Ensemble Bullish", SignalType.ENTRY,
                "Ensemble > 0.25 BULLISH + MC passed", "Long best ticker at 10%", 10, 1),
            "QUANT_E2": Signal("QUANT_E2", "Ensemble Bearish", SignalType.ENTRY,
                "Ensemble > 0.25 BEARISH + MC passed", "Short best ticker at 10%", 10, 1),
        }

    @property
    def exit_signals(self) -> Dict:
        return {
            "QUANT_X1": Signal("QUANT_X1", "Direction Flipped", SignalType.EXIT,
                "Ensemble direction opposite of position", "Close quant position", 100, 1),
            "QUANT_X2": Signal("QUANT_X2", "Score Weakened", SignalType.EXIT,
                "Ensemble score dropped below 0.3", "Close quant position", 100, 2),
        }

    def check_entry_signals(self, market_data: dict) -> List[str]:
        triggered = []
        try:
            qd = json.loads(ENSEMBLE_PATH.read_text())
            ens = qd.get("ensemble", {}).get("signals", {})
            best_ticker, best_score, best_dir = None, 0, "NEUTRAL"
            for ticker, meta in ens.items():
                score = abs(meta.get("ensemble_score", 0))
                if score > best_score:
                    best_score = score
                    best_ticker = ticker
                    best_dir = meta.get("direction", "NEUTRAL")
            if best_ticker and best_score > 0.25:
                qs = qd.get("signals", {}).get(best_ticker, {})
                mc = qs.get("monte-carlo", {})
                if best_dir == "BULLISH" and mc.get("is_significant"):
                    triggered.append("QUANT_E1")
                    market_data["_quant_ticker"] = best_ticker
                    market_data["_quant_score"] = best_score
                elif best_dir == "BEARISH" and mc.get("is_significant"):
                    triggered.append("QUANT_E2")
                    market_data["_quant_ticker"] = best_ticker
                    market_data["_quant_score"] = best_score
        except Exception:
            pass
        return triggered

    def check_exit_signals(self, market_data: dict) -> List[str]:
        triggered = []
        try:
            qd = json.loads(ENSEMBLE_PATH.read_text())
            ens = qd.get("ensemble", {}).get("signals", {})
            for pos in self.open_positions:
                ed = ens.get(pos["symbol"], {})
                curr_dir = ed.get("direction", "NEUTRAL")
                curr_score = abs(ed.get("ensemble_score", 0))
                if pos["direction"] == "long" and curr_dir == "BEARISH":
                    triggered.append("QUANT_X1")
                elif pos["direction"] == "short" and curr_dir == "BULLISH":
                    triggered.append("QUANT_X1")
                if curr_score < 0.3:
                    triggered.append("QUANT_X2")
        except Exception:
            pass
        return triggered

    def execute_entry(self, signal_id: str, price: float, data: dict) -> Optional[int]:
        signal = self.entry_signals.get(signal_id)
        if not signal:
            return None
        ticker = data.get("_quant_ticker", "BTC")
        sym = "IBIT" if ticker == "BTC" else ("ETHA" if ticker == "ETH" else ticker)
        if self.db.has_open_position_for_signal(sym, signal_id):
            self.alerts.append(f"  skip {signal_id} on {sym} - already open")
            return None
        try:
            qd = json.loads(ENSEMBLE_PATH.read_text())
            spot = qd.get("signals", {}).get(ticker, {}).get("mean-reversion", {}).get("close", 0)
            if not spot:
                spot = price
        except Exception:
            spot = price
        if spot <= 0:
            return None
        direction = "long" if signal_id == "QUANT_E1" else "short"

        # Edge-generator confirmation gate
        if EDGE_PATH.exists():
            try:
                eg = json.loads(EDGE_PATH.read_text())
                for rec in eg.get("recommendations", []):
                    if rec.get("ticker") == ticker:
                        eg_rec = rec.get("recommendation", "WAIT")
                        eg_score = rec.get("unified_score", 0)
                        if direction == "long" and eg_rec in ("SELL",):
                            self.alerts.append(
                                f"  BLOCKED {signal_id} on {sym}: edge-gen says {eg_rec} (score={eg_score})")
                            return None
                        if direction == "short" and eg_rec in ("BUY",):
                            self.alerts.append(
                                f"  BLOCKED {signal_id} on {sym}: edge-gen says {eg_rec} (score={eg_score})")
                            return None
                        if eg_rec not in ("BUY", "SELL"):
                            self.alerts.append(
                                f"  edge-gen {eg_rec} (score={eg_score}) - unconfirmed, proceeding")
                        break
            except Exception:
                pass

        allocation = self.initial_cash * (signal.allocation_pct / 100)
        shares = allocation / spot
        trade_id = self.db.open_position(
            symbol=sym, direction=direction, entry_price=spot,
            shares=shares, entry_signal=signal_id,
            notes=f"[QUANT] {signal_id}: {ticker} {direction} @ ${spot:,.2f}, "
                  f"score={data.get('_quant_score', 0):.2f}"
        )
        self.alerts.append(
            f"  {signal.name}: {direction.upper()} {sym} ({ticker}) "
            f"{shares:.4f} sh @ ${spot:,.2f} -> ${allocation:,.0f} deployed"
        )
        return trade_id

    def execute_exit(self, signal_id: str, price: float, data: dict) -> List[int]:
        signal = self.exit_signals.get(signal_id)
        if not signal:
            return []
        closed = []
        for pos in self.open_positions:
            exit_px = price
            try:
                qd = json.loads(ENSEMBLE_PATH.read_text())
                ticker = "BTC" if pos["symbol"] == "IBIT" else "ETH"
                exit_px = qd.get("signals", {}).get(ticker, {}).get(
                    "mean-reversion", {}).get("close", price)
            except Exception:
                exit_px = price
            if exit_px <= 0:
                exit_px = pos["entry_price"]
            pnl = (exit_px - pos["entry_price"]) * pos["shares"] if pos["direction"] == "long" \
                  else (pos["entry_price"] - exit_px) * pos["shares"]
            self.db.close_position(pos["id"], exit_px, signal_id,
                                   f"[QUANT] Exit {signal_id}")
            closed.append(pos["id"])
            pnl_icon = "+" if pnl >= 0 else ""
            self.alerts.append(
                f"  {signal.name}: CLOSED {pos['symbol']} {pos['direction']} "
                f"{pos['shares']:.4f} sh @ ${exit_px:,.2f} -> P&L: {pnl_icon}${pnl:,.2f}"
            )
        if not closed:
            self.alerts.append(f"  {signal_id}: no positions to close")
        return closed


if __name__ == "__main__":
    engine = QuantEngine()
    execute = "--execute" in sys.argv
    result = engine.daily_check({}, execute=execute)
    if execute:
        if engine._executed_signals:
            print(result)
    else:
        print(result)
