#!/usr/bin/env python3
"""Shared database helper for v12 learning modules.

Reads across all 3 per-engine journals via UNION ALL.
Each engine writes to its own journal; learning modules read from the union.
"""

import sqlite3
import os

BASE = os.path.dirname(os.path.abspath(__file__))

ENGINE_DBS = {
    "commodity": os.path.join(BASE, "journal_commodity.db"),
    "ai": os.path.join(BASE, "journal_ai.db"),
    "crypto": os.path.join(BASE, "journal_crypto.db"),
}

SHARED_DB = os.path.join(BASE, "journal.db")


def get_engine_db(engine: str) -> sqlite3.Connection:
    """Return a writable connection to a specific engine's database."""
    if engine not in ENGINE_DBS:
        raise ValueError(f"Unknown engine: {engine}. Choose from {list(ENGINE_DBS.keys())}")
    conn = sqlite3.connect(ENGINE_DBS[engine])
    conn.row_factory = sqlite3.Row
    return conn


def get_shared_db() -> sqlite3.Connection:
    """Return connection to shared journal.db (synthesizer_snapshots, schema_version)."""
    conn = sqlite3.connect(SHARED_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _union_connection(table: str) -> sqlite3.Connection:
    """Internal: create an in-memory connection with a TEMP VIEW combining all 3 engine DBs."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    for engine, db_path in ENGINE_DBS.items():
        conn.execute(f"ATTACH DATABASE ? AS {engine}", (db_path,))

    parts = [f"SELECT *, '{e}' as engine FROM {e}.{table}" for e in ENGINE_DBS]
    conn.execute(f"CREATE TEMP VIEW {table} AS {' UNION ALL '.join(parts)}")
    return conn


def all_trades() -> list[dict]:
    """All trades across all 3 engines."""
    conn = _union_connection("trades")
    return [dict(r) for r in conn.execute("SELECT * FROM trades ORDER BY trade_date")]


def all_signals() -> list[dict]:
    """All signal_log entries across all 3 engines."""
    conn = _union_connection("signal_log")
    return [dict(r) for r in conn.execute("SELECT * FROM signal_log ORDER BY check_date")]


def all_snapshots() -> list[dict]:
    """All portfolio_snapshots across all 3 engines."""
    conn = _union_connection("portfolio_snapshots")
    return [dict(r) for r in conn.execute("SELECT * FROM portfolio_snapshots ORDER BY snap_date")]


def union_query(table: str, where: str = "", params: tuple = ()) -> list[dict]:
    """Run a query against the union view. E.g. union_query('trades', 'WHERE status=?', ('open',))."""
    conn = _union_connection(table)
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" {where}"
    return [dict(r) for r in conn.execute(sql, params)]


# ── Self-test ──
if __name__ == "__main__":
    shared = get_shared_db()

    # Ensure schema_version exists
    shared.execute("""CREATE TABLE IF NOT EXISTS schema_version (
        version TEXT PRIMARY KEY, applied_at TEXT, description TEXT)""")
    shared.execute("""INSERT OR IGNORE INTO schema_version (version, applied_at, description)
        VALUES ('v12.0', datetime('now'), '3-engine isolation: per-engine DBs + db_helper.py union layer')""")
    shared.commit()

    for row in shared.execute("SELECT * FROM schema_version ORDER BY applied_at DESC LIMIT 1"):
        print(f"Schema: {dict(row)}")

    print(f"\nTrades: {len(all_trades())} total")
    print(f"Signals: {len(all_signals())} total")
    print(f"Snapshots: {len(all_snapshots())} total")

    conn = _union_connection("trades")
    for row in conn.execute("SELECT engine, count(*), sum(CASE WHEN status='open' THEN 1 ELSE 0 END) FROM trades GROUP BY engine"):
        print(f"  {row[0]}: {row[1]} trades ({row[2]} open)")

    print("\ndb_helper.py ready.")
