#!/usr/bin/env python3
"""
Signal Fidelity Monitor — Phase 2 Trust Layer
===============================================
Watches signal_log for execution gaps: signals that fire (triggered=1) but
never execute (executed=0). Catches missing-handler bugs like QUANT_X2 that
ran silently for 3 days before being discovered.

Also monitors for stale open positions — quant/intraday positions open beyond
their expected lifetime, indicating a broken exit path.

Run: python3 signal-fidelity-monitor.py
Cron schedule: every 4 hours
Alert target: Telegram DM (only when issues found — silent otherwise)

Design:
  - Reads signal_log and trades from journal.db directly
  - No dependencies on engine.py (decoupled — engine can be broken, monitor still works)
  - Exit code 0 on clean, 1 on warnings, 2 on critical
  - Output: clean plaintext for cron→Telegram delivery
"""

import sqlite3
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional

# ── Config ────────────────────────────────────────────────────────────────
DB_PATH = os.path.expanduser("~/vault/wiki/trading/paper-trader/journal.db")
IST = timezone(timedelta(hours=5, minutes=30))

# How far back to query signal_log (hours)
SIGNAL_WINDOW_HOURS = 6

# How many times a signal can fire without execution before it's a problem
# (Allows for first 1-2 polls before human-cron runs with --execute)
MAX_UNEXECUTED_FIRES = 3

# Max hours a quant or intraday position can stay open without an exit signal
MAX_QUANT_HOLD_HOURS = 72   # 3 days — quant positions should resolve faster
MAX_INTRADAY_HOLD_HOURS = 8  # Intraday positions should close within hours

# ── Database ───────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


# ── Check 1: Triggered But Not Executed ──────────────────────────────────

def check_triggered_unexecuted(db: sqlite3.Connection) -> List[dict]:
    """
    Find signals that fire repeatedly without ever executing.
    This is the QUANT_X2 pattern: check_signals appends to exit_hits,
    execute_exit has no handler → triggered=1, executed=0.
    """
    cutoff = (datetime.now(IST) - timedelta(hours=SIGNAL_WINDOW_HOURS)).strftime(
        "%Y-%m-%d %H:%M")
    
    rows = db.execute("""
        SELECT signal_id, thesis_id,
               SUM(triggered) as fire_count,
               MAX(CASE WHEN executed=1 THEN 1 ELSE 0 END) as ever_executed,
               MAX(check_date) as last_fire,
               MIN(check_date) as first_fire
        FROM signal_log
        WHERE check_date > ? AND triggered = 1
        GROUP BY signal_id, thesis_id
        HAVING SUM(triggered) >= ? AND MAX(CASE WHEN executed=1 THEN 1 ELSE 0 END) = 0
        ORDER BY fire_count DESC
    """, (cutoff, MAX_UNEXECUTED_FIRES)).fetchall()
    
    return [dict(r) for r in rows]


# ── Check 2: Stale Open Positions ────────────────────────────────────────

def check_stale_positions(db: sqlite3.Connection) -> List[dict]:
    """
    Find quant/intraday positions that have been open beyond their expected
    lifetime without any exit signal firing.
    """
    now = datetime.now(IST)
    rows = db.execute("""
        SELECT id, symbol, direction, entry_price, entry_signal, thesis_id,
               entry_timestamp, trade_date
        FROM trades
        WHERE status = 'open'
          AND (entry_signal LIKE 'QUANT_%' OR entry_signal LIKE 'INTRADAY_%')
        ORDER BY entry_timestamp ASC
    """).fetchall()
    
    stale = []
    for r in rows:
        d = dict(r)
        # Determine entry time
        ts_str = d.get("entry_timestamp")
        if ts_str:
            try:
                entry_time = datetime.fromisoformat(ts_str)
            except Exception:
                entry_time = datetime.strptime(d["trade_date"], "%Y-%m-%d")
        else:
            entry_time = datetime.strptime(d["trade_date"], "%Y-%m-%d")
        
        # Ensure entry_time is offset-naive for comparison
        if entry_time.tzinfo is not None:
            entry_time = entry_time.replace(tzinfo=None)
        
        hours_open = (now.replace(tzinfo=None) - entry_time).total_seconds() / 3600
        
        is_intraday = d["entry_signal"].startswith("INTRADAY_")
        max_hours = MAX_INTRADAY_HOLD_HOURS if is_intraday else MAX_QUANT_HOLD_HOURS
        
        if hours_open > max_hours:
            d["hours_open"] = round(hours_open, 1)
            d["max_hours"] = max_hours
            d["type"] = "intraday" if is_intraday else "quant"
            stale.append(d)
    
    return stale


# ── Check 3: Cross-Thesis Contamination ──────────────────────────────────

def check_cross_thesis_contamination(db: sqlite3.Connection) -> List[dict]:
    """
    Check for positions on same symbol opened by different theses that
    could be accidentally closed by a wrong-thesis exit handler.
    
    This catches the CRYPTO_X closing-QUANT-IBIT problem we fixed.
    Still useful as a watchdog in case it regresses.
    """
    rows = db.execute("""
        SELECT symbol, thesis_id, COUNT(*) as cnt,
               GROUP_CONCAT(DISTINCT entry_signal) as signals
        FROM trades
        WHERE status = 'open'
        GROUP BY symbol
        HAVING COUNT(DISTINCT thesis_id) > 1
    """).fetchall()
    
    return [dict(r) for r in rows]


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    if not os.path.exists(DB_PATH):
        print("MONITOR: journal.db not found — skipping")
        return 0
    
    db = get_db()
    issues_found = []
    critical_found = []
    
    # 1. Triggered but not executed
    unexecuted = check_triggered_unexecuted(db)
    if unexecuted:
        critical_found.append("─── EXECUTION GAPS (triggered=1, executed=0) ───")
        for item in unexecuted:
            line = (
                f"🔴 {item['signal_id']} [{item['thesis_id']}] "
                f"fired {item['fire_count']}x in {SIGNAL_WINDOW_HOURS}h "
                f"(first: {item['first_fire']}, last: {item['last_fire']})"
            )
            critical_found.append(line)
    
    # 2. Stale positions
    stale = check_stale_positions(db)
    if stale:
        critical_found.append("─── STALE POSITIONS (open beyond max hold) ───")
        for pos in stale:
            line = (
                f"🔴 {pos['type'].upper()} {pos['symbol']} {pos['direction']} "
                f"open {pos['hours_open']}h (max {pos['max_hours']}h) "
                f"[{pos['entry_signal']}, thesis={pos['thesis_id']}]"
            )
            critical_found.append(line)
    
    # 3. Cross-thesis contamination
    cross = check_cross_thesis_contamination(db)
    if cross:
        issues_found.append("─── CROSS-THESIS OVERLAP ───")
        for item in cross:
            line = (
                f"⚠️  {item['symbol']}: {item['cnt']} open positions across "
                f"theses [{item['thesis_id']}] — signals: {item['signals']}"
            )
            issues_found.append(line)
    
    # 4. Portfolio stats (always show)
    total = db.execute("""
        SELECT 
            COUNT(CASE WHEN status='open' THEN 1 END) as open_count,
            SUM(CASE WHEN status='open' THEN shares * entry_price ELSE 0 END) as deployed,
            SUM(pnl_realized) as total_pnl
        FROM trades
    """).fetchone()
    
    db.close()
    
    # ── Output ──
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    
    all_lines = []
    
    if critical_found or issues_found:
        all_lines.append(f"[MONITOR] Signal Fidelity Check — {now_str}")
        all_lines.append("")
        all_lines.extend(critical_found)
        if critical_found and issues_found:
            all_lines.append("")
        all_lines.extend(issues_found)
        all_lines.append("")
        all_lines.append(
            f"Portfolio: {total['open_count']} open | "
            f"${total['deployed']:,.0f} deployed | "
            f"PnL: ${total['total_pnl']:,.2f}"
        )
        
        output = "\n".join(all_lines)
        # For cron delivery: print to stdout
        print(output)
        
        # Exit code: 2 if critical, 1 if only warnings
        return 2 if critical_found else 1
    else:
        # Clean — silent exit (stdout empty = no Telegram delivery)
        # But print a single-line heartbeat for the cron output file
        print(
            f"[MONITOR] {now_str} — clean: "
            f"{total['open_count']} open, ${total['deployed']:,.0f} deployed — no gaps"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
