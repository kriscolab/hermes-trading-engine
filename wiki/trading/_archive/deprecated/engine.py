#!/usr/bin/env python3
"""
Paper Trader Engine — Commodity Super Cycle Thesis
====================================================
Shared execution engine for all theses. Currently serves the commodity super
cycle thesis (Currie, May 2026) with $100K paper portfolio.

Usage:
    python3 engine.py                  # Check signals, report status
    python3 engine.py --execute        # Check + execute triggered signals
    python3 engine.py --summary        # Portfolio summary only
    python3 engine.py --history        # Trade history

Invoked by:
    - Daily signal check cron (144363e032bf) → --execute
    - Weekly tracker cron (35f039b1f202) → after price fetch
    - Manual: python3 engine.py

State: SQLite journal at paper-trader/journal.db (auto-created)
Schema: see rules.md or AGENTS.md
"""

import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import Enum
from pathlib import Path


# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "journal.db")
TRADING_DIR = os.path.dirname(BASE_DIR)
THESIS_DIR = os.path.join(TRADING_DIR, "theses", "commodity-super-cycle")


# ── Enums ──────────────────────────────────────────────────────────────────

class SignalType(Enum):
    ENTRY = "entry"
    EXIT = "exit"

class TradeStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"  # signal flagged, awaiting execution

class Direction(Enum):
    LONG = "long"
    SHORT = "short"


# ── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class Signal:
    """A trading signal definition."""
    signal_id: str
    name: str
    signal_type: SignalType
    description: str
    trigger_condition: str  # human-readable
    action: str             # human-readable
    allocation_pct: float   # % of portfolio to allocate
    priority: int = 0       # higher = more urgent

@dataclass
class Position:
    """A current or closed position."""
    symbol: str
    direction: Direction
    entry_date: str
    entry_price: float
    shares: float
    entry_signal: str
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_signal: Optional[str] = None
    pnl_realized: float = 0.0

@dataclass
class Portfolio:
    """Paper portfolio state."""
    cash: float = 100_000.0
    positions: List[Position] = field(default_factory=list)
    total_deposits: float = 100_000.0

    @property
    def equity(self) -> float:
        """Total portfolio value (cash + unrealized P&L)."""
        return self.cash  # Simplified: positions valued at entry until closed

    @property
    def allocated_pct(self) -> float:
        """Percentage of portfolio currently deployed."""
        if not self.positions:
            return 0.0
        deployed = sum(p.shares * p.entry_price for p in self.positions
                       if p.exit_date is None)
        return (deployed / self.total_deposits) * 100

    @property
    def realized_pnl(self) -> float:
        return sum(p.pnl_realized for p in self.positions if p.exit_date)


# ── Signal Definitions ────────────────────────────────────────────────────
# Extracted from signals.md. The engine checks these against external data.

ENTRY_SIGNALS: Dict[str, Signal] = {
    "E1": Signal(
        signal_id="E1",
        name="Brent Pullback to Value Zone",
        signal_type=SignalType.ENTRY,
        description="Brent closes below 50-day SMA on weekly close AND Mun7 FCF yield > 12%",
        trigger_condition="brent < brent_50sma AND mun7_fcf_yield > 0.12",
        action="Enter 25% into Mun7 equal-weight basket (XLE proxy)",
        allocation_pct=25.0,
        priority=1,
    ),
    "E2": Signal(
        signal_id="E2",
        name="Brent Breakout Confirmation",
        signal_type=SignalType.ENTRY,
        description="Brent weekly close > $110",
        trigger_condition="brent_close > 110",
        action="Enter 50% into Mun7 basket",
        allocation_pct=50.0,
        priority=2,
    ),
    "E3": Signal(
        signal_id="E3",
        name="Rotation Signal (XLE/XLK Ratio)",
        signal_type=SignalType.ENTRY,
        description="XLE/XLK ratio higher low on weekly OR Energy sector > 4.5% of S&P",
        trigger_condition="xle_xlk_ratio_higher_low OR energy_weight > 0.045",
        action="Enter 25% if not yet fully allocated",
        allocation_pct=25.0,
        priority=3,
    ),
    "E4S": Signal(
        signal_id="E4S",
        name="Gold Tactical Short",
        signal_type=SignalType.ENTRY,
        description="Gold > $3,800 AND DXY rising on weekly",
        trigger_condition="gold > 3800 AND dxy_rising",
        action="Paper-short GLD with 5% of portfolio. Cover at -10% drop or DXY reversal.",
        allocation_pct=5.0,
        priority=4,
    ),
    "E4L": Signal(
        signal_id="E4L",
        name="Gold Structural Long",
        signal_type=SignalType.ENTRY,
        description="Gold drops below $3,000 OR central bank dovish pivot",
        trigger_condition="gold < 3000 OR cb_dovish",
        action="Paper-long GLD with 10% of portfolio. No stop.",
        allocation_pct=10.0,
        priority=5,
    ),
}

EXIT_SIGNALS: Dict[str, Signal] = {
    "X1": Signal(
        signal_id="X1",
        name="Hormuz Reopens",
        signal_type=SignalType.EXIT,
        description="Credible news of Strait of Hormuz reopening",
        trigger_condition="hormuz_reopen_news",
        action="Exit 100% of Mun7 positions within 2 weeks",
        allocation_pct=100.0,
        priority=10,
    ),
    "X2": Signal(
        signal_id="X2",
        name="Mag7 Capex Collapse",
        signal_type=SignalType.EXIT,
        description="Combined Mag7+Oracle quarterly capex drops >30% from $820B run-rate",
        trigger_condition="mag7_capex_drop > 0.30",
        action="Exit 50% immediately, remaining 50% over 4 weeks",
        allocation_pct=50.0,
        priority=9,
    ),
    "X3": Signal(
        signal_id="X3",
        name="Energy Weight Converges",
        signal_type=SignalType.EXIT,
        description="S&P 500 Energy sector weight > 10%",
        trigger_condition="energy_weight > 0.10",
        action="Scale out 25% per percentage point above 10%",
        allocation_pct=25.0,
        priority=7,
    ),
    "X4": Signal(
        signal_id="X4",
        name="Brent Contango",
        signal_type=SignalType.EXIT,
        description="Brent futures curve in contango for 4 consecutive weeks",
        trigger_condition="brent_contango_4w",
        action="Exit 50%",
        allocation_pct=50.0,
        priority=8,
    ),
    "X5": Signal(
        signal_id="X5",
        name="Mun7 FCF Yield Collapse",
        signal_type=SignalType.EXIT,
        description="Mun7 aggregate FCF yield drops below 8%",
        trigger_condition="mun7_fcf_yield < 0.08",
        action="Exit 50%",
        allocation_pct=50.0,
        priority=6,
    ),
}

# ═══════════════════════════════════════════════════════════════════════════
# AI Supercycle Thesis — Aschenbrenner "AGI by 2027"
# ═══════════════════════════════════════════════════════════════════════════

AI_ENTRY_SIGNALS: Dict[str, Signal] = {
    "AI_E1": Signal(
        signal_id="AI_E1",
        name="AI Capex Acceleration",
        signal_type=SignalType.ENTRY,
        description="Mag7 company announces >20% increase in AI capex QoQ",
        trigger_condition="ai_capex_surge",
        action="Enter 25% into AI-BASKET (5 ETFs equal-weight)",
        allocation_pct=25.0,
        priority=1,
    ),
    "AI_E2": Signal(
        signal_id="AI_E2",
        name="Power Deal Announcement",
        signal_type=SignalType.ENTRY,
        description="Major data center power deal >1 GW announced",
        trigger_condition="power_deal_1gw",
        action="Enter 25% overweight DTCR+TAN (electrons layer)",
        allocation_pct=25.0,
        priority=2,
    ),
    "AI_E3": Signal(
        signal_id="AI_E3",
        name="Intel Turnaround Signal",
        signal_type=SignalType.ENTRY,
        description="Intel 18A customer win OR Intel mcap >$200B",
        trigger_condition="intel_turnaround",
        action="Enter 10% into INTC directly",
        allocation_pct=10.0,
        priority=3,
    ),
    "AI_E4": Signal(
        signal_id="AI_E4",
        name="GPU Capacity Milestone",
        signal_type=SignalType.ENTRY,
        description="CoreWeave 100K+ GPU cluster OR CORZ AI revenue > mining",
        trigger_condition="gpu_milestone",
        action="Enter remaining 25% into AI-BASKET",
        allocation_pct=25.0,
        priority=4,
    ),
    "AI_E5": Signal(
        signal_id="AI_E5",
        name="AI Revenue Breakout",
        signal_type=SignalType.ENTRY,
        description="Combined MSFT+GOOGL+AMZN AI revenue >$50B annual run rate",
        trigger_condition="ai_revenue_50b",
        action="Enter 25% if not yet fully allocated",
        allocation_pct=25.0,
        priority=5,
    ),
}

AI_EXIT_SIGNALS: Dict[str, Signal] = {
    "AI_X1": Signal(
        signal_id="AI_X1",
        name="Jevons Paradox — AI Efficiency Breakthrough",
        signal_type=SignalType.EXIT,
        description="Open-source model achieves frontier perf at <10% compute cost",
        trigger_condition="jevons_paradox",
        action="Exit 50% of AI-BASKET immediately",
        allocation_pct=50.0,
        priority=10,
    ),
    "AI_X2": Signal(
        signal_id="AI_X2",
        name="AI Revenue Deceleration",
        signal_type=SignalType.EXIT,
        description="Combined AI revenue growth <30% YoY for 2 quarters",
        trigger_condition="ai_revenue_deceleration",
        action="Exit 50% immediately, remaining over 4 weeks",
        allocation_pct=50.0,
        priority=9,
    ),
    "AI_X3": Signal(
        signal_id="AI_X3",
        name="Power Grid Expansion Accelerates",
        signal_type=SignalType.EXIT,
        description="US data center interconnection queue drops >30% YoY",
        trigger_condition="grid_expansion",
        action="Scale out of DTCR+TAN — 25% per quarter",
        allocation_pct=25.0,
        priority=7,
    ),
    "AI_X4": Signal(
        signal_id="AI_X4",
        name="Aschenbrenner Exits Conviction Stocks",
        signal_type=SignalType.EXIT,
        description="CRWV or BE fully exited from 13F filing",
        trigger_condition="13f_exit_conviction",
        action="Exit AI-BASKET 50%, exit specific stock 100%",
        allocation_pct=50.0,
        priority=8,
    ),
    "AI_X5": Signal(
        signal_id="AI_X5",
        name="GPU Export Controls Tighten",
        signal_type=SignalType.EXIT,
        description="US restricts GPU exports to key markets or >30% tariff",
        trigger_condition="gpu_export_controls",
        action="Exit 50% of AI-BASKET",
        allocation_pct=50.0,
        priority=6,
    ),
}

# AI thesis instrument proxies
AI_ETF_BASKET = ["SOXX", "IGV", "DTCR", "TAN", "XLC"]  # 5 layer ETFs
AI_CONVICTION = ["INTC", "CRWV", "BE", "CORZ"]  # Aschenbrenner's long-term holds
AI_BENCHMARKS = ["SPY", "XLK", "QQQ"]

# ═══════════════════════════════════════════════════════════════════════════
# Crypto Institutional Accumulation Thesis — 6-Layer Confluence
# ═══════════════════════════════════════════════════════════════════════════

CRYPTO_ENTRY_SIGNALS: Dict[str, Signal] = {
    "CRYPTO_E1": Signal(
        signal_id="CRYPTO_E1",
        name="Initial Accumulation Confirmed (3/6 Layers)",
        signal_type=SignalType.ENTRY,
        description="3+ of 6 layers confirm: funding neutral, skew bullish, liquidations one-sided, outflows, reserves down, sentiment calm",
        trigger_condition="crypto_confluence >= 3",
        action="Enter 25% into BTC (60%) + ETH (40%)",
        allocation_pct=25.0,
        priority=1,
    ),
    "CRYPTO_E2": Signal(
        signal_id="CRYPTO_E2",
        name="Accumulation Strengthening (4/6 Layers)",
        signal_type=SignalType.ENTRY,
        description="4+ layers + whale accumulation confirmed over 14 days",
        trigger_condition="crypto_confluence >= 4 AND whale_accumulation",
        action="Add 25% to BTC/ETH positions",
        allocation_pct=25.0,
        priority=2,
    ),
    "CRYPTO_E3": Signal(
        signal_id="CRYPTO_E3",
        name="On-Chain Divergence — Price Down, Flows Up",
        signal_type=SignalType.ENTRY,
        description="BTC -5% in 7d BUT exchange outflows surging, stablecoins rising, funding not panicked",
        trigger_condition="btc_drop_5pct AND exchange_outflow_surge AND stablecoin_rise",
        action="Add 25% — highest-conviction crypto-native signal",
        allocation_pct=25.0,
        priority=3,
    ),
    "CRYPTO_E4": Signal(
        signal_id="CRYPTO_E4",
        name="Breakout with Confluence (5/6 Layers)",
        signal_type=SignalType.ENTRY,
        description="BTC 30d high + OI rising on breakout + volume 2x avg + skew bullish + reserves falling",
        trigger_condition="btc_30d_high AND volume_2x AND oi_rising AND skew_bullish AND reserves_falling",
        action="Enter remaining 25% — breakout confirmed",
        allocation_pct=25.0,
        priority=4,
    ),
}

CRYPTO_EXIT_SIGNALS: Dict[str, Signal] = {
    "CRYPTO_X1": Signal(
        signal_id="CRYPTO_X1",
        name="Exchange Reserves Rising Sharply",
        signal_type=SignalType.EXIT,
        description="BTC exchange reserves increase >5% over 14 days",
        trigger_condition="exchange_reserves_rise_5pct",
        action="Exit 50% immediately",
        allocation_pct=50.0,
        priority=10,
    ),
    "CRYPTO_X2": Signal(
        signal_id="CRYPTO_X2",
        name="Whale Distribution",
        signal_type=SignalType.EXIT,
        description="Top 100 non-exchange wallets decrease >3% over 14 days",
        trigger_condition="whale_distribution",
        action="Exit 50% immediately",
        allocation_pct=50.0,
        priority=9,
    ),
    "CRYPTO_X3": Signal(
        signal_id="CRYPTO_X3",
        name="Derivatives Overheating",
        signal_type=SignalType.EXIT,
        description="Funding >0.05% for 3 consecutive 8h windows AND OI at ATH",
        trigger_condition="funding_overheat",
        action="Exit 25%, re-enter on funding reset",
        allocation_pct=25.0,
        priority=7,
    ),
    "CRYPTO_X4": Signal(
        signal_id="CRYPTO_X4",
        name="BTC Correlation with SPY >0.7",
        signal_type=SignalType.EXIT,
        description="30-day rolling correlation BTC/SPY >0.7 — crypto = levered beta",
        trigger_condition="btc_spy_correlation_high",
        action="Exit 25% — thesis becomes macro, not crypto-native",
        allocation_pct=25.0,
        priority=6,
    ),
    "CRYPTO_X5": Signal(
        signal_id="CRYPTO_X5",
        name="Regulatory Shock",
        signal_type=SignalType.EXIT,
        description="SEC/CFTC enforcement against major exchange or BTC/ETH as security",
        trigger_condition="regulatory_shock",
        action="Exit 100% within 24 hours",
        allocation_pct=100.0,
        priority=10,
    ),
}

# Crypto thesis instruments
CRYPTO_PRIMARY = ["BTC", "ETH"]
CRYPTO_ETF_PROXIES = ["IBIT", "FBTC", "ETHA"]

# ── QUANT SIGNALS (ensemble-driven, non-thesis) ──
# These trade based on quant consensus, not macro thesis.
# Smaller allocation (10%), regime-filtered, MC-gated.
QUANT_INSTRUMENTS = ["IBIT", "ETHA"]
QUANT_ENTRY_SIGNALS: Dict[str, Signal] = {
    "QUANT_E1": Signal("QUANT_E1", "Ensemble Bullish", SignalType.ENTRY,
        "Ensemble > 0.7 BULLISH + MC passed", "Long top ticker at 10%", 10, 1),
    "QUANT_E2": Signal("QUANT_E2", "Ensemble Bearish", SignalType.ENTRY,
        "Ensemble > 0.7 BEARISH + MC passed", "Short top ticker at 10%", 10, 1),
}
QUANT_EXIT_SIGNALS: Dict[str, Signal] = {
    "QUANT_X1": Signal("QUANT_X1", "Ensemble Flipped", SignalType.EXIT,
        "Direction flipped from entry", "Close quant position", 100, 1),
    "QUANT_X2": Signal("QUANT_X2", "Ensemble Weakened", SignalType.EXIT,
        "Score dropped below 0.3", "Close quant position", 100, 2),
}

# ── INTRADAY SIGNALS (short-term TA-driven) ──
INTRADAY_ENTRY_SIGNALS: Dict[str, Signal] = {
    "INTRADAY_LONG": Signal("INTRADAY_LONG", "Intraday Long", SignalType.ENTRY,
        "Pullback to VWAP or breakout above resistance", "Long at 5%, stop -2%, TP +3%", 5, 1),
    "INTRADAY_SHORT": Signal("INTRADAY_SHORT", "Intraday Short", SignalType.ENTRY,
        "Rejection at VWAP or breakdown below support", "Short at 5%, stop -2%, TP +3%", 5, 1),
}
INTRADAY_EXIT_SIGNALS: Dict[str, Signal] = {
    "INTRADAY_X1": Signal("INTRADAY_X1", "Intraday TP Hit", SignalType.EXIT,
        "Take profit reached", "Close intraday position", 100, 1),
    "INTRADAY_X2": Signal("INTRADAY_X2", "Intraday Stop Hit", SignalType.EXIT,
        "Stop loss breached", "Close intraday position", 100, 2),
    "INTRADAY_X3": Signal("INTRADAY_X3", "Intraday Timeout", SignalType.EXIT,
        "Max hold exceeded", "Close intraday position", 100, 3),
}

# ── All signals registry (used by --thesis flag) ──
ALL_SIGNALS = {
    "commodity": (ENTRY_SIGNALS, EXIT_SIGNALS),
    "ai": (AI_ENTRY_SIGNALS, AI_EXIT_SIGNALS),
    "crypto": (CRYPTO_ENTRY_SIGNALS, CRYPTO_EXIT_SIGNALS),
    "quant": (QUANT_ENTRY_SIGNALS, QUANT_EXIT_SIGNALS),
    "intraday": (INTRADAY_ENTRY_SIGNALS, INTRADAY_EXIT_SIGNALS),
}

# Instrument proxies (from thesis instrument map)
MUN7_TICKERS = ["XOM", "CVX", "COP", "SHEL", "TTE", "BP", "EQNR"]
MUN7_PROXY = "XLE"   # Energy Select SPDR — equal-weight proxy when individuals unavailable
MAG7_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
GOLD_PROXY = "GLD"   # SPDR Gold Shares
BRENT_SYMBOL = "BZ=F"  # Yahoo Finance Brent futures


# ── Database ────────────────────────────────────────────────────────────────

class JournalDB:
    """SQLite trade journal. Schema per AGENTS.md."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL CHECK(direction IN ('long', 'short')),
        entry_price REAL NOT NULL,
        shares REAL NOT NULL,
        entry_signal TEXT NOT NULL,
        exit_date TEXT,
        exit_price REAL,
        exit_signal TEXT,
        pnl_realized REAL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed', 'pending')),
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS signal_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        check_date TEXT NOT NULL,
        signal_id TEXT NOT NULL,
        triggered INTEGER NOT NULL DEFAULT 0,
        executed INTEGER NOT NULL DEFAULT 0,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snap_date TEXT NOT NULL,
        cash REAL NOT NULL,
        deployed REAL NOT NULL,
        equity REAL NOT NULL,
        realized_pnl REAL NOT NULL,
        open_positions INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
    CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);
    CREATE INDEX IF NOT EXISTS idx_signal_date ON signal_log(check_date);
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(self.SCHEMA)
        # Migration: add entry_timestamp if missing (v10.9 fix — trade_date was date-only)
        try:
            self.conn.execute("ALTER TABLE trades ADD COLUMN entry_timestamp TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        self.conn.commit()

    def get_open_positions(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE status = 'open' ORDER BY trade_date"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_trades(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM trades ORDER BY trade_date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_closed_trades(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE status = 'closed' ORDER BY exit_date DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def open_position(self, symbol: str, direction: str, entry_price: float,
                      shares: float, entry_signal: str, notes: str = "",
                      thesis_id: str = "") -> int:
        """Open a new position. Returns trade_id."""
        now_ts = datetime.now().isoformat()
        cursor = self.conn.execute(
            """INSERT INTO trades (trade_date, symbol, direction, entry_price,
               shares, entry_signal, status, notes, thesis_id, entry_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
            (datetime.now().strftime("%Y-%m-%d"), symbol, direction,
             entry_price, shares, entry_signal, notes, thesis_id, now_ts)
        )
        self.conn.commit()
        return cursor.lastrowid

    def reduce_position(self, trade_id: int, exit_price: float,
                        exit_pct: float, exit_signal: str, notes: str = "") -> Optional[int]:
        """Reduce a position by a percentage. Returns new trade_id for remaining, or None if fully closed."""
        trade = self.conn.execute(
            "SELECT * FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")
        
        direction = trade["direction"]
        entry_price = trade["entry_price"]
        shares = trade["shares"]
        
        exit_shares = shares * (exit_pct / 100.0)
        remain_shares = shares - exit_shares
        
        # P&L on exited portion
        if direction == "long":
            pnl = (exit_price - entry_price) * exit_shares
        else:
            pnl = (entry_price - exit_price) * exit_shares
        
        if remain_shares <= 0.001:
            # Fully close
            self.conn.execute(
                """UPDATE trades SET exit_date = ?, exit_price = ?, exit_signal = ?,
                   pnl_realized = ?, status = 'closed', notes = notes || ?
                   WHERE id = ?""",
                (datetime.now().strftime("%Y-%m-%d"), exit_price, exit_signal,
                 round(pnl, 2), f"\n{notes}" if notes else "", trade_id)
            )
            self.conn.commit()
            return None
        else:
            # Partial close: close original, open new with remaining shares
            self.conn.execute(
                """UPDATE trades SET exit_date = ?, exit_price = ?, exit_signal = ?,
                   pnl_realized = ?, status = 'closed', notes = notes || ?
                   WHERE id = ?""",
                (datetime.now().strftime("%Y-%m-%d"), exit_price, exit_signal,
                 round(pnl, 2), f"\nPartial exit {exit_pct:.0f}%. {notes}" if notes else f"Partial exit {exit_pct:.0f}%.", trade_id)
            )
            # Open new position for remainder
            now_ts = datetime.now().isoformat()
            cursor = self.conn.execute(
                """INSERT INTO trades (trade_date, symbol, direction, entry_price,
                   shares, entry_signal, status, notes, thesis_id, entry_timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
                (datetime.now().strftime("%Y-%m-%d"), trade["symbol"], direction,
                 entry_price, round(remain_shares, 4), trade["entry_signal"],
                 f"Runner from {exit_signal} — {remain_shares:.4f} shares remaining", trade["thesis_id"], now_ts)
            )
            self.conn.commit()
            return cursor.lastrowid
        
    def close_position(self, trade_id: int, exit_price: float,
                       exit_signal: str, notes: str = "") -> None:
        """Close a position, computing realized P&L."""
        trade = self.conn.execute(
            "SELECT * FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        direction = trade["direction"]
        entry_price = trade["entry_price"]
        shares = trade["shares"]

        if direction == "long":
            pnl = (exit_price - entry_price) * shares
        else:  # short
            pnl = (entry_price - exit_price) * shares

        self.conn.execute(
            """UPDATE trades SET exit_date = ?, exit_price = ?, exit_signal = ?,
               pnl_realized = ?, status = 'closed', notes = notes || ?
               WHERE id = ?""",
            (datetime.now().strftime("%Y-%m-%d"), exit_price, exit_signal,
             round(pnl, 2), f"\n{notes}" if notes else "", trade_id)
        )
        self.conn.commit()

    def log_signal_check(self, signal_id: str, triggered: bool,
                         executed: bool = False, notes: str = "", thesis_id: str = "") -> None:
        self.conn.execute(
            """INSERT INTO signal_log (check_date, signal_id, triggered, executed, notes, thesis_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), signal_id,
             int(triggered), int(executed), notes, thesis_id)
        )
        self.conn.commit()

    def snapshot_portfolio(self, cash: float, deployed: float, equity: float,
                           realized_pnl: float, open_positions: int) -> None:
        self.conn.execute(
            """INSERT INTO portfolio_snapshots
               (snap_date, cash, deployed, equity, realized_pnl, open_positions)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().strftime("%Y-%m-%d"), cash, deployed, equity,
             round(realized_pnl, 2), open_positions)
        )
        self.conn.commit()

    def was_signal_executed(self, signal_id: str, days: int = 30) -> bool:
        """Check if signal already has an OPEN position (idempotency).
        Uses trades table (open positions), not signal_log (which may have stale flags)."""
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE entry_signal = ? AND status = 'open'",
            (signal_id,)
        ).fetchone()
        return row["cnt"] > 0

    def has_open_position(self, symbol: str) -> bool:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE symbol = ? AND status = 'open'",
            (symbol,)
        ).fetchone()
        return row["cnt"] > 0

    def has_open_position_for_symbol_and_signal(self, symbol: str, entry_signal: str) -> bool:
        """Check if there's an open position for a specific symbol+signal combo.
        Used by intraday executor to allow concurrent positions on different tickers."""
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE symbol = ? AND entry_signal = ? AND status = 'open'",
            (symbol, entry_signal)
        ).fetchone()
        return row["cnt"] > 0

    def get_open_positions_for_symbol(self, symbol: str, direction: str = None) -> list:
        """Return open positions for a symbol, optionally filtered by direction."""
        if direction:
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE symbol = ? AND direction = ? AND status = 'open'",
                (symbol, direction)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE symbol = ? AND status = 'open'",
                (symbol,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_total_deployed(self) -> float:
        row = self.conn.execute(
            "SELECT SUM(entry_price * shares) as total FROM trades WHERE status = 'open'"
        ).fetchone()
        return row["total"] or 0.0

    def get_all_signals_recent(self, days: int = 30) -> List[dict]:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT * FROM signal_log WHERE check_date >= ? AND executed = 1",
            (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()


# ── Engine ──────────────────────────────────────────────────────────────────

class PaperTraderEngine:
    """Core execution engine. Checks signals, manages portfolio, logs trades."""

    def __init__(self, db: JournalDB, initial_cash: float = 100_000.0, thesis: str = "commodity"):
        self.db = db
        self.initial_cash = initial_cash
        self.thesis = thesis
        self.entry_sigs, self.exit_sigs = ALL_SIGNALS.get(thesis, (ENTRY_SIGNALS, EXIT_SIGNALS))
        self.alerts: List[str] = []

    # ── Portfolio State ────────────────────────────────────────────────

    def cross_thesis_allocation(self) -> float:
        """
        Returns the max allocation % for this thesis based on total deployed
        across ALL theses. Prevents overallocation beyond 80% of initial capital.
        Returns 0 if already at/above limit.
        """
        total_deployed = self.db.get_total_deployed()
        max_deployed = self.initial_cash * 0.85  # 85% hard cap (bumped from 80% — system matured)
        remaining = max_deployed - total_deployed
        
        if remaining <= 0:
            return 0.0  # At capacity — no more allocation
        
        # Count active theses (with open positions)
        active_theses = set()
        for pos in self.db.get_open_positions():
            sig = pos.get("entry_signal", "")
            if sig.startswith("CRYPTO"):
                active_theses.add("crypto")
            elif sig.startswith("AI"):
                active_theses.add("ai")
            else:
                active_theses.add("commodity")
            
        # Always include current thesis
        active_theses.add(self.thesis)
        count = max(len(active_theses), 1)
        
        # Base split
        base = 1.0 / count
        
        # Scale by remaining capacity
        capacity_ratio = remaining / self.initial_cash
        return min(base, capacity_ratio)

    @property
    def cash(self) -> float:
        deployed = self.db.get_total_deployed()
        closed_trades = self.db.get_closed_trades()
        realized = sum(t["pnl_realized"] for t in closed_trades)
        return self.initial_cash - deployed + realized

    @property
    def deployed(self) -> float:
        return self.db.get_total_deployed()

    @property
    def equity(self) -> float:
        return self.cash + self.deployed

    @property
    def allocated_pct(self) -> float:
        if self.initial_cash == 0:
            return 0.0
        return (self.deployed / self.initial_cash) * 100

    @property
    def open_positions(self) -> List[dict]:
        return self.db.get_open_positions()

    # ── Signal Checking ───────────────────────────────────────────────

    def check_entry_signals(self, market_data: dict) -> List[str]:
        """
        Evaluate entry signals against market data.
        market_data keys vary by thesis:
          commodity: brent_close, brent_50sma, mun7_fcf_yield, ...
          crypto: crypto_confluence, btc_30d_high, volume_2x, ...
          ai: ai_infra_growth, semi_capex, ...
          quant: reads /tmp/quant_signals.json (ensemble data)
        Returns list of triggered signal IDs.
        """
        triggered = []

        # ── INTRADAY THESIS (TA-driven) ─────────────────────────────────
        if self.thesis == "intraday":
            try:
                isd = json.loads(Path("/tmp/intraday_signals.json").read_text())
                for sig in isd.get("signals", []):
                    signal_id = sig.get("signal", "")
                    if signal_id:
                        triggered.append(signal_id)
                        market_data["_intraday_price"] = sig.get("entry_price", 0)
                        market_data["_intraday_ticker"] = sig.get("ticker", "")
            except Exception: pass
            return triggered

        # ── QUANT THESIS (ensemble-driven) ─────────────────────────────
        if self.thesis == "quant":
            try:
                qd = json.loads(Path("/tmp/quant_signals.json").read_text())
                ens = qd.get("ensemble", {}).get("signals", {})
                best_ticker = None; best_score = 0; best_dir = "NEUTRAL"
                for ticker, meta in ens.items():
                    score = abs(meta.get("ensemble_score", 0))
                    if score > best_score:
                        best_score = score; best_ticker = ticker
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
            except Exception: pass
            return triggered

        # ── CRYPTO THESIS ─────────────────────────────────────────────
        if self.thesis == "crypto":
            confluence = market_data.get("crypto_confluence", 0)

            # CRYPTO_E1: 3+ of 6 layers confirm
            if confluence >= 3:
                triggered.append("CRYPTO_E1")

            # CRYPTO_E2: 4+ layers + whale accumulation
            whale = market_data.get("whale_accumulation", False)
            if confluence >= 4 and whale:
                triggered.append("CRYPTO_E2")

            # CRYPTO_E3: BTC drop >5% in 7d + exchange outflows + stablecoin rise
            btc_drop = market_data.get("btc_drop_5pct", False)
            outflow = market_data.get("exchange_outflow_surge", False)
            stable_rise = market_data.get("stablecoin_rise", False)
            if btc_drop and outflow and stable_rise:
                triggered.append("CRYPTO_E3")

            # CRYPTO_E4: BTC 30d high + volume 2x + OI rising + skew bullish + reserves falling
            btc_high = market_data.get("btc_30d_high", False)
            vol_2x = market_data.get("volume_2x", False)
            oi_rising = market_data.get("oi_rising", False)
            skew_bull = market_data.get("skew_bullish", False)
            reserve_fall = market_data.get("reserves_falling", False)
            if btc_high and vol_2x and oi_rising and skew_bull and reserve_fall:
                triggered.append("CRYPTO_E4")

            return triggered

        # ── AI THESIS ──────────────────────────────────────────────────
        if self.thesis == "ai":
            soxx = market_data.get("SOXX", 0)
            igv = market_data.get("IGV", 0)
            dtcr = market_data.get("DTCR", 0)
            tan = market_data.get("TAN", 0)
            corz = market_data.get("CORZ", 0)
            intc = market_data.get("INTC", 0)
            be = market_data.get("BE", 0)

            # AI_E1: SOXX breakout above recent highs (~1s weekly move from current)
            if market_data.get("soxx_trend_strong", soxx > 540):
                triggered.append("AI_E1")

            # AI_E2: Electrons layer outperforming — DTCR + TAN both strong
            if market_data.get("electrons_strong", dtcr > 32 and tan > 67):
                triggered.append("AI_E2")

            # AI_E3: Intel turnaround — needs >1s weekly move above current
            if market_data.get("intel_turnaround", intc > 130):
                triggered.append("AI_E3")

            # AI_E4: Data center buildout — CORZ breakout (~1.2s weekly)
            if market_data.get("datacenter_buildout", corz > 27):
                triggered.append("AI_E4")

            # AI_E5: AI infra cycle confirmed — both SOXX and IGV at highs
            if market_data.get("ai_infra_cycle", soxx > 550 and igv > 105):
                triggered.append("AI_E5")

            return triggered

        # ── COMMODITY THESIS (default) ─────────────────────────────────
        # E1: Brent Pullback
        brent = market_data.get("brent_close", 0)
        brent_sma = market_data.get("brent_50sma")
        if brent_sma is None:
            brent_sma = float("inf")
        fcf = market_data.get("mun7_fcf_yield", 0)
        if brent < brent_sma and fcf > 0.12:
            triggered.append("E1")

        # E2: Brent Breakout
        if brent > 110:
            triggered.append("E2")

        # E3: Rotation
        if market_data.get("xle_xlk_ratio_higher_low", False):
            triggered.append("E3")
        elif market_data.get("energy_weight", 0) > 0.045:
            triggered.append("E3")

        # E4S: Gold Tactical Short
        if market_data.get("gold", 0) > 3800 and market_data.get("dxy_rising", False):
            triggered.append("E4S")

        # E4L: Gold Structural Long
        if market_data.get("gold", float("inf")) < 3000 or market_data.get("cb_dovish", False):
            triggered.append("E4L")

        return triggered

    def check_exit_signals(self, market_data: dict) -> List[str]:
        """
        Evaluate exit signals.
        market_data keys vary by thesis.
        """
        triggered = []

        # ── CRYPTO THESIS ─────────────────────────────────────────────
        if self.thesis == "crypto":
            # CRYPTO_X1: Exchange reserves rising >5% over 14 days
            if market_data.get("exchange_reserves_rise_5pct", False):
                triggered.append("CRYPTO_X1")

            # CRYPTO_X2: Whale distribution (top 100 wallets decrease >3%)
            if market_data.get("whale_distribution", False):
                triggered.append("CRYPTO_X2")

            # CRYPTO_X3: Derivatives overheating
            if market_data.get("derivatives_overheating", False):
                triggered.append("CRYPTO_X3")

            # CRYPTO_X4: BTC/SPY correlation >0.7
            if market_data.get("btc_spy_corr_high", False):
                triggered.append("CRYPTO_X4")

            # CRYPTO_X5: Regulatory risk
            if market_data.get("crypto_regulatory_risk", False):
                triggered.append("CRYPTO_X5")

            return triggered

        # ── AI THESIS ──────────────────────────────────────────────────
        if self.thesis == "ai":
            if market_data.get("jevons_paradox", False):
                triggered.append("AI_X1")
            if market_data.get("ai_revenue_deceleration", False):
                triggered.append("AI_X2")
            if market_data.get("grid_expansion", False):
                triggered.append("AI_X3")
            if market_data.get("13f_exit_conviction", False):
                triggered.append("AI_X4")
            if market_data.get("gpu_export_controls", False):
                triggered.append("AI_X5")
            return triggered

        # ── COMMODITY THESIS (default) ─────────────────────────────────
        if self.thesis not in ("crypto", "ai", "intraday", "quant"):
            if market_data.get("hormuz_reopen_news", False):
                triggered.append("X1")
            if market_data.get("mag7_capex_drop", 0) > 0.30:
                triggered.append("X2")
            if market_data.get("energy_weight", 0) > 0.10:
                triggered.append("X3")
            if market_data.get("brent_contango_4w", False):
                triggered.append("X4")
            if market_data.get("mun7_fcf_yield", 1.0) < 0.08:
                triggered.append("X5")
            return triggered

        # ── INTRADAY THESIS ─────────────────────────────────────────────
        if self.thesis == "intraday":
            from datetime import datetime as dt
            positions = self.db.get_open_positions()
            for pos in positions:
                if not pos["entry_signal"] or not pos["entry_signal"].startswith("INTRADAY_"):
                    continue
                sym = pos["symbol"]
                entry = pos["entry_price"]
                try:
                    import json as _json
                    cp = _json.loads(Path("/tmp/crypto_module_data.json").read_text())
                    prices = cp.get("prices", {})
                    live = prices.get(sym.lower(), entry)
                except Exception:
                    live = entry
                
                pnl_pct = ((live - entry) / entry) if pos["direction"] == "long" else ((entry - live) / entry)
                
                if pnl_pct >= 0.03:
                    triggered.append("INTRADAY_X1")
                    market_data["_intraday_price"] = live
                    market_data["_intraday_ticker"] = sym
                elif pnl_pct <= -0.02:
                    triggered.append("INTRADAY_X2")
                    market_data["_intraday_price"] = live
                    market_data["_intraday_ticker"] = sym
                try:
                    # Use entry_timestamp (ISO) if available, fallback to trade_date (date-only)
                    ts = pos.get("entry_timestamp")
                    if ts:
                        entered = dt.fromisoformat(ts)
                    else:
                        entered = dt.strptime(pos["trade_date"], "%Y-%m-%d")
                    hours_open = (dt.now() - entered).total_seconds() / 3600
                    if hours_open > 4:
                        triggered.append("INTRADAY_X3")
                        market_data["_intraday_price"] = live
                        market_data["_intraday_ticker"] = sym
                except Exception:
                    pass
            return triggered

        # ── QUANT THESIS ────────────────────────────────────────────────
        if self.thesis == "quant":
            try:
                import json as _json
                qd = _json.loads(Path("/tmp/quant_signals.json").read_text())
                ens = qd.get("ensemble", {}).get("signals", {})
                # Only check QUANT positions (not commodity/crypto/AI/intraday)
                for pos in self.db.get_open_positions():
                    if not pos["entry_signal"] or not pos["entry_signal"].startswith("QUANT_E"):
                        continue
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

    # ── Execution ─────────────────────────────────────────────────────

    def execute_entry(self, signal_id: str, price: float,
                      notes: str = "", market_data: dict = None) -> Optional[int]:
        """Execute an entry signal. Returns trade_id or None."""
        signal = self.entry_sigs.get(signal_id)
        if not signal:
            self.alerts.append(f"⚠ Unknown entry signal: {signal_id}")
            return None

        # Idempotency check
        # INTRADAY: check per-ticker (multiple intraday positions on different tickers
        # can coexist — only block if same ticker already has an open intraday position)
        if signal_id.startswith("INTRADAY_"):
            ticker = (market_data or {}).get("_intraday_ticker", "")
            sym = "IBIT" if ticker == "BTC" else ("ETHA" if ticker == "ETH" else ticker)
            if sym and self.db.has_open_position_for_symbol_and_signal(sym, signal_id):
                self.alerts.append(f"⏭ {signal_id} on {sym} already open — skipping duplicate")
                return None
        elif self.db.was_signal_executed(signal_id):
            self.alerts.append(f"⏭ {signal_id} already executed in last 30 days — skipping")
            return None

        allocation = self.initial_cash * (signal.allocation_pct / 100) * self.cross_thesis_allocation()

        # ── OPPOSITE-POSITION GUARD ──────────────────────────────────
        # If entering LONG, close any existing SHORT on same symbol family
        # If entering SHORT, close any existing LONG on same symbol family
        new_dir = "long"  # default direction
        symbol = None  # will be set per signal branch
        # Determine target symbol and direction early for guard check
        if signal_id in ("E1", "E2", "E3"):
            symbol = MUN7_PROXY; new_dir = "long"
        elif signal_id == "E4S":
            symbol = GOLD_PROXY; new_dir = "short"
        elif signal_id == "E4L":
            symbol = GOLD_PROXY; new_dir = "long"
        elif signal_id.startswith("CRYPTO_E"):
            # Crypto entries are always long — close any shorts
            for sym in ["IBIT", "ETHA"]:
                conflicting = self.db.get_open_positions_for_symbol(sym, "short")
                for pos in conflicting:
                    self.db.close_position(pos["id"], price, signal_id,
                                          f"Closed conflicting short before long entry [{signal_id}]")
                    self.alerts.append(f"🔴 Closed conflicting {sym} short position before {signal_id}")
        elif signal_id.startswith("AI_E"):
            # AI uses 5 ETFs — check each
            for etf in ["SOXX", "IGV", "DTCR", "TAN", "XLC"]:
                conflicting = self.db.get_open_positions_for_symbol(etf, "short")
                for pos in conflicting:
                    etf_px = (market_data or {}).get(etf, price * 0.5)
                    self.db.close_position(pos["id"], etf_px, signal_id,
                                          f"Closed conflicting {etf} short before AI long entry [{signal_id}]")
                    self.alerts.append(f"🔴 Closed conflicting {etf} short position before {signal_id}")
        else:
            # Commodity exit signal IDs (X1-X5) don't enter, they exit
            pass
        
        # Now check/close opposite on the primary symbol for commodity signals
        if symbol and symbol in (MUN7_PROXY, GOLD_PROXY):
            opposite = "short" if new_dir == "long" else "long"
            conflicting = self.db.get_open_positions_for_symbol(symbol, opposite)
            for pos in conflicting:
                self.db.close_position(pos["id"], price, signal_id,
                                      f"Closed conflicting {opposite} before {new_dir} entry [{signal_id}]")
                self.alerts.append(f"🔴 Closed conflicting {symbol} {opposite} position before {signal_id}")
        # ── END GUARD ────────────────────────────────────────────────

        # Check if we already have positions from this signal family
        if signal_id in ("E1", "E2", "E3"):
            if self.db.has_open_position(MUN7_PROXY):
                # Partial entry already exists — calculate remaining
                existing_deployed = self.db.get_total_deployed()
                target_deployed = self.initial_cash * (
                    signal.allocation_pct / 100
                )
                allocation = max(0, target_deployed - existing_deployed)
                if allocation <= 0:
                    self.alerts.append(
                        f"⏭ {signal_id}: already at or above target allocation"
                    )
                    return None
                notes += f" | Add-on: deployed ${allocation:,.0f} on top of existing"

            symbol = MUN7_PROXY
            direction = "long"
            shares = allocation / price if price > 0 else 0
            if shares <= 0:
                self.alerts.append(f"⚠ {signal_id}: zero shares computed (price={price})")
                return None

            trade_id = self.db.open_position(
                symbol=symbol, direction=direction, entry_price=price,
                shares=round(shares, 2), entry_signal=signal_id,
                notes=notes, thesis_id=self.thesis
            )

            self.alerts.append(
                f"✅ {signal.name}: Entered {symbol} — "
                f"{shares:.2f} shares @ ${price:,.2f} "
                f"(${allocation:,.0f} deployed, {signal.allocation_pct:.0f}% allocation)"
            )
            return trade_id

        elif signal_id == "E4S":
            # Gold tactical short
            symbol = GOLD_PROXY
            direction = "short"
            shares = allocation / price if price > 0 else 0
            trade_id = self.db.open_position(
                symbol=symbol, direction=direction, entry_price=price,
                shares=round(shares, 2), entry_signal=signal_id,
                notes=f"Tactical short. Cover at -10% or DXY reversal. {notes}",
                thesis_id=self.thesis
            )
            self.alerts.append(
                f"✅ {signal.name}: Shorted {symbol} — "
                f"{shares:.2f} shares @ ${price:,.2f}"
            )
            return trade_id

        elif signal_id == "E4L":
            symbol = GOLD_PROXY
            direction = "long"
            shares = allocation / price if price > 0 else 0
            trade_id = self.db.open_position(
                symbol=symbol, direction=direction, entry_price=price,
                shares=round(shares, 2), entry_signal=signal_id,
                notes=f"Structural long. No stop. {notes}",
                thesis_id=self.thesis
            )
            self.alerts.append(
                f"✅ {signal.name}: Long {symbol} — "
                f"{shares:.2f} shares @ ${price:,.2f}"
            )
            return trade_id

        # ── INTRADAY THESIS ───────────────────────────────────────────
        elif signal_id.startswith("INTRADAY_"):
            ticker = (market_data or {}).get("_intraday_ticker", "BTC")
            is_long = "LONG" in signal_id
            sym = "IBIT" if ticker == "BTC" else ("ETHA" if ticker == "ETH" else ticker)
            direction = "long" if is_long else "short"
            entry = (market_data or {}).get("_intraday_price", price)
            alloc = self.initial_cash * 0.05
            shares = alloc / entry if entry > 0 else 0
            if shares <= 0: return None
            trade_id = self.db.open_position(
                symbol=sym, direction=direction, entry_price=entry,
                shares=round(shares, 2), entry_signal=signal_id,
                notes=f"Intraday {signal_id}: {ticker} {direction} @ ${entry:,.2f}, stop -2%, TP +3%",
                thesis_id=self.thesis)
            self.alerts.append(f"⚡ {signal.name}: {direction.upper()} {sym} ({ticker}) {shares:.2f} @ ${entry:,.2f}")
            return trade_id

        # ── QUANT THESIS ───────────────────────────────────────────────
        elif signal_id.startswith("QUANT_E"):
            ticker = (market_data or {}).get("_quant_ticker", "BTC")
            is_bullish = signal_id == "QUANT_E1"
            
            # Use crypto spot prices for BTC/ETH
            if ticker == "BTC":
                sym = "IBIT"
                # Read spot from quant_signals
                try:
                    qd = json.loads(Path("/tmp/quant_signals.json").read_text())
                    spot = qd.get("signals", {}).get(ticker, {}).get("mean-reversion", {}).get("close", 0)
                    if not spot:
                        qd2 = json.loads(Path("/tmp/crypto_module_data.json").read_text())
                        spot = qd2.get("prices", {}).get("btc", price)
                except Exception:
                    spot = price
            elif ticker == "ETH":
                sym = "ETHA"
                try:
                    qd = json.loads(Path("/tmp/crypto_module_data.json").read_text())
                    spot = qd.get("prices", {}).get("eth", price)
                except Exception:
                    spot = price
            else:
                sym = ticker
                spot = price
            
            direction = "long" if is_bullish else "short"
            
            # ── Edge-generator confirmation gate ──
            edge_path = Path("/tmp/edge_generator.json")
            if edge_path.exists():
                try:
                    import json as _json
                    eg = _json.loads(edge_path.read_text())
                    for rec in eg.get("recommendations", []):
                        if rec.get("ticker") == ticker:
                            eg_rec = rec.get("recommendation", "WAIT")
                            eg_score = rec.get("unified_score", 0)
                            if direction == "long" and eg_rec in ("SELL",):
                                self.alerts.append(
                                    f"⚠ BLOCKED {signal_id}: edge-gen says {eg_rec} (score={eg_score})")
                                return None
                            if direction == "short" and eg_rec in ("BUY",):
                                self.alerts.append(
                                    f"⚠ BLOCKED {signal_id}: edge-gen says {eg_rec} (score={eg_score})")
                                return None
                            break
                except Exception:
                    pass
            
            quant_alloc = self.initial_cash * 0.10 * self.cross_thesis_allocation()
            # Floor: minimum 3% allocation regardless of cap (same pattern as intraday's fixed 5%)
            if quant_alloc < self.initial_cash * 0.03:
                quant_alloc = self.initial_cash * 0.03
            shares = quant_alloc / spot if spot > 0 else 0
            
            if shares <= 0: return None
            
            trade_id = self.db.open_position(
                symbol=sym, direction=direction, entry_price=spot,
                shares=round(shares, 2), entry_signal=signal_id,
                notes=f"Quant {signal_id}: {ticker} {direction} @ ${spot:,.2f}, ensemble={market_data.get('_quant_score',0):.2f}",
                thesis_id=self.thesis)
            self.alerts.append(f"🤖 {signal.name}: {direction.upper()} {sym} ({ticker}) {shares:.2f} @ ${spot:,.2f}")
            return trade_id

        # ── CRYPTO THESIS ─────────────────────────────────────────────
        elif signal_id.startswith("CRYPTO_E"):
            btc_price = price  # passed from daily_check
            eth_price = btc_price * 0.027  # approximate ETH/BTC ratio

            crypto_alloc = self.initial_cash * (signal.allocation_pct / 100) * self.cross_thesis_allocation()
            btc_alloc = crypto_alloc * 0.60
            eth_alloc = crypto_alloc * 0.40

            # BTC leg (IBIT proxy)
            if btc_price > 0:
                btc_shares = btc_alloc / btc_price
                self.db.open_position(
                    symbol="IBIT", direction="long", entry_price=btc_price,
                    shares=round(btc_shares, 2), entry_signal=signal_id,
                    notes=f"Crypto thesis {signal_id}: BTC 60% leg. {notes}",
                    thesis_id=self.thesis
                )
                self.alerts.append(
                    f"✅ {signal.name}: IBIT (BTC) {btc_shares:.2f} sh @ ${btc_price:,.2f}"
                )

            # ETH leg (ETHA proxy)
            if eth_price > 0:
                eth_shares = eth_alloc / eth_price
                self.db.open_position(
                    symbol="ETHA", direction="long", entry_price=eth_price,
                    shares=round(eth_shares, 2), entry_signal=signal_id,
                    notes=f"Crypto thesis {signal_id}: ETH 40% leg. {notes}",
                    thesis_id=self.thesis
                )
                self.alerts.append(
                    f"✅ {signal.name}: ETHA (ETH) {eth_shares:.2f} sh @ ${eth_price:,.2f}"
                )

            return 1  # non-None = success

        # ── AI THESIS ──────────────────────────────────────────────────
        elif signal_id.startswith("AI_E"):
            ai_etfs = ["SOXX", "IGV", "DTCR", "TAN", "XLC"]
            ai_alloc = self.initial_cash * (signal.allocation_pct / 100) * self.cross_thesis_allocation()
            per_etf = ai_alloc / len(ai_etfs)

            executed_count = 0
            for etf in ai_etfs:
                etf_price = (market_data or {}).get(etf, price * 0.5)
                if etf_price > 0:
                    shares = per_etf / etf_price
                    self.db.open_position(
                        symbol=etf, direction="long", entry_price=etf_price,
                        shares=round(shares, 2), entry_signal=signal_id,
                        notes=f"AI thesis {signal_id}: {etf} leg. {notes}",
                        thesis_id=self.thesis
                    )
                    executed_count += 1
                    self.alerts.append(
                        f"✅ {signal.name}: {etf} {shares:.2f} sh @ ${etf_price:.2f}"
                    )

            if executed_count > 0:
                return 1

        return None

    def execute_exit(self, signal_id: str, exit_price: float,
                     notes: str = "") -> List[int]:
        """Execute an exit signal. Returns list of closed trade_ids."""
        signal = self.exit_sigs.get(signal_id)
        if not signal:
            self.alerts.append(f"⚠ Unknown exit signal: {signal_id}")
            return []

        closed = []
        open_positions = self.db.get_open_positions()

        if signal_id == "X1":
            # Exit 100% of Mun7
            for pos in open_positions:
                if pos["symbol"] == MUN7_PROXY and pos["direction"] == "long":
                    self.db.close_position(
                        pos["id"], exit_price, signal_id,
                        f"Hormuz reopens — thesis invalidation. {notes}"
                    )
                    closed.append(pos["id"])
                    self.alerts.append(
                        f"🔴 {signal.name}: CLOSED {pos['symbol']} "
                        f"{pos['shares']} shares @ ${exit_price:,.2f} "
                        f"P&L: ${(exit_price - pos['entry_price']) * pos['shares']:,.2f}"
                    )

        elif signal_id == "X2":
            # Exit 50% immediately
            mun7_positions = [p for p in open_positions
                            if p["symbol"] == MUN7_PROXY and p["direction"] == "long"]
            for pos in mun7_positions[:max(1, len(mun7_positions) // 2)]:
                self.db.close_position(pos["id"], exit_price, signal_id, notes)
                closed.append(pos["id"])
                self.alerts.append(
                    f"🔴 {signal.name}: CLOSED {pos['symbol']} (50% reduction)"
                )

        elif signal_id in ("X3", "X4", "X5"):
            # Scale-out: close portion of Mun7
            mun7_positions = [p for p in open_positions
                            if p["symbol"] == MUN7_PROXY and p["direction"] == "long"]
            pct = signal.allocation_pct / 100
            to_close = max(1, int(len(mun7_positions) * pct))
            for pos in mun7_positions[:to_close]:
                self.db.close_position(pos["id"], exit_price, signal_id, notes)
                closed.append(pos["id"])
                self.alerts.append(
                    f"🔴 {signal.name}: CLOSED {pos['symbol']} "
                    f"P&L: ${(exit_price - pos['entry_price']) * pos['shares']:,.2f}"
                )

        # ── CRYPTO EXITS ─────────────────────────────────────────────
        elif signal_id.startswith("CRYPTO_X"):
            # Close crypto thesis positions ONLY (filter by entry_signal prefix)
            # NOT quant/intraday positions on the same symbols
            crypto_symbols = ("IBIT", "ETHA", "FBTC")
            for pos in open_positions:
                if pos["symbol"] in crypto_symbols and pos["entry_signal"] and pos["entry_signal"].startswith("CRYPTO_E"):
                    pnl = (exit_price - pos["entry_price"]) * pos["shares"] if pos["direction"] == "long" else (pos["entry_price"] - exit_price) * pos["shares"]
                    self.db.close_position(pos["id"], exit_price, signal_id,
                                          f"Crypto exit {signal_id}: {notes}")
                    closed.append(pos["id"])
                    self.alerts.append(
                        f"🔴 {signal.name}: CLOSED {pos['symbol']} "
                        f"{pos['shares']} shares @ ${exit_price:,.2f} "
                        f"P&L: ${pnl:,.2f}"
                    )

            if not closed:
                self.alerts.append(f"⚠ {signal_id}: No crypto positions to close")

        # ── AI EXITS ─────────────────────────────────────────────────
        elif signal_id.startswith("AI_X"):
            # Close AI thesis positions only (filter by entry_signal prefix)
            for pos in open_positions:
                if pos["entry_signal"] and pos["entry_signal"].startswith("AI_E"):
                    pnl = (exit_price - pos["entry_price"]) * pos["shares"] if pos["direction"] == "long" else (pos["entry_price"] - exit_price) * pos["shares"]
                    self.db.close_position(pos["id"], exit_price, signal_id,
                                          f"AI exit {signal_id}: {notes}")
                    closed.append(pos["id"])
                    self.alerts.append(
                        f"{'🟢' if pnl > 0 else '🔴'} {signal.name}: CLOSED {pos['symbol']} "
                        f"{pos['shares']} shares @ ${exit_price:,.2f} "
                        f"P&L: ${pnl:,.2f}"
                    )
            if not closed:
                self.alerts.append(f"⚠ {signal_id}: No AI positions to close")

        # ── QUANT EXITS ──────────────────────────────────────────────
        elif signal_id.startswith("QUANT_X"):
            # Close all quant thesis positions (IBIT/ETHA)
            for pos in open_positions:
                if pos["entry_signal"] and pos["entry_signal"].startswith("QUANT_E"):
                    pnl = (exit_price - pos["entry_price"]) * pos["shares"] if pos["direction"] == "long" else (pos["entry_price"] - exit_price) * pos["shares"]
                    self.db.close_position(pos["id"], exit_price, signal_id,
                                          f"Quant exit {signal_id}: {notes}")
                    closed.append(pos["id"])
                    self.alerts.append(
                        f"{'🟢' if pnl > 0 else '🔴'} {signal.name}: CLOSED {pos['symbol']} "
                        f"{pos['shares']} shares @ ${exit_price:,.2f} "
                        f"P&L: ${pnl:,.2f}"
                    )
            if not closed:
                self.alerts.append(f"⚠ {signal_id}: No quant positions to close")

        # ── INTRADAY EXITS ───────────────────────────────────────────
        elif signal_id.startswith("INTRADAY_X"):
            # Only close the specific timed-out ticker, not all intraday positions
            # check_exit_signals sets _intraday_ticker to the symbol that triggered
            target_symbol = notes.strip() if notes else ""
            for pos in open_positions:
                if pos["entry_signal"] and pos["entry_signal"].startswith("INTRADAY_"):
                    if target_symbol and pos["symbol"] != target_symbol:
                        continue  # not the position that triggered this exit
                    pnl = (exit_price - pos["entry_price"]) * pos["shares"] if pos["direction"] == "long" else (pos["entry_price"] - exit_price) * pos["shares"]
                    self.db.close_position(pos["id"], exit_price, signal_id,
                                          f"Intraday exit {signal_id}: {notes}")
                    closed.append(pos["id"])
                    self.alerts.append(
                        f"{'🟢' if pnl > 0 else '🔴'} {signal.name}: CLOSED {pos['symbol']} "
                        f"{pos['shares']} shares @ ${exit_price:,.2f} "
                        f"P&L: ${pnl:,.2f}"
                    )
            if not closed:
                self.alerts.append(f"⚠ {signal_id}: No intraday positions to close")

        return closed

    # ── Daily Check ───────────────────────────────────────────────────

    def daily_check(self, market_data: dict, execute: bool = False) -> str:
        """
        Run the daily signal check. Returns a summary string suitable for
        Telegram delivery.

        If execute=True, also executes any triggered signals.
        """
        self.alerts = []
        lines = []
        tag = getattr(self, 'thesis', 'commodity').upper()
        lines.append(f"[{tag}] #signal-check")
        lines.append("")

        # Entry signals
        entry_hits = self.check_entry_signals(market_data)
        exit_hits = self.check_exit_signals(market_data)

        # Status report
        lines.append("**Entry Signals:**")
        for sig_id, sig in self.entry_sigs.items():
            status = "🔴 FIRING" if sig_id in entry_hits else "🟢 idle"
            already_done = self.db.was_signal_executed(sig_id)
            if already_done:
                status = "✅ done"
            lines.append(f"  {status} | {sig_id} — {sig.name}")

        lines.append("")
        lines.append("**Exit Signals:**")
        for sig_id, sig in self.exit_sigs.items():
            status = "🔴 FIRING" if sig_id in exit_hits else "🟢 idle"
            lines.append(f"  {status} | {sig_id} — {sig.name}")

        lines.append("")
        lines.append(f"💰 Cash: ${self.cash:,.0f} | Deployed: ${self.deployed:,.0f} "
                     f"({self.allocated_pct:.1f}%) | Equity: ${self.equity:,.0f}")

        open_pos = self.open_positions
        if open_pos:
            lines.append("")
            lines.append("**Open Positions:**")
            for pos in open_pos:
                direction = "🟢 LONG" if pos["direction"] == "long" else "🔴 SHORT"
                lines.append(
                    f"  {direction} {pos['symbol']}: {pos['shares']} shares "
                    f"@ ${pos['entry_price']:,.2f} ({pos['entry_signal']})"
                )

        # Snapshot portfolio every check
        self.db.snapshot_portfolio(
            cash=self.cash, deployed=self.deployed, equity=self.equity,
            realized_pnl=sum(t["pnl_realized"] for t in self.db.get_closed_trades(limit=1000)),
            open_positions=len(self.open_positions)
        )

        # Track which signals executed in this run
        executed_this_run = set()

        # Execute if requested
        if execute:
            lines.append("")
            lines.append("─── Execution ───")
            executed_any = False

            # Exit first (preserve capital)
            intraday_ticker = ""  # initialized for INTRADAY_X exit path
            for sig_id in exit_hits:
                if sig_id.startswith("CRYPTO_X"):
                    price = market_data.get("btc", market_data.get("IBIT", 76000))
                elif sig_id.startswith("AI_X"):
                    price = market_data.get("SOXX", 200)
                elif sig_id.startswith("INTRADAY_X"):
                    price = market_data.get("_intraday_price", 0)
                    intraday_ticker = market_data.get("_intraday_ticker", "")
                elif sig_id.startswith("QUANT_X"):
                    price = market_data.get("btc", market_data.get("IBIT", 76000))
                else:
                    price = market_data.get("mun7_price", market_data.get("xle_price", 100))
                closed = self.execute_exit(sig_id, price,
                    notes=intraday_ticker if sig_id.startswith("INTRADAY_X") else "")
                if closed:
                    executed_any = True
                    executed_this_run.add(sig_id)

            # Then entries
            for sig_id in entry_hits:
                if sig_id in ("E1", "E2", "E3"):
                    price = market_data.get("mun7_price", market_data.get("xle_price", 100))
                elif sig_id in ("E4S", "E4L"):
                    price = market_data.get("gold", 3500)
                elif sig_id.startswith("CRYPTO_E"):
                    price = market_data.get("btc", market_data.get("IBIT", 76000))
                elif sig_id.startswith("AI_E"):
                    price = market_data.get("SOXX", 200)
                elif sig_id.startswith("INTRADAY_"):
                    price = 0  # execute_entry reads _intraday_price from market_data
                elif sig_id.startswith("QUANT_E"):
                    price = 0  # execute_entry reads _quant_price from market_data
                else:
                    continue
                trade_id = self.execute_entry(sig_id, price, market_data=market_data)
                if trade_id:
                    executed_any = True
                    executed_this_run.add(sig_id)

            if not executed_any:
                lines.append("  No signals executed (all already active or skipped)")

            for alert in self.alerts:
                lines.append(alert)

        # Log signal checks AFTER execution (single entry per signal)
        for sig_id in self.entry_sigs:
            triggered = sig_id in entry_hits
            was_executed = sig_id in executed_this_run
            self.db.log_signal_check(sig_id, triggered, was_executed,
                                     "Firing" if triggered else "Not triggered",
                                     thesis_id=self.thesis)
        for sig_id in self.exit_sigs:
            triggered = sig_id in exit_hits
            was_executed = sig_id in executed_this_run
            self.db.log_signal_check(sig_id, triggered, was_executed,
                                     "Firing" if triggered else "Not triggered",
                                     thesis_id=self.thesis)

        return "\n".join(lines)

    # ── Summary ───────────────────────────────────────────────────────

    def unrealized_pnl(self, prices: dict = None) -> float:
        """Compute unrealized P&L given current prices."""
        if not prices:
            return 0.0
        total = 0.0
        for pos in self.open_positions:
            current = prices.get(pos["symbol"])
            if current is None:
                continue
            if pos["direction"] == "long":
                total += (current - pos["entry_price"]) * pos["shares"]
            else:  # short
                total += (pos["entry_price"] - current) * pos["shares"]
        return total

    def portfolio_summary(self, prices: dict = None) -> str:
        """Human-readable portfolio summary with optional mark-to-market."""
        lines = []
        tag = getattr(self, 'thesis', 'commodity').upper()
        lines.append(f"[{tag}] #portfolio-summary")
        lines.append("")

        unrealized = self.unrealized_pnl(prices) if prices else 0.0
        total_equity = self.equity + unrealized

        lines.append(f"💰 Cash:           ${self.cash:>12,.2f}")
        lines.append(f"📊 Deployed:       ${self.deployed:>12,.2f} ({self.allocated_pct:.1f}%)")

        closed = self.db.get_closed_trades(limit=1000)
        realized = sum(t["pnl_realized"] for t in closed)
        lines.append(f"💵 Realized P&L:   ${realized:>12,.2f}")

        upnl_str = f"+${unrealized:,.2f}" if unrealized >= 0 else f"-${abs(unrealized):,.2f}"
        lines.append(f"📉 Unrealized P&L: {upnl_str:>12}")
        lines.append(f"📈 Equity:         ${total_equity:>12,.2f}")

        open_pos = self.open_positions
        lines.append(f"📋 Open Positions:  {len(open_pos)}")
        for pos in open_pos:
            direction = "LONG " if pos["direction"] == "long" else "SHORT"
            entry = pos["entry_price"]
            shares = pos["shares"]
            line = f"   {direction} {pos['symbol']:5s} {shares:>8.2f} shares @ ${entry:>10,.2f}"

            if prices:
                current = prices.get(pos["symbol"])
                if current:
                    if pos["direction"] == "long":
                        pos_pnl = (current - entry) * shares
                    else:
                        pos_pnl = (entry - current) * shares
                    change_pct = ((current - entry) / entry * 100)
                    if pos["direction"] == "short":
                        change_pct = -change_pct
                    arrow = "↑" if pos_pnl >= 0 else "↓"
                    pnl_str = f"+${pos_pnl:,.2f}" if pos_pnl >= 0 else f"-${abs(pos_pnl):,.2f}"
                    line += f" → ${current:,.2f} ({arrow} {pnl_str}, {change_pct:+.1f}%)"

            line += f"  [{pos['entry_signal']}]"
            lines.append(line)

        if closed:
            lines.append("")
            lines.append("**Recent Closed Trades:**")
            for t in closed[-10:]:
                pnl_str = f"+${t['pnl_realized']:,.2f}" if t['pnl_realized'] >= 0 else f"-${abs(t['pnl_realized']):,.2f}"
                lines.append(
                    f"   {t['symbol']:5s} {t['entry_signal']:4s} → {t['exit_signal'] or '?':4s}  "
                    f"{pnl_str}"
                )

        return "\n".join(lines)

    # ── Confluence Analyzer ──────────────────────────────────────────────

    def analyze_confluence(self, market_data: dict) -> str:
        """
        Cross-layer confluence analysis for fired signals.

        For each fired signal, checks adjacent data layers for confirmation
        or contradiction. Returns a Telegram-ready recommendation report.

        Layers used (commodity thesis):
          - Macro: DXY direction, rate regime, risk sentiment
          - Cross-asset: equity/bond correlation, VIX, sector flows
          - Fundamental: FCF yields, earnings trajectory
          - Sentiment: Fear & Greed, positioning extremes
        """
        entry_hits = self.check_entry_signals(market_data)
        exit_hits = self.check_exit_signals(market_data)
        all_hits = entry_hits + exit_hits

        if not all_hits:
            return None  # No signals, no confluence to analyze

        lines = []
        lines.append("[SIGNAL] #confluence-analysis")
        lines.append("")

        for sig_id in all_hits:
            sig = self.entry_sigs.get(sig_id) or self.exit_sigs.get(sig_id)
            if not sig:
                continue

            checks = []
            confidence = "NEUTRAL"

            # ── Macro Context (applies to all signals) ──
            dxy = market_data.get("dxy", 100)
            dxy_rising = market_data.get("dxy_rising", False)
            dxy_falling = market_data.get("dxy_falling", False)
            dxy_direction = "rising" if dxy_rising else ("falling" if dxy_falling else "flat")
            vix = market_data.get("vix", 20)

            if dxy_direction == "falling":
                checks.append(("✅", "DXY falling — USD weakness supports commodities"))
            elif dxy_direction == "rising":
                checks.append(("⚠️", f"DXY rising ({dxy}) — headwind for commodities/gold"))

            if vix > 25:
                checks.append(("⚠️", f"VIX elevated ({vix}) — risk-off, reduce size"))
            elif vix < 15:
                checks.append(("✅", "VIX low — calm markets, conviction entries favored"))

            # ── Signal-specific confluence ──

            if sig_id == "E1":  # Brent Pullback
                # Check: is the pullback macro-driven or structural?
                brent = market_data.get("brent_close", 0)
                brent_sma = market_data.get("brent_50sma", float("inf"))
                spread = ((brent - brent_sma) / brent_sma) * 100

                if dxy_direction == "falling":
                    checks.append(("✅", "DXY falling + Brent pullback = USD-driven, not structural. Good entry."))
                elif dxy_direction == "rising" and spread < -3:
                    checks.append(("🔴", "DXY rising + Brent deep below SMA = macro pressure. Wait for DXY reversal before entering."))

                # Check FCF yield trend
                fcf = market_data.get("mun7_fcf_yield", 0)
                if fcf > 0.15:
                    checks.append(("✅", f"Mun7 FCF yield strong ({fcf*100:.1f}%) — fundamental floor intact"))
                elif fcf < 0.10:
                    checks.append(("🔴", f"FCF yield weakening ({fcf*100:.1f}%) — value case eroding"))

            elif sig_id == "E2":  # Brent Breakout
                # Check: is volume confirming?
                volume_surge = market_data.get("brent_volume_surge", False)
                if volume_surge:
                    checks.append(("✅", "Breakout on volume surge — genuine demand"))
                else:
                    checks.append(("⚠️", "Volume data unavailable — verify with XLE volume"))

                # Check: is contango forming?
                if market_data.get("brent_contango_4w", False):
                    checks.append(("🔴", "Brent contango forming — breakout may be short squeeze, not structural"))

            elif sig_id == "E3":  # Rotation Signal
                energy_weight = market_data.get("energy_weight", 0)
                xle_vs_xlk = market_data.get("xle_xlk_ratio", 0)

                if energy_weight > 0.045:
                    checks.append(("✅", f"Energy weight rising ({energy_weight*100:.1f}%) — rotation underway"))
                if xle_vs_xlk > 0.35:
                    checks.append(("✅", f"XLE/XLK ratio strong ({xle_vs_xlk:.3f}) — energy outperforming tech"))

            elif sig_id == "E4S":  # Gold Tactical Short
                gold = market_data.get("gold", 0)
                real_rates = market_data.get("real_rates", "unknown")

                if dxy_direction == "rising" and gold > 3800:
                    checks.append(("✅", f"DXY {dxy:.2f} rising + Gold ${gold:,.0f} extended — short confluence confirmed"))
                else:
                    checks.append(("⚠️", "DXY signal mixed — verify with real rates"))

                if real_rates == "rising":
                    checks.append(("✅", "Real rates rising — gold headwind confirmed"))
                elif real_rates == "falling":
                    checks.append(("🔴", "Real rates falling — contradicts gold short thesis"))

            elif sig_id == "E4L":  # Gold Structural Long
                if market_data.get("cb_dovish", False):
                    checks.append(("✅", "Central bank dovish pivot — gold long thesis confirmed"))
                if market_data.get("gold", float("inf")) < 3000:
                    checks.append(("✅", "Gold below $3,000 — structural value zone"))

            elif sig_id in ("X1", "X2", "X3", "X4", "X5"):
                # Exit signals — all high priority when triggered
                checks.append(("🔴", "THESIS INVALIDATION — confluence analysis bypassed. Exit takes priority."))

            # ── Score confidence ──
            confirms = sum(1 for icon, _ in checks if icon == "✅")
            warns = sum(1 for icon, _ in checks if icon == "⚠️")
            contradicts = sum(1 for icon, _ in checks if icon == "🔴")

            if contradicts > 0:
                confidence = "🔴 LOW — contradictions present"
            elif warns > confirms:
                confidence = "🟡 MIXED — proceed with reduced size"
            elif confirms >= 2:
                confidence = "🟢 HIGH — multiple layers confirm"
            elif confirms >= 1:
                confidence = "🟡 MODERATE — one layer confirms"
            else:
                confidence = "⚪ INSUFFICIENT DATA"

            # ── Output signal block ──
            lines.append(f"### {sig_id} — {sig.name}")
            lines.append(f"**Signal:** {sig.description}")
            lines.append(f"**Confidence:** {confidence}")
            lines.append("")
            for icon, msg in checks:
                lines.append(f"  {icon} {msg}")
            lines.append("")

            # ── Recommendation ──
            if sig_id in self.entry_sigs and contradicts == 0:
                already_executed = self.db.was_signal_executed(sig_id)
                if already_executed:
                    lines.append(f"  💡 **Recommendation:** Already executed. Hold. {sig.action}")
                elif confidence.startswith("🟢"):
                    allocation = sig.allocation_pct
                    lines.append(f"  🎯 **Recommendation: EXECUTE at {allocation:.0f}% allocation.** {sig.action}")
                elif confidence.startswith("🟡"):
                    lines.append(f"  💡 **Recommendation: WATCH.** Wait for one more confirmation layer. {sig.action}")
                else:
                    lines.append(f"  ⏸ **Recommendation: WAIT.** Contradictions present. Re-evaluate next check.")
            elif sig_id in self.entry_sigs:
                lines.append(f"  🚫 **Recommendation: SKIP.** Contradictions detected. Do not enter.")
            elif sig_id in self.exit_sigs:
                lines.append(f"  🔴 **Recommendation: EXECUTE EXIT.** {sig.action}")

            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def trade_history(self, limit: int = 20) -> str:
        """Trade history output."""
        trades = self.db.get_all_trades(limit=limit)
        lines = ["[COMMODITY] #trade-history", ""]
        for t in trades:
            status_icon = "🟢" if t["status"] == "open" else "⚫"
            pnl = f" P&L: ${t['pnl_realized']:,.2f}" if t["pnl_realized"] else ""
            lines.append(
                f"{status_icon} {t['trade_date']} | {t['symbol']} {t['direction']} | "
                f"Entry: ${t['entry_price']:,.2f} x {t['shares']} | "
                f"Signal: {t['entry_signal']}{pnl}"
            )
        return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Paper Trader Engine")
    parser.add_argument("--execute", action="store_true",
                        help="Execute triggered signals (default: check only)")
    parser.add_argument("--summary", action="store_true",
                        help="Show portfolio summary")
    parser.add_argument("--history", action="store_true",
                        help="Show trade history")
    parser.add_argument("--recommend", action="store_true",
                        help="Run confluence analysis and output trade recommendations")
    parser.add_argument("--data", type=str, default=None,
                        help="JSON file with market data for signal checking")
    parser.add_argument("--prices", type=str, default=None,
                        help="JSON string of current prices, e.g. '{\"GLD\": 417.29, \"XLE\": 59.44}'")
    parser.add_argument("--thesis", type=str, default="commodity",
                        choices=["commodity", "ai", "crypto", "quant", "intraday"],
                        help="Thesis to operate on (default: commodity)")
    args = parser.parse_args()

    db = JournalDB()
    engine = PaperTraderEngine(db, thesis=args.thesis)

    # Parse current prices for mark-to-market
    current_prices = None
    if args.prices:
        try:
            current_prices = json.loads(args.prices)
        except json.JSONDecodeError:
            print(f"⚠ Invalid --prices JSON: {args.prices}", file=sys.stderr)

    if args.summary:
        print(engine.portfolio_summary(prices=current_prices))
        db.close()
        return

    if args.history:
        print(engine.trade_history())
        db.close()
        return

    # Load market data
    market_data = {}
    if args.data and os.path.exists(args.data):
        with open(args.data) as f:
            market_data = json.load(f)

    if args.recommend:
        confluence = engine.analyze_confluence(market_data)
        if confluence:
            print(confluence)
        else:
            print("[SIGNAL] #confluence-analysis\n\nNo signals firing — no confluence to analyze.")
        db.close()
        return

    # Run daily check
    output = engine.daily_check(market_data, execute=args.execute)
    print(output)
    db.close()


if __name__ == "__main__":
    main()
