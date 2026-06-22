#!/usr/bin/env python3
"""Phase 1: Database Isolation — Migration Script.
Creates 3 per-engine journals, migrates data, builds UNION VIEW.
"""

import sqlite3
import shutil
import os
from datetime import datetime

BASE = "/home/hermes-pilot/vault/wiki/trading/paper-trader"
SRC_DB = os.path.join(BASE, "journal.db")
BACKUP_DB = os.path.join(BASE, f"journal_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

COMMODITY_DB = os.path.join(BASE, "journal_commodity.db")
AI_DB = os.path.join(BASE, "journal_ai.db")
CRYPTO_DB = os.path.join(BASE, "journal_crypto.db")

# ── Backup original ──
print(f"BACKUP: {SRC_DB} → {BACKUP_DB}")
shutil.copy2(SRC_DB, BACKUP_DB)

# ── Schema (same as original for trades/signal_log/snapshots, plus crypto extras) ──
TRADES_DDL = """CREATE TABLE trades (
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
    notes TEXT,
    thesis_id TEXT DEFAULT "commodity",
    entry_timestamp TEXT
)"""

SIGNAL_DDL = """CREATE TABLE signal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_date TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    triggered INTEGER NOT NULL DEFAULT 0,
    executed INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    thesis_id TEXT DEFAULT "commodity"
)"""

SNAPSHOT_DDL = """CREATE TABLE portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snap_date TEXT NOT NULL,
    cash REAL NOT NULL,
    deployed REAL NOT NULL,
    equity REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    open_positions INTEGER NOT NULL,
    thesis_id TEXT DEFAULT "commodity"
)"""

# Crypto-only extra tables
QUANT_WEIGHTS_DDL = """CREATE TABLE quant_module_weights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    regime TEXT NOT NULL,
    module_name TEXT NOT NULL,
    weight REAL NOT NULL,
    sharpe_30d REAL,
    win_rate_30d REAL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active','suspended','graduating'))
)"""

EXECUTION_QUALITY_DDL = """CREATE TABLE execution_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    expected_price REAL NOT NULL,
    actual_price REAL NOT NULL,
    slippage_bps REAL,
    fill_time_ms INTEGER,
    regime TEXT,
    FOREIGN KEY(trade_id) REFERENCES trades(id)
)"""

RISK_EVENTS_DDL = """CREATE TABLE risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT,
    positions_closed INTEGER DEFAULT 0
)"""

# ── Create databases ──
for db_path, name in [(COMMODITY_DB, "commodity"), (AI_DB, "ai"), (CRYPTO_DB, "crypto")]:
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(TRADES_DDL)
    conn.execute(SIGNAL_DDL)
    conn.execute(SNAPSHOT_DDL)
    if name == "crypto":
        conn.execute(QUANT_WEIGHTS_DDL)
        conn.execute(EXECUTION_QUALITY_DDL)
        conn.execute(RISK_EVENTS_DDL)
    conn.commit()
    conn.close()
    print(f"CREATED: {db_path}")

# ── Migrate data ──
src = sqlite3.connect(SRC_DB)
src.row_factory = sqlite3.Row

# Migration plan:
#   commodity → journal_commodity.db (2 trades, 1 open)
#   ai        → journal_ai.db      (5 trades, all open)
#   crypto    → LIQUIDATED, mark with notes (2 trades)
#   intraday  → journal_crypto.db  (21 trades, all closed)
#   quant     → journal_crypto.db  (1 trade, closed)

THESIS_MAP = {
    "commodity": COMMODITY_DB,
    "ai": AI_DB,
    "crypto": CRYPTO_DB,
    "intraday": CRYPTO_DB,
    "quant": CRYPTO_DB,
}

LIQUIDATION_NOTE = "LIQUIDATED 2026-06-01: Entry price contaminated (BTC/ETH spot stored as ETF price). P&L was fiction. Clean start for v12."

for thesis, db_path in THESIS_MAP.items():
    dest = sqlite3.connect(db_path)
    
    # Trades
    rows = src.execute("SELECT * FROM trades WHERE thesis_id=?", (thesis,)).fetchall()
    for row in rows:
        d = dict(row)
        if thesis == "crypto" and d["status"] == "open":
            # Liquidate contaminated positions
            d["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d["exit_price"] = d["entry_price"]  # mark at entry (P&L = 0, clean slate)
            d["exit_signal"] = "v12_LIQUIDATION"
            d["status"] = "closed"
            d["notes"] = LIQUIDATION_NOTE
            d["pnl_realized"] = 0.0
        cols = ",".join(d.keys())
        placeholders = ",".join(["?" for _ in d])
        dest.execute(f"INSERT INTO trades ({cols}) VALUES ({placeholders})", list(d.values()))
    
    # Signal log
    sig_rows = src.execute("SELECT * FROM signal_log WHERE thesis_id=?", (thesis,)).fetchall()
    for row in sig_rows:
        d = dict(row)
        cols = ",".join(d.keys())
        placeholders = ",".join(["?" for _ in d])
        dest.execute(f"INSERT INTO signal_log ({cols}) VALUES ({placeholders})", list(d.values()))
    
    # Portfolio snapshots
    snap_rows = src.execute("SELECT * FROM portfolio_snapshots WHERE thesis_id=?", (thesis,)).fetchall()
    for row in snap_rows:
        d = dict(row)
        cols = ",".join(d.keys())
        placeholders = ",".join(["?" for _ in d])
        dest.execute(f"INSERT INTO portfolio_snapshots ({cols}) VALUES ({placeholders})", list(d.values()))
    
    dest.commit()
    dest.close()
    print(f"MIGRATED: {thesis} → {db_path}")

src.close()

# ── Verify ──
print("\n=== VERIFICATION ===")
for name, db_path in [("commodity", COMMODITY_DB), ("ai", AI_DB), ("crypto", CRYPTO_DB)]:
    conn = sqlite3.connect(db_path)
    trades = conn.execute("SELECT count(*), sum(CASE WHEN status='open' THEN 1 ELSE 0 END) FROM trades").fetchone()
    sigs = conn.execute("SELECT count(*) FROM signal_log").fetchone()
    snaps = conn.execute("SELECT count(*) FROM portfolio_snapshots").fetchone()
    print(f"{name}: {trades[0]} trades ({trades[1]} open), {sigs[0]} signals, {snaps[0]} snapshots")
    conn.close()

# ── Show crypto liquidation ──
conn = sqlite3.connect(CRYPTO_DB)
for row in conn.execute("SELECT symbol, direction, entry_price, status, notes FROM trades WHERE thesis_id='crypto'"):
    print(f"  LIQUIDATED: {row[0]} {row[1]} @ {row[2]} → {row[3]}")
conn.close()

print("\nPhase 1 migration complete.")
