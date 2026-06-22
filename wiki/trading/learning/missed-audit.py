#!/usr/bin/env python3
"""
Missed Opportunity Audit — v10.6
================================
Reads signal_log for triggered-but-not-executed signals.
Backtests: "if we had acted on this signal, how would it have performed?"
Outputs findings to Telegram + appends to rules.md Learning Log.

Usage:
    python3 missed-audit.py              # Full audit → stdout
    python3 missed-audit.py --summary    # Compact for Telegram
    python3 missed-audit.py --days 30    # Look back 30 days (default: 7)

Run: Sunday 9:30 PM IST (after weekly review at 9 PM)
"""

import sqlite3
import os
import sys
import json
from collections import defaultdict
from datetime import datetime, timedelta

try:
    import yfinance as yf
except ImportError:
    print("⚠ yfinance not installed. Install: pip install yfinance", file=sys.stderr)
    sys.exit(1)

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "paper-trader", "journal.db")
RULES_PATH = os.path.join(BASE_DIR, "paper-trader", "rules.md")
LEARNING_DIR = os.path.join(BASE_DIR, "learning")
AUDIT_PATH = os.path.join(LEARNING_DIR, "missed-opportunities.md")

# ── Signal → Symbol mapping ──
SIGNAL_SYMBOL_MAP = {
    # Commodity
    "E1": "XLE", "E2": "XLE", "E3": "XLE",
    "E4S": "GLD", "E4L": "GLD",
    "X1": "XLE", "X2": "XLE", "X3": "XLE", "X4": "XLE", "X5": "XLE",
    # AI
    "AI_E1": "SOXX", "AI_E2": "DTCR", "AI_E3": "INTC",
    "AI_E4": "SOXX", "AI_E5": "SOXX",
    "AI_X1": "SOXX", "AI_X2": "SOXX", "AI_X3": "DTCR",
    "AI_X4": "SOXX", "AI_X5": "SOXX",
    # Crypto
    "CRYPTO_E1": "BTC-USD", "CRYPTO_E2": "BTC-USD",
    "CRYPTO_E3": "BTC-USD", "CRYPTO_E4": "BTC-USD",
    "CRYPTO_X1": "BTC-USD", "CRYPTO_X2": "BTC-USD",
    "CRYPTO_X3": "BTC-USD", "CRYPTO_X4": "BTC-USD",
    "CRYPTO_X5": "BTC-USD",
    # Quant (ensemble-driven, ticker resolved at runtime — use IBIT as BTC proxy)
    "QUANT_E1": "IBIT", "QUANT_E2": "IBIT",
    "QUANT_X1": "IBIT", "QUANT_X2": "IBIT",
    # Intraday (ticker resolved at runtime)
    "INTRADAY_LONG": "IBIT", "INTRADAY_SHORT": "IBIT",
    "INTRADAY_X1": "IBIT", "INTRADAY_X2": "IBIT", "INTRADAY_X3": "IBIT",
}

SIGNAL_DIRECTION = {}  # Inferred from signal_id: entry=long, exit=close
for sig in SIGNAL_SYMBOL_MAP:
    if sig.startswith("X") or sig.startswith("AI_X") or sig.startswith("CRYPTO_X"):
        SIGNAL_DIRECTION[sig] = "exit"
    else:
        SIGNAL_DIRECTION[sig] = "entry"


# ── Database ──

class MissedAuditDB:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_missed_signals(self, days=7) -> list:
        """Find signals that triggered but were NOT executed.
        
        Excludes idempotent skips: if a position was already open for this
        signal+ticker, the skip was correct — not a missed opportunity.
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self.conn.execute(
            """SELECT * FROM signal_log
               WHERE triggered = 1 AND executed = 0
               AND check_date >= ?
               ORDER BY check_date DESC""",
            (cutoff,)
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            sig_id = d["signal_id"]
            # Determine if this was an idempotent skip (position already open)
            symbol = SIGNAL_SYMBOL_MAP.get(sig_id)
            if symbol and self._was_position_already_open(sig_id, symbol, d["check_date"]):
                # Signal was correctly skipped — position was already open
                # Mark it executed so future audits don't re-count it
                self.conn.execute(
                    "UPDATE signal_log SET executed=1, notes='[AUDIT] idempotent skip — position was open' WHERE id=?",
                    (d["id"],)
                )
                self.conn.commit()
                continue
            results.append(d)
        return results

    def _was_position_already_open(self, signal_id: str, symbol: str, check_date: str) -> bool:
        """Check if a position was already open at the time the signal fired.
        
        Uses time-range comparison: position opened before signal, and either
        not yet closed or closed after the signal fired.
        Note: entry_timestamp uses 'T' separator, check_date uses space — 
        we replace 'T' with space for consistent string comparison.
        """
        # For entry signals: same entry_signal had an open position at check time
        if "_E" in signal_id or (not signal_id.startswith("X") and "X" not in signal_id):
            row = self.conn.execute(
                """SELECT COUNT(*) as c FROM trades
                   WHERE entry_signal=? 
                   AND REPLACE(entry_timestamp, 'T', ' ') <= ?
                   AND (exit_date IS NULL OR exit_date >= ?)""",
                (signal_id, check_date, check_date[:10])
            ).fetchone()
            return row["c"] > 0 if row else False
        
        # For exit signals: only count positions from the same signal family
        if "X" in signal_id:
            # Determine which entry signals this exit applies to
            # QUANT_X* exits only apply to QUANT_E* entries
            # INTRADAY_X* exits only apply to INTRADAY_* entries
            # Thesis X* exits apply to thesis E* entries
            if signal_id.startswith("QUANT_X"):
                entry_filter = "AND entry_signal LIKE 'QUANT_E%'"
            elif signal_id.startswith("INTRADAY_X"):
                entry_filter = "AND entry_signal LIKE 'INTRADAY_%'"
            else:
                entry_filter = ""  # Thesis exits — check all
            
            row = self.conn.execute(
                f"""SELECT COUNT(*) as c FROM trades
                   WHERE REPLACE(entry_timestamp, 'T', ' ') <= ?
                   AND (exit_date IS NULL OR exit_date >= ?)
                   {entry_filter}""",
                (check_date, check_date[:10])
            ).fetchone()
            # For exits: if no matching position open, the skip was correct
            return row["c"] == 0 if row else True
        
        return False

    def get_all_missed(self) -> list:
        """Get ALL missed signals historically."""
        rows = self.conn.execute(
            """SELECT * FROM signal_log
               WHERE triggered = 1 AND executed = 0
               ORDER BY check_date DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def get_total_signals(self, days=7) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM signal_log WHERE check_date >= ?",
            (cutoff,)
        ).fetchone()
        return row["cnt"] if row else 0

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


# ── Price Backtester ──

class PriceBacktester:
    """Fetch historical prices and compute hypothetical P&L."""

    @staticmethod
    def get_price(symbol: str, date_str: str) -> float:
        """Get closing price for a symbol on a given date."""
        try:
            # Parse date, get 5 days of data around it
            target_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            end_date = target_date + timedelta(days=3)

            data = yf.download(symbol, start=target_date - timedelta(days=2),
                              end=end_date, progress=False, auto_adjust=True)
            if data.empty:
                return None

            closes = data["Close"].dropna()
            if closes.empty:
                return None

            # If multi-column (yfinance quirk), pick first column
            if isinstance(closes, type(data)) and closes.shape[1] > 1:
                closes = closes.iloc[:, 0]
            closes = closes.squeeze()  # ensure 1-D Series
            if closes.empty:
                return None

            # Normalize timezone
            if hasattr(closes.index, 'tz') and closes.index.tz:
                closes.index = closes.index.tz_localize(None)
            
            target_naive = datetime(target_date.year, target_date.month, target_date.day)
            if target_naive >= datetime.now().replace(hour=0, minute=0, second=0):
                # Target is today or future — use latest available close
                return round(float(closes.iloc[-1]), 2)
            closest_idx = min(closes.index, key=lambda d: abs((d - target_naive).days))
            pos = list(closes.index).index(closest_idx)
            return round(float(closes.iloc[pos]), 2)
        except Exception:
            return None

    @staticmethod
    def compute_hypothetical_pnl(signal_id: str, signal_date: str,
                                 symbol: str, current_price: float) -> dict:
        """
        Simulate: "what if we had entered/exited on signal_date?"
        Returns dict with hypothetical result.
        """
        entry_price = PriceBacktester.get_price(symbol, signal_date)
        if entry_price is None:
            return {"status": "no_price_data", "entry_price": None, "pnl": None}

        direction = SIGNAL_DIRECTION.get(signal_id, "entry")
        allocation_pct = 0.05 if signal_id == "E4S" else 0.25  # rough

        # Simulate $100K portfolio
        capital = 100000 * allocation_pct
        shares = capital / entry_price if entry_price > 0 else 0

        if direction == "entry":
            pnl = (current_price - entry_price) * shares
        else:
            pnl = (entry_price - current_price) * shares  # exit = close position

        pnl_pct = (pnl / capital * 100) if capital > 0 else 0

        result = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "FLAT")

        return {
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "shares": round(shares, 4),
            "allocation_pct": allocation_pct,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 1),
            "result": result,
            "signal_date": signal_date,
        }


# ── Analyzer ──

class MissedAudit:
    def __init__(self, db: MissedAuditDB):
        self.db = db

    def analyze(self, days: int = 7) -> dict:
        """Run the full missed opportunity analysis."""
        missed = self.db.get_missed_signals(days)
        total = self.db.get_total_signals(days)

        report = {
            "total_checks": total,
            "missed_count": len(missed),
            "missed_rate": len(missed) / total * 100 if total > 0 else 0,
            "opportunities": [],
            "total_missed_pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "no_data": 0,
            "regime_breakdown": defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0}),
        }

        for sig in missed:
            sig_id = sig["signal_id"]
            symbol = SIGNAL_SYMBOL_MAP.get(sig_id)
            if not symbol:
                continue

            # Get current price
            current_price = PriceBacktester.get_price(symbol,
                datetime.now().strftime("%Y-%m-%d"))
            if current_price is None:
                continue

            result = PriceBacktester.compute_hypothetical_pnl(
                sig_id, sig["check_date"], symbol, current_price
            )

            # Correlate with regime
            regime = self.db.get_regime_at(sig["check_date"][:10])
            result["regime"] = regime

            if result["pnl"] is not None:
                report["total_missed_pnl"] += result["pnl"]
                if result["result"] == "WIN":
                    report["wins"] += 1
                    report["regime_breakdown"][regime]["wins"] += 1
                elif result["result"] == "LOSS":
                    report["losses"] += 1
                report["regime_breakdown"][regime]["count"] += 1
                report["regime_breakdown"][regime]["pnl"] += result["pnl"]
            else:
                report["no_data"] += 1

            report["opportunities"].append({
                "signal_id": sig_id,
                "check_date": sig["check_date"],
                "notes": sig.get("notes", ""),
                "backtest": result,
            })

        return report

    def summary(self, report: dict) -> str:
        """Compact Telegram-ready summary."""
        lines = ["[AUDIT] #missed-opportunities", ""]

        if report["missed_count"] == 0:
            lines.append("✅ **No missed signals this week.**")
            lines.append(f"   {report['total_checks']} checks, 0 missed.")
            return "\n".join(lines)

        missed_rate = report["missed_rate"]
        icon = "🔴" if missed_rate > 10 else ("🟡" if missed_rate > 5 else "🟢")

        lines.append(f"{icon} **{report['missed_count']} missed signals** "
                     f"out of {report['total_checks']} checks ({missed_rate:.0f}%)")

        if report["opportunities"]:
            wins = report["wins"]
            losses = report["losses"]
            total_pnl = report["total_missed_pnl"]
            pnl_str = f"+${total_pnl:,.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.2f}"

            lines.append(f"   Backtest: {wins}W / {losses}L — hypothetical P&L: {pnl_str}")

            # ── Regime Context ──
            rb = report.get("regime_breakdown", {})
            if rb:
                risky_regimes = {"RISK_OFF", "CAUTIOUS"}
                safe_misses = sum(rb[r]["count"] for r in risky_regimes if r in rb)
                total_rb = sum(v["count"] for v in rb.values())
                if safe_misses > 0:
                    pct = safe_misses / total_rb * 100
                    lines.append(f"   🛡️ **{safe_misses}/{total_rb} missed signals ({pct:.0f}%) were in RISK_OFF/CAUTIOUS** — "
                                f"these would have been filtered, not missed")
                # Regime-by-regime breakdown
                regime_lines = []
                for reg in sorted(rb.keys()):
                    rd = rb[reg]
                    pnl_s = f"+${rd['pnl']:,.0f}" if rd['pnl'] >= 0 else f"-${abs(rd['pnl']):,.0f}"
                    wr = rd['wins']/rd['count']*100 if rd['count']>0 else 0
                    regime_lines.append(f"     {reg}: {rd['count']} signals, {wr:.0f}% WR, {pnl_s}")
                if regime_lines:
                    lines.append("   📊 **By regime:**")
                    lines.extend(regime_lines)

            for opp in report["opportunities"][:5]:
                bt = opp["backtest"]
                result_icon = "✅" if bt.get("result") == "WIN" else ("❌" if bt.get("result") == "LOSS" else "➖")
                pnl_str = f"+${bt['pnl']:,.2f}" if bt.get('pnl', 0) >= 0 else f"-${abs(bt.get('pnl', 0)):,.2f}"
                lines.append(
                    f"   {result_icon} {opp['signal_id']} on {opp['check_date'][:10]} "
                    f"— {bt['symbol']} @ ${bt.get('entry_price', '?'):,.2f} "
                    f"→ ${bt.get('current_price', '?'):,.2f} ({pnl_str})"
                )

            # Recommendation
            if wins > losses and total_pnl > 0:
                lines.append("")
                lines.append(f"💡 **Recommendation:** {wins}/{wins+losses} missed signals were profitable. "
                            "Consider lowering execution threshold or adding auto-execute.")
            elif losses > wins:
                lines.append("")
                lines.append(f"💡 **Note:** More losses than wins. The execution filter (delivery bug, "
                            "data gap) saved capital. No action needed.")

        return "\n".join(lines)

    def full_report(self, report: dict) -> str:
        """Full audit report for vault."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M IST")
        lines = [
            "# Missed Opportunity Audit",
            f"> {now} | Past 7 days",
            "",
            f"**{report['missed_count']} missed** / {report['total_checks']} total checks ({report['missed_rate']:.0f}%)",
            f"Hypothetical P&L: ${report['total_missed_pnl']:,.2f}",
            f"Backtest: {report['wins']}W / {report['losses']}L",
            "",
        ]

        if report["opportunities"]:
            lines.append("| Signal | Date | Symbol | Regime | Entry | Current | P&L | Result |")
            lines.append("|--------|------|--------|--------|-------|---------|-----|--------|")
            for opp in report["opportunities"]:
                bt = opp["backtest"]
                result_icon = "✅ WIN" if bt.get("result") == "WIN" else ("❌ LOSS" if bt.get("result") == "LOSS" else "➖ FLAT")
                pnl_str = f"+${bt['pnl']:,.2f}" if bt.get('pnl', 0) >= 0 else f"-${abs(bt.get('pnl', 0)):,.2f}"
                regime = bt.get("regime", "?")
                lines.append(
                    f"| {opp['signal_id']} | {opp['check_date'][:10]} | {bt.get('symbol','?')} | "
                    f"{regime} | "
                    f"${bt.get('entry_price','?'):,.2f} | ${bt.get('current_price','?'):,.2f} | "
                    f"{pnl_str} | {result_icon} |"
                )

        lines.append("")
        lines.append("---")
        lines.append("*Generated by learning/missed-audit.py (v10.6)*")
        return "\n".join(lines)

    def log_entry(self, report: dict) -> str:
        """Generate a learning log entry for rules.md."""
        now = datetime.now().strftime("%Y-%m-%d")
        if report["missed_count"] == 0:
            return f"| {now} | 0 missed | {report['total_checks']} checks | ✅ No missed opportunities |"

        wins = report["wins"]
        losses = report["losses"]
        pnl = report["total_missed_pnl"]
        pnl_str = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
        return (f"| {now} | {report['missed_count']} missed, {wins}W/{losses}L | "
                f"Hypothetical {pnl_str} | "
                f"{'Review execution threshold' if wins > losses else 'Filter working correctly'} |")


# ── Main ──

def main():
    summary_only = "--summary" in sys.argv
    days = 7
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    db = MissedAuditDB()
    auditor = MissedAudit(db)

    report = auditor.analyze(days)

    # Write full report
    os.makedirs(LEARNING_DIR, exist_ok=True)
    with open(AUDIT_PATH, "w") as f:
        f.write(auditor.full_report(report))

    # Append to rules.md Learning Log
    with open(RULES_PATH, "a") as f:
        f.write(auditor.log_entry(report) + "\n")

    # Output
    if summary_only:
        print(auditor.summary(report))
    else:
        print(auditor.full_report(report))

    db.close()


if __name__ == "__main__":
    main()
