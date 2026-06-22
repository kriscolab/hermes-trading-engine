#!/usr/bin/env python3
"""AI Engine — v12.0. $100K isolated. Thesis: Aschenbrenner "AGI by 2027."
Schedule: Daily 9:15 AM IST. Journal: journal_ai.db.

Signal naming: AI_ENTRY_<trigger> / AI_EXIT_<trigger>
Signal uniqueness: AI_ENTRY_CAPEX = 1 SOXX position family max.
"""

import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.base import EngineBase, now_ist, get_live_price, load_json

class AIEngine(EngineBase):
    ENGINE_NAME = "ai"
    JOURNAL_DB = "journal_ai.db"
    TOTAL_CAPITAL = 100_000.0
    CHECK_WINDOW = (9, 10)

    THESIS_ENTRY = {
        "AI_ENTRY_CAPEX":       {"thesis": "ai", "name": "Capex Acceleration",   "ticker": "SOXX", "direction": "long", "allocation_pct": 20},
        "AI_ENTRY_GPU":         {"thesis": "ai", "name": "GPU Demand Surge",     "ticker": "DTCR", "direction": "long", "allocation_pct": 20},
        "AI_ENTRY_SOFTWARE":    {"thesis": "ai", "name": "AI Software Breakout", "ticker": "IGV",  "direction": "long", "allocation_pct": 20},
        "AI_ENTRY_DATACENTER":  {"thesis": "ai", "name": "Data Center Buildout", "ticker": "SOXX", "direction": "long", "allocation_pct": 20},
        "AI_ENTRY_RENEWABLES":  {"thesis": "ai", "name": "Renewables Surge",     "ticker": "TAN",  "direction": "long", "allocation_pct": 20},
    }

    THESIS_EXIT = {
        "AI_EXIT_CAPEX_CUT":   {"thesis": "ai", "name": "Capex Cuts",       "ticker": "SOXX"},
        "AI_EXIT_GPU_OVER":    {"thesis": "ai", "name": "GPU Oversupply",   "ticker": "DTCR"},
        "AI_EXIT_REGULATION":  {"thesis": "ai", "name": "AI Regulation",    "ticker": "IGV"},
        "AI_EXIT_POWER":       {"thesis": "ai", "name": "Power Constraint", "ticker": "DTCR"},
        "AI_EXIT_RENEW_BUST":  {"thesis": "ai", "name": "Renewables Bust",  "ticker": "TAN"},
    }

    # Signal uniqueness: AI_ENTRY_CAPEX family = 1 SOXX position max
    SIGNAL_FAMILIES = {"AI_ENTRY_CAPEX": ["SOXX"]}

    def detect_signals(self):
        """Read daily_state.json for regime + portfolio prices for stop-loss."""
        state = load_json(Path("/home/hermes-pilot/vault/wiki/trading/synthesis/daily_state.json"))
        prices = load_json(Path("/tmp/portfolio_prices.json"))
        tid = self.ENGINE_NAME

        if state:
            ai = state.get("thesis_recommendations", {}).get("ai", {})
            bias = ai.get("bias", "NEUTRAL")

            # Exit signals: if BEARISH, flag exits for all open AI positions
            if bias in ("BEARISH", "SLIGHTLY_BEARISH"):
                for sid, cfg in self.THESIS_EXIT.items():
                    ticker = cfg["ticker"]
                    if self.has_open_signal(sid, ticker):
                        self.alerts.append(f"🚨 {tid} regime {bias}: {cfg['name']} candidate")
                        self.log_signal(sid, True, tid)

        # Stop-loss: flag open positions >25% underwater
        if prices:
            for pos in self.open_positions():
                symbol = pos["symbol"]
                if symbol in prices:
                    entry = float(pos["entry_price"])
                    current = prices[symbol]
                    if entry > 0:
                        pnl_pct = (current - entry) / entry
                        if pos["direction"] == "short":
                            pnl_pct = -pnl_pct
                        if pnl_pct < -0.25:
                            self.alerts.append(f"🛑 {symbol}: {pnl_pct:.1%} drawdown — stop-loss candidate")
                            self.log_signal(f"STOPLOSS_{symbol}", True, tid)

    def run(self):
        if self.summary_mode:
            return []
        self.detect_signals()
        return super().run()

    def execute_entries(self):
        outputs = []
        if not self._in_check_window() or not self.regime.get("allow_entries", True):
            return outputs
        size_mult = self.regime.get("size_multiplier", 1.0)

        for sid, cfg in self.THESIS_ENTRY.items():
            ticker, direction = cfg["ticker"], cfg["direction"]
            alloc_pct, thesis = cfg["allocation_pct"], cfg.get("thesis", self.ENGINE_NAME)

            family_tickers = self.SIGNAL_FAMILIES.get(sid, [ticker])
            already_open = any(
                self.conn.execute("SELECT COUNT(*) as c FROM trades WHERE symbol=? AND status='open' AND entry_signal LIKE 'AI_%'", (ft,)).fetchone()["c"] > 0
                for ft in family_tickers
            )
            if already_open: continue

            opp = "short" if direction == "long" else "long"
            if self.conn.execute("SELECT COUNT(*) as c FROM trades WHERE symbol=? AND direction=? AND status='open'", (ticker, opp)).fetchone()["c"] > 0:
                self.alerts.append(f"⚠️ {sid}: opposite position on {ticker}")
                continue

            pos_val = self.TOTAL_CAPITAL * (alloc_pct / 100.0) * size_mult
            if self.total_deployed() + pos_val > self.TOTAL_CAPITAL * self.HARD_CAP_PCT: continue

            price = get_live_price(ticker)
            if price <= 0: continue

            shares = pos_val / price
            self.open_position(ticker, direction, price, shares, sid, thesis)
            self.log_signal(sid, True, thesis)
            self.mark_executed(sid)
            outputs.append(f"✅ {sid} ({cfg['name']}): {direction} {ticker} @ ${price:.2f} = ${pos_val:,.0f}")
            self.trades_today.append(outputs[-1])
        return outputs


def main():
    execute, summary = "--execute" in sys.argv, "--summary" in sys.argv
    engine = AIEngine(execute_mode=execute, summary_mode=summary)
    outputs = engine.run()
    if summary: print(engine.summary())
    elif outputs:
        print(f"[AI] {now_ist().strftime('%H:%M IST')}")
        for l in outputs: print(f"  {l}")
        print(f"  ── {engine.summary()}")
    engine.close()

if __name__ == "__main__": main()
