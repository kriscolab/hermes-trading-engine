#!/usr/bin/env python3
"""
Unified Execution Engine v1.0
==============================
Single engine, one cron, one journal. All theses, all signal types.

Reads ALL signal sources → checks execution gates → trades → journals → outputs.
Replaces: quant_engine.py, intraday_crypto_engine.py, quant-executor.sh,
          intraday-executor.sh, quant-engine.sh, intraday-crypto-engine.sh.

Usage:
  python3 engines/unified_engine.py              # Check only (full output)
  python3 engines/unified_engine.py --execute    # Cron mode (silent unless trade)
  python3 engines/unified_engine.py --summary    # Portfolio snapshot
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

IST = timezone(timedelta(hours=5, minutes=30))

# ── Paths ────────────────────────────────────────────────────────────────
TRADING_DIR = Path(__file__).resolve().parent.parent
DB_PATH = TRADING_DIR / "paper-trader" / "journal.db"
QUANT_PATH = Path("/tmp/quant_signals.json")
INTRADAY_PATH = Path("/tmp/intraday_signals.json")
EDGE_PATH = Path("/tmp/edge_generator.json")
PRICES_PATH = Path("/tmp/portfolio_prices.json")
CRYPTO_PATH = Path("/tmp/crypto_module_data.json")
MARKET_PATH = Path("/tmp/live_market_data.json")
SYNTH_PATH = TRADING_DIR / "synthesis" / "daily_state.json"
RISK_PATH = Path("/tmp/risk_alerts.json")

# ── Capital Allocation ───────────────────────────────────────────────────
TOTAL_CAPITAL = 100_000.0
ALLOC = {
    "commodity": 0.40,   # $40K
    "ai":         0.30,  # $30K
    "crypto":     0.15,  # $15K
    "quant":      0.10,  # $10K
    "intraday":   0.05,  # $5K
}
HARD_CAP_PCT = 0.80  # Never exceed 80% of total across all theses

# ── Signal Definitions ───────────────────────────────────────────────────
# Thesis entry signals (commodity, AI, crypto)
THESIS_ENTRY = {
    # Commodity (Currie Mag7→Mun7)
    "E1":   {"thesis": "commodity", "name": "Brent Pullback",            "ticker": "XLE",  "direction": "long",  "allocation_pct": 15},
    "E2":   {"thesis": "commodity", "name": "Brent Breakout",            "ticker": "XLE",  "direction": "long",  "allocation_pct": 15},
    "E3":   {"thesis": "commodity", "name": "Energy Rotation",           "ticker": "XLE",  "direction": "long",  "allocation_pct": 10},
    "E4S":  {"thesis": "commodity", "name": "Gold Tactical Short",       "ticker": "GLD",  "direction": "short", "allocation_pct": 10},
    "E4L":  {"thesis": "commodity", "name": "Gold Structural Long",      "ticker": "GLD",  "direction": "long",  "allocation_pct": 10},
    # AI (Aschenbrenner AGI 2027)
    "AI_E1": {"thesis": "ai", "name": "Capex Acceleration", "ticker": "SOXX", "direction": "long", "allocation_pct": 20},
    "AI_E2": {"thesis": "ai", "name": "GPU Demand Surge",   "ticker": "SOXX", "direction": "long", "allocation_pct": 5},
    "AI_E3": {"thesis": "ai", "name": "AI Software Breakout","ticker": "IGV",  "direction": "long", "allocation_pct": 5},
    "AI_E4": {"thesis": "ai", "name": "Data Center Buildout","ticker": "DTCR", "direction": "long", "allocation_pct": 5},
    "AI_E5": {"thesis": "ai", "name": "Renewables Surge",   "ticker": "TAN",  "direction": "long", "allocation_pct": 5},
    # Crypto (6-layer confluence)
    "CRYPTO_E1": {"thesis": "crypto", "name": "3/6 Confluence",         "ticker": "IBIT", "direction": "long", "allocation_pct": 25},
    "CRYPTO_E2": {"thesis": "crypto", "name": "4/6 + Whale Accum",     "ticker": "IBIT", "direction": "long", "allocation_pct": 25},
    "CRYPTO_E3": {"thesis": "crypto", "name": "Price/Flow Divergence", "ticker": "IBIT", "direction": "long", "allocation_pct": 25},
    "CRYPTO_E4": {"thesis": "crypto", "name": "Breakout on Volume",    "ticker": "IBIT", "direction": "long", "allocation_pct": 25},
}

THESIS_EXIT = {
    "X1":  {"thesis": "commodity", "name": "Hormuz Reopens",       "ticker": "XLE"},
    "X2":  {"thesis": "commodity", "name": "Capex Cuts >30%",      "ticker": "XLE"},
    "X3":  {"thesis": "commodity", "name": "Energy >10% S&P",      "ticker": "XLE"},
    "X4":  {"thesis": "commodity", "name": "Brent Contango 4w",    "ticker": "XLE"},
    "X5":  {"thesis": "commodity", "name": "FCF Collapse",         "ticker": "XLE"},
    "AI_X1": {"thesis": "ai", "name": "Capex Cuts",                "ticker": "SOXX"},
    "AI_X2": {"thesis": "ai", "name": "GPU Oversupply",            "ticker": "SOXX"},
    "AI_X3": {"thesis": "ai", "name": "AI Regulation",             "ticker": "IGV"},
    "AI_X4": {"thesis": "ai", "name": "Power Constraint",          "ticker": "DTCR"},
    "AI_X5": {"thesis": "ai", "name": "Renewables Bust",           "ticker": "TAN"},
    "CRYPTO_X1": {"thesis": "crypto", "name": "Reserves +5%",      "ticker": "IBIT"},
    "CRYPTO_X2": {"thesis": "crypto", "name": "Whale Distribution", "ticker": "IBIT"},
    "CRYPTO_X3": {"thesis": "crypto", "name": "Derivatives Overheat","ticker": "IBIT"},
    "CRYPTO_X4": {"thesis": "crypto", "name": "BTC/SPY Corr >0.7", "ticker": "IBIT"},
    "CRYPTO_X5": {"thesis": "crypto", "name": "Regulatory Shock",  "ticker": "IBIT"},
}

# Intraday tickers (standalone engine tickers)
INTRADAY_TICKERS = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE"]
TICKER_TO_INSTRUMENT = {"BTC": "IBIT", "ETH": "ETHA", "SOL": "SOL",
                         "AVAX": "AVAX", "LINK": "LINK", "DOGE": "DOGE"}

# ── Helpers ──────────────────────────────────────────────────────────────

def now_ist():
    return datetime.now(IST)

def load_json(path: Path) -> dict:
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return {}

def get_live_price(symbol: str) -> float:
    """Get live price from available data sources."""
    symbol_upper = symbol.upper()
    # Try portfolio prices first (equity/ETF)
    if PRICES_PATH.exists():
        try:
            prices = json.loads(PRICES_PATH.read_text())
            if symbol_upper in prices:
                return float(prices[symbol_upper])
        except: pass
    # Try crypto data
    if CRYPTO_PATH.exists():
        try:
            cp = json.loads(CRYPTO_PATH.read_text())
            prices = cp.get("prices", {})
            sym_lower = symbol_upper.lower()
            if sym_lower in prices:
                return float(prices[sym_lower])
        except: pass
    return 0.0

def get_thesis_deployed(db, thesis: str) -> float:
    """Calculate total deployed capital for a thesis."""
    rows = db.execute(
        "SELECT COALESCE(SUM(shares * entry_price), 0) FROM trades WHERE status='open' AND entry_signal IN "
        "(SELECT signal_id FROM signal_log WHERE thesis_id=? GROUP BY signal_id)",
        (thesis,)
    ).fetchone()
    return float(rows[0]) if rows else 0.0

# ── Engine ───────────────────────────────────────────────────────────────

class UnifiedEngine:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.trades_today: List[str] = []
        self.alerts: List[str] = []

    # ── DB Helpers ──

    def open_position(self, symbol, direction, entry_price, shares, entry_signal, thesis_id):
        now = now_ist()
        cursor = self.conn.execute(
            """INSERT INTO trades (trade_date, symbol, direction, entry_price, shares,
               entry_signal, status, entry_timestamp, thesis_id)
               VALUES (?,?,?,?,?,?,'open',?,?)""",
            (now.strftime("%Y-%m-%d"), symbol, direction, entry_price,
             round(shares, 6), entry_signal, now.isoformat(), thesis_id)
        )
        self.conn.commit()
        return cursor.lastrowid

    def close_position(self, trade_id, exit_price, exit_signal, notes=""):
        trade = self.conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if not trade: return
        direction = trade["direction"]
        entry_price = trade["entry_price"]
        shares = trade["shares"]
        pnl = (exit_price - entry_price) * shares if direction == "long" \
              else (entry_price - exit_price) * shares
        pnl = round(pnl, 2)
        now = now_ist()
        self.conn.execute(
            """UPDATE trades SET exit_date=?, exit_price=?, exit_signal=?,
               pnl_realized=?, status='closed', notes=? WHERE id=?""",
            (now.strftime("%Y-%m-%d"), exit_price, exit_signal, pnl,
             notes if notes else "", trade_id)
        )
        self.conn.commit()
        return pnl, trade["symbol"], trade["direction"]

    def has_open_signal(self, entry_signal, symbol=None):
        if symbol:
            r = self.conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE entry_signal=? AND symbol=? AND status='open'",
                (entry_signal, symbol)
            ).fetchone()
        else:
            r = self.conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE entry_signal=? AND status='open'",
                (entry_signal,)
            ).fetchone()
        return r["c"] > 0

    def mark_signal_executed(self, signal_id):
        now = now_ist().strftime("%Y-%m-%d %H:%M")
        self.conn.execute(
            "UPDATE signal_log SET executed=1, notes='Executed by unified engine' "
            "WHERE signal_id=? AND triggered=1 AND executed=0",
            (signal_id,)
        )
        self.conn.commit()

    # ── Thesis Cadence ──
    # Commodity + AI are long-duration theses (days-weeks). Only check them
    # during the 9:00-9:45 AM IST window (03:00-03:45 UTC) after the signal
    # check cron has fired. Quant + intraday + edge-gen run every tick.
    def _check_commodity_ai_today(self) -> bool:
        """Only check commodity/AI thesis signals in the morning window."""
        now = now_ist()
        return 9 <= now.hour < 10  # 9:00-9:59 AM IST

    def get_pending_thesis_signals(self):
        """Get thesis signals that triggered but haven't been executed."""
        return [dict(r) for r in self.conn.execute(
            "SELECT signal_id, thesis_id, check_date FROM signal_log "
            "WHERE triggered=1 AND executed=0 "
            "AND signal_id NOT LIKE '%X%' AND signal_id NOT LIKE '%INTRADAY%' AND signal_id NOT LIKE '%QUANT%' "
            "ORDER BY check_date ASC"
        ).fetchall()]

    def get_pending_exit_signals(self):
        """Get exit signals that triggered but haven't been executed."""
        return [dict(r) for r in self.conn.execute(
            "SELECT signal_id, thesis_id, check_date FROM signal_log "
            "WHERE triggered=1 AND executed=0 "
            "AND (signal_id LIKE '%X%' OR signal_id LIKE '%INTRADAY_X%' OR signal_id LIKE '%QUANT_X%') "
            "ORDER BY check_date ASC"
        ).fetchall()]

    # ── Portfolio State ──

    def total_deployed(self):
        r = self.conn.execute(
            "SELECT COALESCE(SUM(shares * entry_price), 0) FROM trades WHERE status='open'"
        ).fetchone()
        return float(r[0])

    def total_equity(self):
        deployed = self.total_deployed()
        closed_pnl = self.conn.execute(
            "SELECT COALESCE(SUM(pnl_realized), 0) FROM trades WHERE status='closed'"
        ).fetchone()
        return TOTAL_CAPITAL - deployed + float(closed_pnl[0])

    def open_positions(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT id, symbol, direction, entry_price, shares, entry_signal, trade_date FROM trades WHERE status='open'"
        ).fetchall()]

    # ═════════════════════════════════════════════════════════════════════
    # THESIS SIGNAL EXECUTION
    # ═════════════════════════════════════════════════════════════════════

    def execute_thesis_entries(self) -> List[str]:
        """Execute pending thesis entry signals. Commodity/AI only in 9 AM IST window."""
        outputs = []

        # Commodity + AI are long-duration — only check in morning window
        check_commodity_ai = self._check_commodity_ai_today()
        pending = self.get_pending_thesis_signals()

        for sig in pending:
            sid = sig["signal_id"]
            thesis = sig.get("thesis_id", "")

            if sid not in THESIS_ENTRY:
                continue

            # Time-gate: commodity/AI only 9:00-9:59 AM IST
            if thesis in ("commodity", "ai") and not check_commodity_ai:
                continue

            cfg = THESIS_ENTRY[sid]
            ticker = cfg["ticker"]
            direction = cfg["direction"]
            alloc_pct = cfg["allocation_pct"]

            # ── Guards ──
            # 1. Already have open position for this signal?
            if self.has_open_signal(sid, ticker):
                self.mark_signal_executed(sid)
                continue

            # 2. Opposite position?
            opp_dir = "short" if direction == "long" else "long"
            opp = self.conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE symbol=? AND direction=? AND status='open'",
                (ticker, opp_dir)
            ).fetchone()
            if opp["c"] > 0:
                self.alerts.append(f"⚠️ {sid}: opposite position open on {ticker} — skipped")
                self.mark_signal_executed(sid)
                continue

            # 3. Capital cap check
            thesis_alloc = TOTAL_CAPITAL * ALLOC.get(thesis, 0.10)
            deployed_thesis = self.conn.execute(
                "SELECT COALESCE(SUM(shares*entry_price),0) FROM trades WHERE status='open' AND entry_signal IN "
                "(SELECT signal_id FROM signal_log WHERE thesis_id=?)",
                (thesis,)
            ).fetchone()[0]
            deployed_thesis = float(deployed_thesis)

            position_size = thesis_alloc * (alloc_pct / 100.0)
            if deployed_thesis + position_size > thesis_alloc:
                self.alerts.append(f"⚠️ {sid}: thesis cap reached ({thesis}) — skipped")
                self.mark_signal_executed(sid)
                continue

            # 4. Global hard cap
            if self.total_deployed() + position_size > TOTAL_CAPITAL * HARD_CAP_PCT:
                self.alerts.append(f"⚠️ {sid}: global hard cap — skipped")
                self.mark_signal_executed(sid)
                continue

            # 5. Get live price
            price = get_live_price(ticker)
            if price <= 0:
                self.alerts.append(f"⚠️ {sid}: no price for {ticker} — skipped")
                continue

            # ── Execute ──
            shares = position_size / price
            trade_id = self.open_position(ticker, direction, price, shares, sid, thesis)
            if trade_id:
                self.mark_signal_executed(sid)
                direction_icon = "🟢 LONG" if direction == "long" else "🔴 SHORT"
                outputs.append(
                    f"✅ {direction_icon} | {sid} ({cfg['name']}) | "
                    f"{ticker} | {shares:.2f} sh @ ${price:,.2f} | "
                    f"Size: ${position_size:,.0f}"
                )

        return outputs

    def execute_thesis_exits(self) -> List[str]:
        """Execute pending thesis exit signals. Commodity/AI only in 9 AM IST window."""
        outputs = []
        check_commodity_ai = self._check_commodity_ai_today()
        pending = self.get_pending_exit_signals()

        for sig in pending:
            sid = sig["signal_id"]

            if sid not in THESIS_EXIT:
                continue

            # Time-gate: commodity/AI exits only in morning window
            thesis = THESIS_EXIT[sid].get("thesis", "")
            if thesis in ("commodity", "ai") and not check_commodity_ai:
                continue

            cfg = THESIS_EXIT[sid]
            ticker = cfg["ticker"]

            # Find open positions for this ticker
            open_for_ticker = self.conn.execute(
                "SELECT id, symbol, direction, entry_price, shares, entry_signal FROM trades WHERE symbol=? AND status='open'",
                (ticker,)
            ).fetchall()

            if not open_for_ticker:
                self.mark_signal_executed(sid)
                continue

            # Close all positions for this ticker
            price = get_live_price(ticker)
            if price <= 0:
                self.alerts.append(f"⚠️ {sid}: no price for {ticker}")
                continue

            for pos in open_for_ticker:
                pnl, sym, direc = self.close_position(pos["id"], price, sid, f"Exit: {cfg['name']}")
                icon = "📈" if pnl > 0 else "📉"
                outputs.append(
                    f"🔴 CLOSED | {sid} ({cfg['name']}) | {sym} {direc} | "
                    f"P&L: ${pnl:+,.0f} {icon}"
                )

            self.mark_signal_executed(sid)

        return outputs

    # ═════════════════════════════════════════════════════════════════════
    # REGIME GATE — loaded from synthesizer, gates ALL execution
    # ═════════════════════════════════════════════════════════════════════

    def _load_regime(self) -> dict:
        """Load market regime from synthesizer's daily_state.json."""
        d = load_json(SYNTH_PATH)
        regime = d.get("market_regime", {})
        risk = d.get("primary_risk_factor", {})
        thesis_recs = d.get("thesis_recommendations", {})
        return {
            "regime": regime.get("primary", "NEUTRAL"),
            "confidence": regime.get("confidence", 0.5),
            "risk_severity": risk.get("severity", "MEDIUM"),
            "commodity_size": thesis_recs.get("commodity", {}).get("size_adjustment", 1.0),
            "crypto_size": thesis_recs.get("crypto", {}).get("size_adjustment", 1.0),
            "ai_size": thesis_recs.get("ai", {}).get("size_adjustment", 1.0),
        }

    def _regime_allows_entries(self, regime: dict) -> bool:
        """RISK_OFF blocks all new entries. CAUTIOUS allows half-size."""
        return regime["regime"] != "RISK_OFF"

    def _regime_size_multiplier(self, regime: dict, thesis: str) -> float:
        """Return position size multiplier based on regime + thesis bias."""
        base = {
            "RISK_ON": 1.0,
            "TRENDING": 1.0,
            "NEUTRAL": 1.0,
            "CAUTIOUS": 0.5,
            "RISK_OFF": 0.0,  # No entries
        }.get(regime["regime"], 1.0)
        # Layer thesis-specific size adjustment from synthesizer
        thesis_key = f"{thesis}_size"
        thesis_adj = regime.get(thesis_key, 1.0)
        return base * thesis_adj

    # ═════════════════════════════════════════════════════════════════════
    # CRYPTO CROSS-CHECK — quant ensemble × intraday signals
    # ═════════════════════════════════════════════════════════════════════

    def _crypto_cross_check(self, ticker: str) -> tuple:
        """
        Compare quant and intraday signals for a ticker.
        Returns: (verdict, size_mult)
          CONFIRMED  = both agree → 1.5x
          QUANT_ONLY = only quant fires → 1.0x
          INTRADAY_ONLY = only intraday → 0.5x
          CONFLICT   = opposite directions → skip
          NONE       = neither fires → skip
        """
        qd = load_json(QUANT_PATH)
        idata = load_json(INTRADAY_PATH)

        # Quant direction
        ens = qd.get("ensemble", {}).get("signals", {})
        q_meta = ens.get(ticker, {})
        q_score = abs(q_meta.get("ensemble_score", 0))
        q_dir = q_meta.get("direction", "NEUTRAL")
        q_firing = q_score > 0.25 and q_dir != "NEUTRAL"

        # MC gate for quant
        if q_firing:
            qs = qd.get("signals", {}).get(ticker, {})
            mc = qs.get("monte-carlo", {})
            if not mc.get("passed", False):
                q_firing = False

        # Intraday direction
        id_signals = idata.get("signals", [])
        id_dir = None
        for s in id_signals:
            if s.get("ticker", "").upper() == ticker.upper():
                id_dir = s.get("direction", "")
                break

        q_is_bull = q_dir == "BULLISH"
        q_is_bear = q_dir == "BEARISH"

        if q_firing and id_dir:
            if (q_is_bull and id_dir == "long") or (q_is_bear and id_dir == "short"):
                return ("CONFIRMED", 1.5)
            else:
                return ("CONFLICT", 0.0)
        elif q_firing:
            return ("QUANT_ONLY", 1.0)
        elif id_dir:
            return ("INTRADAY_ONLY", 0.5)
        else:
            return ("NONE", 0.0)

    # ═════════════════════════════════════════════════════════════════════
    # CRYPTO LANE — quant ensemble × intraday cross-check + regime gate
    # ═════════════════════════════════════════════════════════════════════

    def execute_crypto_lane(self, regime: dict) -> List[str]:
        """
        Crypto execution with cross-check + regime gate.
        Quant ensemble and intraday signals are cross-checked per ticker.
        Regime determines size multiplier. CRYPTO thesis signals checked separately.
        """
        outputs = []

        # Regime gate: no crypto entries in RISK_OFF
        if not self._regime_allows_entries(regime):
            return outputs

        size_mult = self._regime_size_multiplier(regime, "crypto")
        crypto_alloc = TOTAL_CAPITAL * ALLOC["crypto"]

        # Get all crypto tickers from quant ensemble + intraday
        qd = load_json(QUANT_PATH)
        ens = qd.get("ensemble", {}).get("signals", {})
        idata = load_json(INTRADAY_PATH)
        id_signals = idata.get("signals", [])

        # Collect all tickers that appear in either source
        all_crypto_tickers = set(ens.keys())
        for s in id_signals:
            t = s.get("ticker", "").upper()
            if t:
                all_crypto_tickers.add(t)

        for ticker in all_crypto_tickers:
            verdict, x_mult = self._crypto_cross_check(ticker)
            if verdict in ("NONE", "CONFLICT"):
                if verdict == "CONFLICT":
                    self.alerts.append(f"⚠️ CONFLICT {ticker}: quant × intraday disagree — skipped")
                continue

            instrument = TICKER_TO_INSTRUMENT.get(ticker.upper(), ticker.upper())

            # Determine direction from the firing lane
            q_meta = ens.get(ticker, {})
            if verdict == "QUANT_ONLY" or verdict == "CONFIRMED":
                direction = "long" if q_meta.get("direction") == "BULLISH" else "short"
            else:  # INTRADAY_ONLY
                for s in id_signals:
                    if s.get("ticker", "").upper() == ticker.upper():
                        direction = s.get("direction", "long")
                        break
                else:
                    continue

            # Guard: already have crypto position for this ticker
            if self.has_open_signal(f"CRYPTO_{ticker}", instrument):
                continue

            # Position sizing: base allocation × cross-check multiplier × regime multiplier
            base_size = crypto_alloc * 0.10  # 10% of crypto allocation per position
            position_size = base_size * x_mult * size_mult

            # Cap check
            deployed_crypto = float(self.conn.execute(
                "SELECT COALESCE(SUM(shares*entry_price),0) FROM trades WHERE status='open' AND entry_signal LIKE 'CRYPTO_%'"
            ).fetchone()[0])
            if deployed_crypto + position_size > crypto_alloc:
                continue

            # Global hard cap
            if self.total_deployed() + position_size > TOTAL_CAPITAL * HARD_CAP_PCT:
                continue

            price = get_live_price(instrument)
            if price <= 0:
                continue

            shares = position_size / price
            sig_id = f"CRYPTO_{ticker}"
            trade_id = self.open_position(instrument, direction, price, shares, sig_id, "crypto")
            if trade_id:
                verdict_label = {"CONFIRMED": "🔥 CONFIRMED", "QUANT_ONLY": "📊 QUANT", "INTRADAY_ONLY": "⚡ INTRADAY"}
                label = verdict_label.get(verdict, verdict)
                icon = "🟢 LONG" if direction == "long" else "🔴 SHORT"
                outputs.append(
                    f"✅ {icon} | {label} {ticker} | {instrument} | "
                    f"{shares:.2f} sh @ ${price:,.2f} | "
                    f"x{x_mult:.1f}(cross)×{size_mult:.1f}(regime) | ${position_size:,.0f}"
                )

        return outputs

    # ═════════════════════════════════════════════════════════════════════
    # INTRADAY EXITS (TP/SL/Timeout)
    # ═════════════════════════════════════════════════════════════════════

    def execute_intraday_exits(self) -> List[str]:
        """Check and execute intraday TP/SL/timeout exits."""
        outputs = []
        open_id = self.conn.execute(
            "SELECT * FROM trades WHERE status='open' AND entry_signal LIKE 'INTRADAY_%'"
        ).fetchall()

        for pos in open_id:
            pos = dict(pos)
            ticker = pos["symbol"]
            entry_price = pos["entry_price"]
            entry_time_str = pos.get("entry_timestamp", "")
            direction = pos["direction"]
            shares = pos["shares"]
            trade_id = pos["id"]

            price = get_live_price(ticker)
            if price <= 0:
                continue

            # Calculate P&L
            if direction == "long":
                pnl_pct = (price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - price) / entry_price

            exit_reason = None

            # TP: +3%
            if pnl_pct >= 0.03:
                exit_reason = f"TP +{pnl_pct*100:.1f}%"
            # SL: -2%
            elif pnl_pct <= -0.02:
                exit_reason = f"SL {pnl_pct*100:.1f}%"
            # Timeout: 4 hours
            elif entry_time_str:
                try:
                    entry_time = datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
                    if (now_ist() - entry_time).total_seconds() > 4 * 3600:
                        exit_reason = f"Timeout {pnl_pct*100:.1f}%"
                except:
                    pass

            if exit_reason:
                pnl, sym, direc = self.close_position(trade_id, price, "INTRADAY_X", exit_reason)
                icon = "📈" if pnl > 0 else "📉"
                outputs.append(
                    f"🔴 CLOSED | INTRADAY {sym} {direc} | "
                    f"P&L: ${pnl:+,.0f} {icon} | {exit_reason}"
                )

        return outputs

    # ═════════════════════════════════════════════════════════════════════
    # EDGE GENERATOR EXECUTION
    # ═════════════════════════════════════════════════════════════════════

    def execute_edge_signals(self) -> List[str]:
        """Execute edge generator picks that cross the 50 threshold."""
        outputs = []
        ed = load_json(EDGE_PATH)
        if not ed:
            return outputs

        picks = ed.get("top_picks", [])
        if not isinstance(picks, list) or not picks:
            return outputs

        for pick in picks:
            ticker = pick.get("ticker", "")
            action = pick.get("action", "")
            edge_score = pick.get("edge_score", 0)
            confidence = pick.get("confidence", "")

            instrument = TICKER_TO_INSTRUMENT.get(ticker.upper(), ticker.upper())

            # Gate: edge_score > 50
            if edge_score <= 50:
                continue

            direction = "long" if action == "BUY" else ("short" if action == "SELL" else None)
            if not direction:
                continue

            if self.has_open_signal(f"EDGE_{ticker}", instrument):
                continue

            price = get_live_price(instrument)
            if price <= 0:
                continue

            # Use quant allocation for edge-gen trades
            quant_alloc = TOTAL_CAPITAL * ALLOC["quant"]
            position_size = quant_alloc * 0.10
            shares = position_size / price

            sig_id = f"EDGE_{ticker}"
            trade_id = self.open_position(instrument, direction, price, shares, sig_id, "quant")
            if trade_id:
                icon = "🟢 LONG" if direction == "long" else "🔴 SHORT"
                outputs.append(
                    f"✅ {icon} | EDGE {ticker} | {instrument} | "
                    f"{shares:.2f} sh @ ${price:,.2f} | Edge: {edge_score} | ${position_size:,.0f}"
                )

        return outputs

    # ═════════════════════════════════════════════════════════════════════
    # ORCHESTRATION
    # ═════════════════════════════════════════════════════════════════════

    def run(self, execute: bool = False) -> str:
        """Run all checks. If execute=True, also trade. Return output string."""
        self.alerts = []
        self.trades_today = []

        # ── Load regime (top gate for ALL execution) ──
        regime = self._load_regime()

        # 1. Intraday exits first (time-sensitive)
        intraday_exits = self.execute_intraday_exits() if execute else []

        # 2. Thesis exits (commodity/AI: 9 AM only; crypto: always)
        thesis_exits = self.execute_thesis_exits() if execute else []

        # 3. Crypto lane: quant × intraday cross-check + regime gate (every tick)
        crypto_trades = self.execute_crypto_lane(regime) if execute else []

        # 4. Thesis entries: commodity/AI only 9 AM window, crypto always
        thesis_entries = self.execute_thesis_entries() if execute else []

        # 5. Edge-gen entries (every tick)
        edge_entries = self.execute_edge_signals() if execute else []

        all_trades = intraday_exits + thesis_exits + crypto_trades + thesis_entries + edge_entries

        if not execute:
            # Check mode: full report
            return self._format_check_report()

        # Execute mode: silent if no trades
        if not all_trades:
            return ""  # Empty = silent delivery

        # Format trade output
        lines = [f"🤖 UNIFIED — {now_ist().strftime('%b %d %H:%M IST')}"]
        lines.extend(all_trades)
        if self.alerts:
            lines.append("")
            lines.append("⚠️ Alerts:")
            lines.extend(f"  {a}" for a in self.alerts)

        # Portfolio snapshot
        deployed = self.total_deployed()
        equity = self.total_equity()
        pnl_total = float(self.conn.execute(
            "SELECT COALESCE(SUM(pnl_realized),0) FROM trades WHERE status='closed'"
        ).fetchone()[0])
        open_count = len(self.open_positions())
        lines.append("")
        lines.append(f"📊 Deployed: ${deployed:,.0f} | Equity: ${equity:,.0f} | "
                      f"Realized P&L: ${pnl_total:+,.0f} | Open: {open_count}")

        return "\n".join(lines)

    def _format_check_report(self) -> str:
        """Full check-mode report (no trades)."""
        regime = self._load_regime()
        lines = [f"═══ Unified Engine — Check {now_ist().strftime('%b %d %H:%M IST')} ═══", ""]

        # ── Regime ──
        r_label = regime["regime"]
        r_icon = {"RISK_ON": "🟢", "TRENDING": "🟢", "NEUTRAL": "🟡", "CAUTIOUS": "🟠", "RISK_OFF": "🔴"}
        lines.append(f"Regime: {r_icon.get(r_label, '⚪')} {r_label} (conf={regime['confidence']:.0%}) | "
                     f"Risk: {regime['risk_severity']} | Sizes: C={regime['commodity_size']:.1f}x "
                     f"AI={regime['ai_size']:.1f}x Crypto={regime['crypto_size']:.1f}x")
        if not self._regime_allows_entries(regime):
            lines.append("  ⛔ RISK_OFF — no new entries allowed")
        lines.append("")

        # Pending thesis signals
        pending = self.get_pending_thesis_signals()
        pending_exits = self.get_pending_exit_signals()

        lines.append(f"Pending Entry Signals: {len(pending)}")
        for s in pending:
            sid = s["signal_id"]
            cfg = THESIS_ENTRY.get(sid, {})
            lines.append(f"  ⚠️ {sid:15} {cfg.get('name','?'):25} → {cfg.get('ticker','?')} "
                         f"{cfg.get('direction','?')} | {s.get('check_date','?')}")
        if not pending:
            lines.append("  (none)")

        lines.append(f"\nPending Exit Signals: {len(pending_exits)}")
        for s in pending_exits:
            sid = s["signal_id"]
            cfg = THESIS_EXIT.get(sid, {})
            lines.append(f"  ⚠️ {sid:15} {cfg.get('name','?'):25} → close {cfg.get('ticker','?')}")
        if not pending_exits:
            lines.append("  (none)")

        # Crypto cross-check summary
        qd = load_json(QUANT_PATH)
        ens = qd.get("ensemble", {}).get("signals", {})
        lines.append(f"\nCrypto Cross-Check (quant × intraday):")
        cc_results = {"CONFIRMED": [], "CONFLICT": [], "QUANT_ONLY": [], "INTRADAY_ONLY": []}
        for ticker in ens.keys():
            verdict, _ = self._crypto_cross_check(ticker)
            if verdict != "NONE":
                cc_results[verdict].append(ticker)
        for v, tickers in cc_results.items():
            if tickers:
                lines.append(f"  {v:15} {', '.join(tickers)}")
        if not any(cc_results.values()):
            lines.append("  (no cross-signals firing)")

        # Intraday
        idata = load_json(INTRADAY_PATH)
        lines.append(f"\nIntraday: {len(idata.get('signals',[]))} candidates")
        if not idata.get("signals", []):
            lines.append("  (no tradeable patterns)")

        # Edge gen
        ed = load_json(EDGE_PATH)
        picks = ed.get("top_picks_summary", "")
        lines.append(f"\nEdge Generator: {picks}")

        # Portfolio
        deployed = self.total_deployed()
        equity = self.total_equity()
        pnl_total = float(self.conn.execute(
            "SELECT COALESCE(SUM(pnl_realized),0) FROM trades WHERE status='closed'"
        ).fetchone()[0])
        open_pos = self.open_positions()
        lines.append(f"\nPortfolio: ${deployed:,.0f} deployed | ${equity:,.0f} equity | "
                      f"${pnl_total:+,.0f} realized | {len(open_pos)} open")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    execute = "--execute" in sys.argv
    summary = "--summary" in sys.argv

    engine = UnifiedEngine()

    if summary:
        deployed = engine.total_deployed()
        equity = engine.total_equity()
        pnl = float(engine.conn.execute(
            "SELECT COALESCE(SUM(pnl_realized),0) FROM trades WHERE status='closed'"
        ).fetchone()[0])
        positions = engine.open_positions()
        print(f"📊 Portfolio — {now_ist().strftime('%b %d %H:%M IST')}")
        print(f"Deployed: ${deployed:,.0f} | Equity: ${equity:,.0f} | Realized: ${pnl:+,.0f} | Open: {len(positions)}")
        for p in positions:
            d = "LONG" if p["direction"] == "long" else "SHORT"
            print(f"  {d:5} {p['symbol']:6} {p['shares']:>10.4f} sh @ ${p['entry_price']:,.2f} [{p['entry_signal']}]")
    else:
        output = engine.run(execute=execute)
        if output:
            print(output)

    engine.conn.close()
