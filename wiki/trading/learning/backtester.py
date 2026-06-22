#!/usr/bin/env python3
"""
Walk-Forward Backtester — v10.6
================================
Systematic backtest of ALL triggered signals. Simulates entry at signal date,
walks forward day-by-day, closes on exit signal or today.

Usage:
    python3 backtester.py              # Full backtest → stdout
    python3 backtester.py --summary    # Telegram-ready summary
    python3 backtester.py --days 90    # Look back 90 days (default: all)

Output: learning/backtest-report.md
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

try:
    import yfinance as yf
except ImportError:
    print("yfinance required", file=sys.stderr)
    sys.exit(1)

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "paper-trader" / "journal.db"
REPORT_PATH = BASE_DIR / "learning" / "backtest-report.md"

SIGNAL_SYMBOL_MAP = {
    "E1": "XLE", "E2": "XLE", "E3": "XLE",
    "E4S": "GLD", "E4L": "GLD",
    "X1": "XLE", "X2": "XLE", "X3": "XLE", "X4": "XLE", "X5": "XLE",
    "AI_E1": "SOXX", "AI_E2": "DTCR", "AI_E3": "INTC",
    "AI_E4": "SOXX", "AI_E5": "SOXX",
    "AI_X1": "SOXX", "AI_X2": "SOXX", "AI_X3": "DTCR",
    "AI_X4": "SOXX", "AI_X5": "SOXX",
    "CRYPTO_E1": "BTC-USD", "CRYPTO_E2": "BTC-USD",
    "CRYPTO_E3": "BTC-USD", "CRYPTO_E4": "BTC-USD",
}

SIGNAL_DIRECTION = {}
for sig in SIGNAL_SYMBOL_MAP:
    SIGNAL_DIRECTION[sig] = "exit" if ("X" in sig and not sig.startswith("E")) else "entry"


# ═══════════════════════════════════════════════════════════════════════════

class BacktestDB:
    def __init__(self, db_path=str(DB_PATH)):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_triggered_signals(self, days: int = None) -> List[Dict]:
        """Get all triggered signals, optionally within N days."""
        query = "SELECT * FROM signal_log WHERE triggered = 1"
        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            query += f" AND check_date >= '{cutoff}'"
        query += " ORDER BY check_date ASC"
        return [dict(r) for r in self.conn.execute(query).fetchall()]

    def get_regime_at(self, date_str: str) -> str:
        """Find the synthesizer regime closest to a given date. Returns 'UNKNOWN' if no data."""
        try:
            row = self.conn.execute(
                """SELECT regime FROM synthesizer_snapshots
                   WHERE created_at >= ? AND created_at <= ?
                   ORDER BY created_at LIMIT 1""",
                (date_str + " 00:00", date_str + " 23:59")
            ).fetchone()
            return row["regime"] if row else "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def close(self):
        self.conn.close()


class WalkForwardBacktester:
    """Walk-forward simulate every triggered signal."""

    @staticmethod
    def fetch_price_history(symbol: str, start_date: str, end_date: str) -> Optional[Tuple[List[float], List]]:
        """Fetch daily closing prices between dates. Returns (prices, dates) or None."""
        try:
            start = datetime.strptime(start_date[:10], "%Y-%m-%d")
            end = datetime.strptime(end_date[:10], "%Y-%m-%d")
            buffer_start = start - timedelta(days=5)
            buffer_end = end + timedelta(days=2)

            data = yf.download(symbol, start=buffer_start, end=buffer_end,
                              progress=False, auto_adjust=True)
            if data.empty:
                return None

            closes = data["Close"].dropna()
            if closes.empty:
                return None
            # Handle yfinance multi-column quirk
            if hasattr(closes, 'shape') and len(closes.shape) > 1 and closes.shape[1] > 0:
                closes = closes.iloc[:, 0]
            closes = closes.squeeze()
            if closes.empty:
                return None
            # Normalize timezone
            dates = list(closes.index)
            if hasattr(dates[0], 'tz') and dates[0].tz:
                dates = [d.replace(tzinfo=None) for d in dates]
            prices = [float(c) for c in closes]
            return prices, dates
        except Exception:
            return None

    @staticmethod
    def nearest_price(prices: List[float], dates: list, target_date: str) -> Optional[float]:
        """Find price nearest to target_date using actual date list."""
        target = datetime.strptime(target_date[:10], "%Y-%m-%d")
        best = None
        best_diff = timedelta(days=9999)
        for i, d in enumerate(dates):
            if hasattr(d, 'tz') and d.tz:
                d = d.replace(tzinfo=None)
            if isinstance(d, datetime):
                diff = abs(d - target)
                if diff < best_diff:
                    best_diff = diff
                    best = prices[i] if i < len(prices) else None
        # Fallback: if no date match found, use last price
        return best if best is not None else (prices[-1] if prices else None)

    @staticmethod
    def simulate_trade(signal_id: str, entry_date: str, symbol: str,
                       prices: List[float], dates: list,
                       exit_signal_date: Optional[str] = None) -> Dict:
        """Simulate a single trade from entry to exit or today."""
        direction = SIGNAL_DIRECTION.get(signal_id, "entry")
        entry_price = WalkForwardBacktester.nearest_price(prices, dates, entry_date)
        if entry_price is None:
            return {"status": "no_data"}

        # Find exit price
        exit_price = None
        if exit_signal_date:
            exit_price = WalkForwardBacktester.nearest_price(prices, dates, exit_signal_date)
        if exit_price is None and prices:
            exit_price = prices[-1]  # today's price

        if exit_price is None:
            return {"status": "no_data"}

        # P&L
        if direction == "entry":
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100

        return {
            "status": "ok",
            "symbol": symbol,
            "direction": direction,
            "entry_date": entry_date[:10],
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl_pct, 1),
            "result": "WIN" if pnl_pct > 0 else ("LOSS" if pnl_pct < 0 else "FLAT"),
            "exit_date": exit_signal_date[:10] if exit_signal_date else "today",
        }

    def run(self, days: int = None) -> Dict:
        """Run full backtest on all triggered signals."""
        db = BacktestDB()
        signals = db.get_triggered_signals(days)

        if not signals:
            db.close()
            return {"trades": [], "summary": {"count": 0, "message": "No triggered signals found"}}

        trades = []
        # Group by signal_id + check_date to avoid duplicates
        seen = set()
        unique_signals = []
        for s in signals:
            key = (s["signal_id"], s["check_date"][:10])
            if key not in seen:
                seen.add(key)
                unique_signals.append(s)

        regime_perf = defaultdict(lambda: {"count": 0, "wins": 0, "total_pnl": 0.0})

        for sig in unique_signals:
            sig_id = sig["signal_id"]
            symbol = SIGNAL_SYMBOL_MAP.get(sig_id)
            if not symbol:
                continue

            entry_date = sig["check_date"][:10]
            end_date = datetime.now().strftime("%Y-%m-%d")

            prices_raw = self.fetch_price_history(symbol, entry_date, end_date)
            if prices_raw is None:
                continue
            prices, date_list = prices_raw

            trade = self.simulate_trade(sig_id, entry_date, symbol,
                                        prices, date_list)
            if trade.get("status") == "ok":
                trade["signal_id"] = sig_id
                trade["regime"] = db.get_regime_at(entry_date)
                trades.append(trade)
                regime_perf[trade["regime"]]["count"] += 1
                regime_perf[trade["regime"]]["total_pnl"] += trade["pnl_pct"]
                if trade["result"] == "WIN":
                    regime_perf[trade["regime"]]["wins"] += 1

        db.close()

        # Aggregate
        wins = [t for t in trades if t["result"] == "WIN"]
        losses = [t for t in trades if t["result"] == "LOSS"]
        flats = [t for t in trades if t["result"] == "FLAT"]

        total_pnl = sum(t["pnl_pct"] for t in trades)
        avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0

        # Sort by entry date
        trades.sort(key=lambda t: t["entry_date"])

        # Running equity curve (simplified: cumulative P&L %)
        equity_curve = []
        running = 0.0
        max_equity = 0.0
        max_drawdown = 0.0
        for t in trades:
            running += t["pnl_pct"]
            equity_curve.append(round(running, 1))
            if running > max_equity:
                max_equity = running
            dd = max_equity - running
            if dd > max_drawdown:
                max_drawdown = dd

        # Signal-level performance
        signal_perf = defaultdict(lambda: {"count": 0, "wins": 0, "total_pnl": 0.0})
        for t in trades:
            sid = t["signal_id"]
            signal_perf[sid]["count"] += 1
            signal_perf[sid]["total_pnl"] += t["pnl_pct"]
            if t["result"] == "WIN":
                signal_perf[sid]["wins"] += 1

        return {
            "trades": trades,
            "summary": {
                "count": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "flats": len(flats),
                "win_rate": len(wins) / len(trades) * 100 if trades else 0,
                "total_pnl_pct": round(total_pnl, 1),
                "avg_win_pct": round(avg_win, 1),
                "avg_loss_pct": round(avg_loss, 1),
                "max_drawdown_pct": round(max_drawdown, 1),
                "equity_curve": equity_curve,
                "signal_performance": dict(signal_perf),
                "regime_performance": dict(regime_perf),
            }
        }

    def summary_str(self, result: Dict) -> str:
        """Telegram-ready summary."""
        s = result["summary"]
        if s["count"] == 0:
            return "[BACKTEST] #validation\n\nNo triggered signals to backtest."

        lines = ["[BACKTEST] #walk-forward", ""]
        lines.append(f"📊 **{s['count']} trades** backtested")
        lines.append(f"✅ Win rate: **{s['win_rate']:.0f}%** ({s['wins']}W / {s['losses']}L / {s['flats']}F)")
        pnl_str = f"+{s['total_pnl_pct']}%" if s['total_pnl_pct'] >= 0 else f"{s['total_pnl_pct']}%"
        lines.append(f"💰 Cumulative P&L: **{pnl_str}**")
        lines.append(f"📈 Avg win: +{s['avg_win_pct']}% | Avg loss: {s['avg_loss_pct']}%")
        if s['max_drawdown_pct'] > 0:
            lines.append(f"📉 Max drawdown: -{s['max_drawdown_pct']}%")

        # Best/worst
        trades = result.get("trades", [])
        if trades:
            best = max(trades, key=lambda t: t["pnl_pct"])
            worst = min(trades, key=lambda t: t["pnl_pct"])
            lines.append(f"🏆 Best: {best['signal_id']} {best['symbol']} +{best['pnl_pct']}%")
            lines.append(f"💀 Worst: {worst['signal_id']} {worst['symbol']} {worst['pnl_pct']}%")

        # Regime performance
        rp = s.get("regime_performance", {})
        if rp:
            lines.append("")
            lines.append("**Regime Performance:**")
            for reg, rd in sorted(rp.items(), key=lambda x: x[1]["total_pnl"], reverse=True):
                wr = rd["wins"] / rd["count"] * 100 if rd["count"] > 0 else 0
                pnl_s = f"+{rd['total_pnl']}%" if rd['total_pnl'] >= 0 else f"{rd['total_pnl']}%"
                lines.append(f"  {reg}: {rd['count']} trades, {wr:.0f}% WR, {pnl_s}")

        # Signal performance
        perf = s.get("signal_performance", {})
        if perf:
            lines.append("")
            lines.append("**Signal Performance:**")
            for sid, p in sorted(perf.items(), key=lambda x: x[1]["wins"]/max(x[1]["count"],1), reverse=True)[:5]:
                wr = p["wins"] / p["count"] * 100 if p["count"] > 0 else 0
                pnl_s = f"+{p['total_pnl']}%" if p['total_pnl'] >= 0 else f"{p['total_pnl']}%"
                lines.append(f"  {sid}: {wr:.0f}% WR, {pnl_s} ({p['count']} trades)")

        return "\n".join(lines)


# ── Main ──

def main():
    summary_only = "--summary" in sys.argv
    days = None
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    bt = WalkForwardBacktester()
    result = bt.run(days)

    # Write report
    os.makedirs(REPORT_PATH.parent, exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(f"# Walk-Forward Backtest Report\n")
        f.write(f"> {datetime.now().strftime('%Y-%m-%d %H:%M IST')}\n\n")
        f.write(f"**{result['summary']['count']} trades** | ")
        f.write(f"Win rate: {result['summary']['win_rate']:.0f}% | ")
        f.write(f"Cumulative P&L: {result['summary']['total_pnl_pct']:+.1f}%\n\n")
        for t in result.get("trades", []):
            icon = "✅" if t["result"] == "WIN" else "❌"
            f.write(f"{icon} {t['signal_id']} {t['symbol']} | "
                    f"{t['entry_date']} → {t['exit_date']} | "
                    f"{t['pnl_pct']:+.1f}% ({t['result']})\n")

    if summary_only:
        print(bt.summary_str(result))
    else:
        print(bt.summary_str(result))
        print()
        for t in result.get("trades", [])[:20]:
            icon = "✅" if t["result"] == "WIN" else "❌"
            print(f"{icon} {t['signal_id']:8s} {t['symbol']:6s} "
                  f"{t['entry_date']} → {t['exit_date']} "
                  f"{t['pnl_pct']:+.1f}%")


if __name__ == "__main__":
    main()
