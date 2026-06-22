#!/usr/bin/env python3
"""Engine Base — shared engine framework for v12 3-engine architecture.

Provides: DB helpers, portfolio state, regime integration, signal execution,
capital tracking, journal management.

Usage (in engine files):
    from engines.base import EngineBase
    class CommodityEngine(EngineBase): ...
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

IST = timezone(timedelta(hours=5, minutes=30))

TRADING_DIR = Path(__file__).resolve().parent.parent
SYNTH_PATH = TRADING_DIR / "synthesis" / "daily_state.json"
PRICES_PATH = Path("/tmp/portfolio_prices.json")
CRYPTO_PATH = Path("/tmp/crypto_module_data.json")


def now_ist():
    return datetime.now(IST)


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def get_live_price(symbol: str) -> float:
    """Get live price from portfolio prices, crypto data, or HL universe."""
    s = symbol.upper()
    
    # 1. Try HL universe (most current — mark prices from Hyperliquid oracle)
    hl_path = Path("/tmp/hl_universe.json")
    if hl_path.exists():
        try:
            uni = json.loads(hl_path.read_text())
            for asset in uni.get("native", []):
                if asset["name"].upper() == s:
                    px = asset.get("markPx", 0)
                    if px > 0: return float(px)
            for asset in uni.get("hip3", []):
                if asset["name"].upper() == s:
                    px = asset.get("markPx", 0)
                    if px > 0: return float(px)
        except: pass
    
    # 2. Try portfolio prices or crypto data
    for pfile in [PRICES_PATH, CRYPTO_PATH]:
        if pfile.exists():
            try:
                data = json.loads(pfile.read_text())
                if s in data: return float(data[s])
                if symbol.lower() in data.get("prices", {}):
                    return float(data["prices"][symbol.lower()])
            except: pass
    return 0.0


class EngineBase:
    """Shared engine framework. Each thesis gets its own subclass."""

    # Override these in subclasses
    ENGINE_NAME: str = "base"
    JOURNAL_DB: str = "journal_base.db"
    TOTAL_CAPITAL: float = 100_000.0
    HARD_CAP_PCT: float = 0.80

    # Entry/exit signal definitions — subclasses define these
    THESIS_ENTRY: dict = {}  # {signal_id: {thesis, name, ticker, direction, allocation_pct}}
    THESIS_EXIT: dict = {}   # {signal_id: {thesis, name, ticker}}

    # Schedule: when does this engine run?
    CHECK_WINDOW: Optional[Tuple[int, int]] = None  # (start_hour_ist, end_hour_ist) or None for always

    def __init__(self, execute_mode: bool = False, summary_mode: bool = False):
        self.execute_mode = execute_mode
        self.summary_mode = summary_mode
        self.alerts: List[str] = []
        self.trades_today: List[str] = []

        # Connect to own journal
        journal_path = TRADING_DIR / "paper-trader" / self.JOURNAL_DB
        self.conn = sqlite3.connect(str(journal_path))
        self.conn.row_factory = sqlite3.Row

        # ── Fix #2: Read daily_state.json at startup ──
        self.regime = self._load_regime()

        # ── Read meta-optimizer params if available ──
        params_path = Path(f"/tmp/{self.ENGINE_NAME}_params.json")
        self.meta_params = load_json(params_path).get("params", {})

    # ═══════════════════════════════════════════════════════════════
    # REGIME INTEGRATION (Fix #2)
    # ═══════════════════════════════════════════════════════════════

    def _load_regime(self) -> dict:
        """Read synthesizer daily_state.json. Sets per-thesis regime and sizing."""
        state = load_json(SYNTH_PATH)
        if not state:
            return {"regime": "NEUTRAL", f"{self.ENGINE_NAME}_size": 1.0}

        regime = state.get("regime", "NEUTRAL")
        thesis_bias = state.get(f"{self.ENGINE_NAME}_bias", "NEUTRAL")

        # Map synthesizer bias → size multiplier
        bias_mult = {"BULLISH": 1.0, "NEUTRAL": 1.0, "BEARISH": 0.5}
        thesis_size = bias_mult.get(thesis_bias, 1.0)

        return {
            "regime": regime,
            "thesis_bias": thesis_bias,
            "size_multiplier": self._regime_size_multiplier(regime, thesis_size),
            "allow_entries": regime != "RISK_OFF",
        }

    def _regime_size_multiplier(self, regime: str, thesis_size: float) -> float:
        base = {"RISK_ON": 1.0, "TRENDING": 1.0, "NEUTRAL": 1.0,
                "CAUTIOUS": 0.5, "RISK_OFF": 0.0}.get(regime, 1.0)
        return base * thesis_size

    # ═══════════════════════════════════════════════════════════════
    # DB HELPERS
    # ═══════════════════════════════════════════════════════════════

    def open_position(self, symbol, direction, entry_price, shares, entry_signal, thesis_id=None):
        """Open a new position. Returns trade_id."""
        t = now_ist()
        tid = thesis_id or self.ENGINE_NAME
        cursor = self.conn.execute(
            """INSERT INTO trades (trade_date, symbol, direction, entry_price, shares,
               entry_signal, status, entry_timestamp, thesis_id)
               VALUES (?,?,?,?,?,?,'open',?,?)""",
            (t.strftime("%Y-%m-%d"), symbol, direction, entry_price,
             round(shares, 6), entry_signal, t.isoformat(), tid),
        )
        self.conn.commit()
        return cursor.lastrowid

    def close_position(self, trade_id, exit_price, exit_signal, notes=""):
        """Close a position. Returns (pnl, symbol, direction)."""
        trade = self.conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if not trade:
            return None

        direction = trade["direction"]
        entry_price = trade["entry_price"]
        shares = trade["shares"]
        pnl = ((exit_price - entry_price) * shares if direction == "long"
               else (entry_price - exit_price) * shares)
        pnl = round(pnl, 2)

        t = now_ist()
        self.conn.execute(
            """UPDATE trades SET exit_date=?, exit_price=?, exit_signal=?,
               pnl_realized=?, status='closed', notes=? WHERE id=?""",
            (t.strftime("%Y-%m-%d"), exit_price, exit_signal, pnl, notes or "", trade_id),
        )
        self.conn.commit()
        return pnl, trade["symbol"], trade["direction"]

    def has_open_signal(self, entry_signal, symbol=None):
        """Check if there's already an open position for this signal."""
        if symbol:
            r = self.conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE entry_signal=? AND symbol=? AND status='open'",
                (entry_signal, symbol),
            ).fetchone()
        else:
            r = self.conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE entry_signal=? AND status='open'",
                (entry_signal,),
            ).fetchone()
        return r["c"] > 0

    def log_signal(self, signal_id, triggered, thesis_id=None):
        """Write to signal_log."""
        t = now_ist().strftime("%Y-%m-%d %H:%M")
        tid = thesis_id or self.ENGINE_NAME
        self.conn.execute(
            "INSERT INTO signal_log (check_date, signal_id, triggered, thesis_id) VALUES (?,?,?,?)",
            (t, signal_id, 1 if triggered else 0, tid),
        )
        self.conn.commit()

    def mark_executed(self, signal_id):
        self.conn.execute(
            "UPDATE signal_log SET executed=1, notes='executed by v12 engine' "
            "WHERE signal_id=? AND triggered=1 AND executed=0",
            (signal_id,),
        )
        self.conn.commit()

    # ═══════════════════════════════════════════════════════════════
    # PORTFOLIO STATE
    # ═══════════════════════════════════════════════════════════════

    def total_deployed(self) -> float:
        r = self.conn.execute(
            "SELECT COALESCE(SUM(shares * entry_price), 0) FROM trades WHERE status='open'"
        ).fetchone()
        return float(r[0])

    def total_equity(self) -> float:
        deployed = self.total_deployed()
        closed_pnl = self.conn.execute(
            "SELECT COALESCE(SUM(pnl_realized), 0) FROM trades WHERE status='closed'"
        ).fetchone()
        return self.TOTAL_CAPITAL - deployed + float(closed_pnl[0])

    def open_positions(self) -> list:
        return [dict(r) for r in self.conn.execute(
            "SELECT id, symbol, direction, entry_price, shares, entry_signal, trade_date, thesis_id, entry_timestamp "
            "FROM trades WHERE status='open'"
        ).fetchall()]

    def closed_trades(self, days=7) -> list:
        cutoff = (now_ist() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM trades WHERE status='closed' AND exit_date >= ? ORDER BY exit_date",
            (cutoff,),
        ).fetchall()]

    def capital_remaining(self) -> float:
        cap = self.TOTAL_CAPITAL * self.HARD_CAP_PCT
        return cap - self.total_deployed()

    # ═══════════════════════════════════════════════════════════════
    # SIGNAL EXECUTION
    # ═══════════════════════════════════════════════════════════════

    def _in_check_window(self) -> bool:
        """Is this engine's check window active? None = always."""
        if self.CHECK_WINDOW is None:
            return True
        h = now_ist().hour
        start, end = self.CHECK_WINDOW
        return start <= h < end

    def execute_entries(self) -> List[str]:
        """Execute thesis entry signals that were TRIGGERED but not executed.
        
        Reads signal_log for triggered=1, executed=0 entries.
        Does NOT blindly open positions for all defined signals.
        """
        outputs = []
        if not self._in_check_window():
            return outputs
        if not self.regime.get("allow_entries", True):
            return outputs

        size_mult = self.regime.get("size_multiplier", 1.0)

        # Get triggered-but-unexecuted entry signals from signal_log
        today = now_ist().strftime("%Y-%m-%d")
        triggered_signals = self.conn.execute(
            "SELECT signal_id, thesis_id FROM signal_log "
            "WHERE triggered=1 AND executed=0 AND check_date LIKE ? "
            "AND signal_id NOT LIKE '%EXIT%'",
            (f"{today}%",)
        ).fetchall()

        for row in triggered_signals:
            sid = row["signal_id"]
            if sid not in self.THESIS_ENTRY:
                continue

            cfg = self.THESIS_ENTRY[sid]
            ticker = cfg["ticker"]
            direction = cfg["direction"]
            alloc_pct = cfg["allocation_pct"]
            thesis = cfg.get("thesis", self.ENGINE_NAME)

            # Guard: already open?
            if self.has_open_signal(sid, ticker):
                continue

            # Guard: opposite position?
            opp = "short" if direction == "long" else "long"
            r = self.conn.execute(
                "SELECT COUNT(*) as c FROM trades WHERE symbol=? AND direction=? AND status='open'",
                (ticker, opp),
            ).fetchone()
            if r["c"] > 0:
                self.alerts.append(f"⚠️ {sid}: opposite position open on {ticker} — skipped")
                continue

            # Position sizing
            position_value = self.TOTAL_CAPITAL * (alloc_pct / 100.0) * size_mult

            # Hard cap check
            if self.total_deployed() + position_value > self.TOTAL_CAPITAL * self.HARD_CAP_PCT:
                continue

            price = get_live_price(ticker)
            if price <= 0:
                continue

            shares = position_value / price
            trade_id = self.open_position(ticker, direction, price, shares, sid, thesis)
            self.log_signal(sid, True, thesis)
            self.mark_executed(sid)

            msg = f"✅ {sid} ({cfg['name']}): {direction} {ticker} @ ${price:.2f} × {shares:.2f} = ${position_value:,.0f}"
            outputs.append(msg)
            self.trades_today.append(msg)

        return outputs

    def execute_exits(self) -> List[str]:
        """Execute pending exit signals. ONE position per exit signal."""
        outputs = []
        open_pos = self.open_positions()

        for sid, cfg in self.THESIS_EXIT.items():
            ticker = cfg["ticker"]

            # Find ONE open position on this ticker to close
            for pos in open_pos:
                if pos["symbol"] != ticker or pos.get("status") != "open":
                    continue

                price = get_live_price(ticker)
                if price <= 0:
                    continue

                result = self.close_position(pos["id"], price, sid)
                if result:
                    pnl, sym, direction = result
                    self.log_signal(sid, True)
                    msg = f"❌ {sid} ({cfg['name']}): CLOSED {direction} {sym} @ ${price:.2f} | P&L=${pnl:,.2f}"
                    outputs.append(msg)
                    self.trades_today.append(msg)
                    break  # One position per exit signal

        return outputs

    # ═══════════════════════════════════════════════════════════════
    # SNAPSHOT
    # ═══════════════════════════════════════════════════════════════

    def take_snapshot(self):
        t = now_ist().strftime("%Y-%m-%d %H:%M")
        deployed = self.total_deployed()
        equity = self.total_equity()
        realized = self.conn.execute(
            "SELECT COALESCE(SUM(pnl_realized), 0) FROM trades WHERE status='closed'"
        ).fetchone()[0]
        open_count = len(self.open_positions())

        self.conn.execute(
            "INSERT INTO portfolio_snapshots (snap_date, cash, deployed, equity, realized_pnl, open_positions, thesis_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (t, self.TOTAL_CAPITAL - deployed, deployed, equity, realized, open_count, self.ENGINE_NAME),
        )
        self.conn.commit()

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════

    def summary(self) -> str:
        """One-line portfolio summary."""
        open_pos = self.open_positions()
        deployed = self.total_deployed()
        equity = self.total_equity()
        closed = self.closed_trades(days=7)
        realized_7d = sum(t["pnl_realized"] for t in closed)
        cap_pct = (deployed / self.TOTAL_CAPITAL * 100) if self.TOTAL_CAPITAL > 0 else 0
        return (f"[{self.ENGINE_NAME.upper()}] ${equity:,.0f} equity | "
                f"${deployed:,.0f} deployed ({cap_pct:.0f}%) | "
                f"{len(open_pos)} open | 7d P&L ${realized_7d:,.2f}")

    def run(self) -> List[str]:
        """Run one engine tick. Returns list of trade messages.
        In summary mode: report only, no execution."""
        if self.summary_mode:
            return []

        outputs = []
        outputs.extend(self.execute_exits())
        outputs.extend(self.execute_entries())
        self.take_snapshot()
        if self.alerts:
            outputs.extend(self.alerts)
        return outputs

    def close(self):
        self.conn.close()
