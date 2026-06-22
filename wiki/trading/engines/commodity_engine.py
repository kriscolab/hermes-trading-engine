#!/usr/bin/env python3
"""Commodity Engine — v12.0. $100K isolated. Thesis: Currie "Mag7→Mun7."
Schedule: Daily 9:00 AM IST. Journal: journal_commodity.db.

Signal naming: COMM_ENTRY_<trigger> / COMM_EXIT_<trigger>
"""

import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.base import EngineBase, now_ist, load_json

class CommodityEngine(EngineBase):
    ENGINE_NAME = "commodity"
    JOURNAL_DB = "journal_commodity.db"
    TOTAL_CAPITAL = 100_000.0
    CHECK_WINDOW = (9, 10)  # 9:00–9:59 AM IST

    THESIS_ENTRY = {
        "COMM_ENTRY_BRENT_PBACK": {"thesis": "commodity", "name": "Brent Pullback",      "ticker": "XLE", "direction": "long",  "allocation_pct": 25},
        "COMM_ENTRY_BRENT_BREAK": {"thesis": "commodity", "name": "Brent Breakout",      "ticker": "XLE", "direction": "long",  "allocation_pct": 25},
        "COMM_ENTRY_ENERGY_ROT":  {"thesis": "commodity", "name": "Energy Rotation",     "ticker": "XLE", "direction": "long",  "allocation_pct": 25},
        "COMM_ENTRY_GOLD_SHORT":  {"thesis": "commodity", "name": "Gold Tactical Short", "ticker": "GLD", "direction": "short", "allocation_pct": 25},
    }

    THESIS_EXIT = {
        "COMM_EXIT_HORMUZ":      {"thesis": "commodity", "name": "Hormuz Reopens",   "ticker": "XLE"},
        "COMM_EXIT_CAPEX_CUT":   {"thesis": "commodity", "name": "Capex Cuts >30%",  "ticker": "XLE"},
        "COMM_EXIT_ENERGY_SP":   {"thesis": "commodity", "name": "Energy >10% S&P",  "ticker": "XLE"},
        "COMM_EXIT_CONTANGO":    {"thesis": "commodity", "name": "Brent Contango 4w", "ticker": "XLE"},
        "COMM_EXIT_FCF":         {"thesis": "commodity", "name": "FCF Collapse",     "ticker": "XLE"},
    }

    def detect_signals(self):
        """Read live_market_data.json and log triggered entry/exit signals."""
        data = load_json(Path("/tmp/live_market_data.json"))
        if not data:
            return
        tid = self.ENGINE_NAME

        # ── Entry signals ──
        # E1: Brent Pullback — Brent < 50d SMA AND Mun7 FCF > 12%
        sma = data.get("brent_50sma")
        brent = data.get("brent_close", 0)
        if sma and brent < sma and data.get("mun7_fcf_yield", 0) > 0.12:
            self.log_signal("COMM_ENTRY_BRENT_PBACK", True, tid)

        # E2: Brent Breakout — weekly close > $110
        if brent > 110:
            self.log_signal("COMM_ENTRY_BRENT_BREAK", True, tid)

        # E3: Energy Rotation — XLE/XLK higher low OR Energy sector > 4.5%
        if data.get("xle_xlk_ratio_higher_low") or data.get("energy_weight", 0) > 0.045:
            self.log_signal("COMM_ENTRY_ENERGY_ROT", True, tid)

        # E4: Gold Tactical Short — Gold > $3,800 AND DXY rising
        if data.get("gold", 0) > 3800 and data.get("dxy_rising"):
            self.log_signal("COMM_ENTRY_GOLD_SHORT", True, tid)

        # ── Exit signals ──
        if data.get("hormuz_reopen_news"):
            self.log_signal("COMM_EXIT_HORMUZ", True, tid)
        if data.get("mag7_capex_drop", 0) > 0.30:
            self.log_signal("COMM_EXIT_CAPEX_CUT", True, tid)
        if data.get("energy_weight", 0) > 0.10:
            self.log_signal("COMM_EXIT_ENERGY_SP", True, tid)
        if data.get("brent_contango_4w"):
            self.log_signal("COMM_EXIT_CONTANGO", True, tid)
        if data.get("mun7_fcf_yield", 99) < 0.08:
            self.log_signal("COMM_EXIT_FCF", True, tid)

    def run(self):
        if self.summary_mode:
            return []
        self.detect_signals()
        return super().run()


def main():
    execute, summary = "--execute" in sys.argv, "--summary" in sys.argv
    engine = CommodityEngine(execute_mode=execute, summary_mode=summary)
    outputs = engine.run()
    if summary: print(engine.summary())
    elif outputs:
        print(f"[COMMODITY] {now_ist().strftime('%H:%M IST')}")
        for line in outputs: print(f"  {line}")
        print(f"  ── {engine.summary()}")
    engine.close()

if __name__ == "__main__": main()
