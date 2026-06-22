#!/usr/bin/env python3
"""
Intraday Crypto Engine — $25K TA-Driven
=========================================
Standalone engine for short-term crypto trades (IBIT, ETHA, SOL, AVAX, LINK, DOGE).
5% per trade, -2% SL, +3% TP, 4h timeout. Multiple concurrent positions allowed.

Usage:
  python3 engines/intraday_crypto_engine.py                  # Check only
  python3 engines/intraday_crypto_engine.py --execute         # Check + execute
  python3 engines/intraday_crypto_engine.py --summary         # Portfolio summary
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from base import BaseEngine, Signal, SignalType

IST = timezone(timedelta(hours=5, minutes=30))
INTRA_PATH = Path("/tmp/intraday_signals.json")
CRYPTO_DATA = Path("/tmp/crypto_module_data.json")

TICKER_MAP = {"BTC": "IBIT", "ETH": "ETHA", "SOL": "SOL", "AVAX": "AVAX",
              "LINK": "LINK", "DOGE": "DOGE"}


def get_live_price(symbol: str) -> float:
    try:
        cp = json.loads(CRYPTO_DATA.read_text())
        prices = cp.get("prices", {})
        return prices.get(symbol.lower(), 0)
    except Exception:
        return 0


class IntradayCryptoEngine(BaseEngine):
    name = "intraday"
    initial_cash = 25_000.0

    @property
    def entry_signals(self) -> Dict:
        return {
            "INTRADAY_LONG": Signal("INTRADAY_LONG", "Intraday Crypto Long",
                SignalType.ENTRY, "Pullback/breakout long", "Long at 5%, -2% SL, +3% TP", 5, 1),
            "INTRADAY_SHORT": Signal("INTRADAY_SHORT", "Intraday Crypto Short",
                SignalType.ENTRY, "Rejection/breakdown short", "Short at 5%, -2% SL, +3% TP", 5, 1),
        }

    @property
    def exit_signals(self) -> Dict:
        return {
            "INTRADAY_X1": Signal("INTRADAY_X1", "Take Profit (+3%)", SignalType.EXIT,
                "TP reached", "Close position", 100, 1),
            "INTRADAY_X2": Signal("INTRADAY_X2", "Stop Loss (-2%)", SignalType.EXIT,
                "SL breached", "Close position", 100, 2),
            "INTRADAY_X3": Signal("INTRADAY_X3", "Timeout (4h)", SignalType.EXIT,
                "Max hold exceeded", "Close position", 100, 3),
        }

    def check_entry_signals(self, market_data: dict) -> List[str]:
        triggered = []
        try:
            isd = json.loads(INTRA_PATH.read_text())
            for sig in isd.get("signals", []):
                signal_id = sig.get("signal", "")
                if signal_id and signal_id.startswith("INTRADAY_"):
                    triggered.append(signal_id)
                    market_data["_entry_price"] = sig.get("entry_price", 0)
                    market_data["_ticker"] = sig.get("ticker", "")
        except Exception:
            pass
        return triggered

    def check_exit_signals(self, market_data: dict) -> List[str]:
        triggered = []
        now = datetime.now()
        for pos in self.open_positions:
            sym = pos["symbol"]
            entry = pos["entry_price"]
            live = get_live_price(sym)
            if live <= 0:
                live = entry
            direction = pos["direction"]
            pnl_pct = ((live - entry) / entry) if direction == "long" else ((entry - live) / entry)
            if pnl_pct >= 0.03:
                triggered.append("INTRADAY_X1")
                market_data["_exit_price"] = live
                market_data["_exit_ticker"] = sym
            elif pnl_pct <= -0.02:
                triggered.append("INTRADAY_X2")
                market_data["_exit_price"] = live
                market_data["_exit_ticker"] = sym
            try:
                ts = pos.get("entry_timestamp")
                if ts:
                    entered = datetime.fromisoformat(ts)
                    if entered.tzinfo:
                        entered = entered.replace(tzinfo=None)
                    hours_open = (now.replace(tzinfo=None) - entered).total_seconds() / 3600
                    if hours_open > 4:
                        triggered.append("INTRADAY_X3")
                        market_data["_exit_price"] = live
                        market_data["_exit_ticker"] = sym
            except Exception:
                pass
        return triggered

    def execute_entry(self, signal_id: str, price: float, data: dict) -> Optional[int]:
        signal = self.entry_signals.get(signal_id)
        if not signal:
            return None
        ticker = data.get("_ticker") or "BTC"
        sym = TICKER_MAP.get(ticker, ticker)
        entry_px = data.get("_entry_price", price)
        if entry_px <= 0:
            entry_px = get_live_price(sym)
        if entry_px <= 0:
            return None
        if self.db.has_open_position_for_signal(sym, signal_id):
            self.alerts.append(f"  skip {signal_id} on {sym} — already open")
            return None
        direction = "long" if "LONG" in signal_id else "short"
        allocation = self.initial_cash * (signal.allocation_pct / 100)
        shares = allocation / entry_px
        trade_id = self.db.open_position(
            symbol=sym, direction=direction, entry_price=entry_px,
            shares=shares, entry_signal=signal_id,
            notes=f"[INTRADAY] {signal_id}: {ticker} {direction} @ ${entry_px:,.2f}, "
                  f"-2% SL, +3% TP"
        )
        self.alerts.append(
            f"  {signal.name}: {direction.upper()} {sym} ({ticker}) "
            f"{shares:.4f} sh @ ${entry_px:,.2f} -> ${allocation:,.0f} deployed"
        )
        return trade_id

    def execute_exit(self, signal_id: str, price: float, data: dict) -> List[int]:
        signal = self.exit_signals.get(signal_id)
        if not signal:
            return []
        target_symbol = data.get("_exit_ticker", "")
        exit_px = data.get("_exit_price", price)
        if exit_px <= 0:
            exit_px = price
        closed = []
        for pos in self.open_positions:
            if target_symbol and pos["symbol"] != target_symbol:
                continue
            pnl = (exit_px - pos["entry_price"]) * pos["shares"] if pos["direction"] == "long" \
                  else (pos["entry_price"] - exit_px) * pos["shares"]
            self.db.close_position(pos["id"], exit_px, signal_id,
                                   f"[INTRADAY] Exit {signal_id}")
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
    engine = IntradayCryptoEngine()
    execute = "--execute" in sys.argv
    result = engine.daily_check({}, execute=execute)
    if execute:
        if engine._executed_signals:
            print(result)
        # else: cron mode, silent — nothing executed
    else:
        print(result)
