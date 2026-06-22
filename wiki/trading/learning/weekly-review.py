#!/usr/bin/env python3
"""
Weekly Review — Learning Loop (v5)
====================================
Reads per-engine journals via db_helper union, analyzes trade patterns,
generates weekly-review.md, and appends findings to rules.md Learning Log.

Usage:
    python3 weekly-review.py                # Full review → stdout + writes files
    python3 weekly-review.py --summary      # Compact output for Telegram

Run: Sunday 9 PM IST (after weekly tracker at 8 PM)
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paper-trader"))
from db_helper import all_trades, all_signals, all_snapshots, union_query
from datetime import datetime, timedelta
from collections import defaultdict

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(BASE_DIR, "paper-trader", "rules.md")
LEARNING_DIR = os.path.join(BASE_DIR, "learning")
REVIEW_PATH = os.path.join(LEARNING_DIR, "weekly-review.md")
PATTERN_PATH = os.path.join(LEARNING_DIR, "pattern-journal.md")

# ── Database ──

class ReviewDB:
    """Read-only access to all 3 per-engine journals via db_helper union layer."""

    def get_trades_since(self, days=7):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return union_query("trades", "WHERE trade_date >= ?", (cutoff,))

    def get_all_trades(self):
        return all_trades()

    def get_closed_trades(self, days=7):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return union_query("trades", "WHERE status = 'closed' AND exit_date >= ?", (cutoff,))

    def get_open_positions(self):
        return union_query("trades", "WHERE status = 'open'")

    def get_signal_activity(self, days=7):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return union_query("signal_log", "WHERE check_date >= ?", (cutoff,))

    def get_snapshots(self, days=7):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return union_query("portfolio_snapshots", "WHERE snap_date >= ?", (cutoff,))

    def close(self):
        pass  # db_helper manages connections internally


# ── Analysis ──

class WeeklyReview:
    def __init__(self, db: ReviewDB):
        self.db = db
        self.week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        self.today = datetime.now().strftime("%Y-%m-%d")

    def analyze(self) -> dict:
        """Run all analyses. Returns a structured report dict."""
        report = {}

        # ── Trade Performance ──
        all_trades = self.db.get_all_trades()
        closed = self.db.get_closed_trades(days=7)
        open_pos = self.db.get_open_positions()
        signals = self.db.get_signal_activity(days=7)
        snapshots = self.db.get_snapshots(days=7)

        report["total_trades_all_time"] = len(all_trades)
        report["open_positions"] = len(open_pos)
        report["closed_this_week"] = len(closed)

        # Closed trade stats
        if closed:
            winners = [t for t in closed if t["pnl_realized"] > 0]
            losers = [t for t in closed if t["pnl_realized"] <= 0]
            report["win_count"] = len(winners)
            report["loss_count"] = len(losers)
            report["win_rate"] = len(winners) / len(closed) * 100 if closed else 0
            report["total_realized_pnl"] = sum(t["pnl_realized"] for t in closed)
            report["best_trade"] = max(closed, key=lambda t: t["pnl_realized"]) if closed else None
            report["worst_trade"] = min(closed, key=lambda t: t["pnl_realized"]) if closed else None

            # R-multiple (PnL / initial risk). Risk = entry_price * shares for longs,
            # simplified as % return on deployed capital
            if closed:
                total_risk = sum(t["entry_price"] * t["shares"] for t in closed)
                if total_risk > 0:
                    report["avg_r_multiple"] = report["total_realized_pnl"] / total_risk

        # Open position aging
        report["oldest_open_days"] = 0
        for pos in open_pos:
            entry_date = datetime.strptime(pos["trade_date"], "%Y-%m-%d")
            age = (datetime.now() - entry_date).days
            if age > report["oldest_open_days"]:
                report["oldest_open_days"] = age

        # Signal activity
        triggered = [s for s in signals if s["triggered"]]
        executed = [s for s in triggered if s["executed"]]
        missed = [s for s in triggered if not s["executed"]]
        report["signals_checked"] = len(signals)
        report["signals_triggered"] = len(triggered)
        report["signals_executed"] = len(executed)
        report["signals_missed"] = len(missed)
        report["missed_details"] = [
            f"{s['signal_id']} on {s['check_date']} — {s['notes']}" for s in missed
        ]

        # Entry signal performance (which signals win?)
        if closed:
            signal_perf = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0})
            for t in closed:
                sig = t["entry_signal"]
                signal_perf[sig]["count"] += 1
                signal_perf[sig]["pnl"] += t["pnl_realized"]
                if t["pnl_realized"] > 0:
                    signal_perf[sig]["wins"] += 1
            report["signal_performance"] = dict(signal_perf)

        # Portfolio snapshots trend
        if len(snapshots) >= 2:
            first = snapshots[-1]
            last = snapshots[0]
            report["equity_start"] = first["equity"]
            report["equity_end"] = last["equity"]
            report["equity_change"] = last["equity"] - first["equity"]
            report["equity_change_pct"] = (
                (last["equity"] - first["equity"]) / first["equity"] * 100
                if first["equity"] > 0 else 0
            )

        return report

    def weekly_review_md(self, report: dict) -> str:
        """Generate the weekly-review.md content."""
        now = datetime.now()
        week_num = now.isocalendar()[1]
        lines = []

        lines.append(f"# Weekly Review — Week {week_num}, {now.year}")
        lines.append("")
        lines.append(f"> {self.week_start} → {self.today}")
        lines.append(f"> Generated: {now.strftime('%Y-%m-%d %H:%M IST')}")
        lines.append("")

        # ── Portfolio Health ──
        lines.append("## Portfolio Health")
        lines.append("")
        if "equity_start" in report:
            arrow = "↑" if report["equity_change"] >= 0 else "↓"
            lines.append(f"Equity: ${report['equity_start']:,.0f} → ${report['equity_end']:,.0f} "
                         f"({arrow} {report['equity_change_pct']:+.1f}%)")
        lines.append(f"Open positions: {report['open_positions']}")
        if report["oldest_open_days"] > 0:
            lines.append(f"Oldest open: {report['oldest_open_days']} days")
        lines.append("")

        # ── Trade Performance ──
        lines.append("## Trade Performance (Last 7 Days)")
        lines.append("")
        if report["closed_this_week"] > 0:
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Trades closed | {report['closed_this_week']} |")
            lines.append(f"| Win rate | {report.get('win_rate', 0):.0f}% ({report.get('win_count', 0)}W / {report.get('loss_count', 0)}L) |")
            lines.append(f"| Realized P&L | ${report['total_realized_pnl']:,.2f} |")
            if "avg_r_multiple" in report:
                lines.append(f"| Avg R-multiple | {report['avg_r_multiple']:.2f}R |")
            if report.get("best_trade"):
                lines.append(f"| Best trade | {report['best_trade']['symbol']} {report['best_trade']['entry_signal']}: +${report['best_trade']['pnl_realized']:,.2f} |")
            if report.get("worst_trade") and report["worst_trade"]["pnl_realized"] < 0:
                lines.append(f"| Worst trade | {report['worst_trade']['symbol']} {report['worst_trade']['entry_signal']}: -${abs(report['worst_trade']['pnl_realized']):,.2f} |")
        else:
            lines.append("No trades closed this week.")
        lines.append("")

        # ── Signal Activity ──
        lines.append("## Signal Activity")
        lines.append("")
        lines.append(f"| Metric | Count |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Checks run | {report['signals_checked']} |")
        lines.append(f"| Signals triggered | {report['signals_triggered']} |")
        lines.append(f"| Executed | {report['signals_executed']} |")
        lines.append(f"| **Missed** | **{report['signals_missed']}** |")
        if report["missed_details"]:
            lines.append("")
            lines.append("### ⚠️ Missed Signals")
            for detail in report["missed_details"]:
                lines.append(f"- {detail}")
        lines.append("")

        # ── Signal Performance (if closed trades exist) ──
        if report.get("signal_performance"):
            lines.append("## Entry Signal Performance (All-Time)")
            lines.append("")
            lines.append("| Signal | Trades | Win Rate | Total P&L | Rating |")
            lines.append("|--------|--------|----------|-----------|--------|")
            for sig, perf in sorted(report["signal_performance"].items()):
                win_rate = perf["wins"] / perf["count"] * 100 if perf["count"] > 0 else 0
                pnl_str = f"+${perf['pnl']:,.2f}" if perf["pnl"] >= 0 else f"-${abs(perf['pnl']):,.2f}"
                rating = "⭐⭐⭐" if win_rate >= 70 else ("⭐⭐" if win_rate >= 50 else "⭐")
                lines.append(f"| {sig} | {perf['count']} | {win_rate:.0f}% | {pnl_str} | {rating} |")
            lines.append("")

        # ── Open Positions ──
        open_pos = self.db.get_open_positions()
        if open_pos:
            lines.append("## Open Positions")
            lines.append("")
            for pos in open_pos:
                direction = "LONG" if pos["direction"] == "long" else "SHORT"
                entry_date = pos["trade_date"]
                age = (datetime.now() - datetime.strptime(entry_date, "%Y-%m-%d")).days
                lines.append(f"- **{direction} {pos['symbol']}** — {pos['shares']} shares @ ${pos['entry_price']:,.2f} "
                             f"({pos['entry_signal']}, {age}d old)")
            lines.append("")

        # ── Learning Log (appended to rules.md) ──
        lines.append("## Patterns & Learnings")
        lines.append("")
        learnings = self.extract_patterns(report)
        for l in learnings:
            lines.append(f"- {l}")
        lines.append("")

        # ── Suggested Rule Changes ──
        if report["signals_missed"] > 0:
            lines.append("## Suggested Rule Changes")
            lines.append("")
            lines.append(f"- Investigate why {report['signals_missed']} signal(s) missed execution.")
            lines.append("- If delivery failure: add pre-flight check to cron.")
            lines.append("- If data gap: add fallback data source for signal check.")
            lines.append("")

        lines.append("---")
        # ── Synthesizer Context ──
        if report.get("synth_context"):
            lines.append(report["synth_context"])
            lines.append("")
        lines.append("*Generated by learning/weekly-review.py (v5 learning loop)*")
        return "\n".join(lines)

    def extract_patterns(self, report: dict) -> list:
        """Extract actionable patterns from the data."""
        patterns = []

        if report["signals_missed"] > 0:
            patterns.append(f"⚠️ {report['signals_missed']} signal(s) triggered but not executed — check delivery pipeline.")

        if report["open_positions"] == 0 and report["closed_this_week"] == 0:
            patterns.append("📭 No activity this week. All signals idle. Thesis waiting for price action.")

        if report["closed_this_week"] == 0 and report["open_positions"] > 0:
            patterns.append(f"⏳ {report['open_positions']} position(s) aging. No exits hit. Thesis patience intact.")

        if report.get("win_rate", 0) >= 70 and report["closed_this_week"] >= 2:
            patterns.append("✅ High win rate — signal rules are working. Consider increasing size on high-confluence entries.")

        if report.get("win_rate", 0) <= 40 and report["closed_this_week"] >= 2:
            patterns.append("⚠️ Low win rate — review signal thresholds. May need tighter confluence requirements.")

        if report.get("oldest_open_days", 0) > 30:
            patterns.append(f"⏳ Oldest position {report['oldest_open_days']} days old. Review whether thesis timeline still valid.")

        return patterns

    def learning_log_entry(self, report: dict) -> str:
        """Generate a compact learning log entry for rules.md."""
        now = datetime.now().strftime("%Y-%m-%d")
        patterns = self.extract_patterns(report)
        lines = [f"\n| {now} |"]
        if report["closed_this_week"] > 0:
            lines[0] += f" {report['closed_this_week']} closed, {report.get('win_rate', 0):.0f}% win rate |"
        else:
            lines[0] += " No closed trades |"
        lines[0] += f" {report['open_positions']} open, {report['signals_triggered']} triggered |"
        if patterns:
            lines[0] += f" {'; '.join(patterns[:2])} |"
        else:
            lines[0] += " — |"
        return "".join(lines)


# ── Main ──

def main():
    summary_only = "--summary" in sys.argv

    db = ReviewDB()
    reviewer = WeeklyReview(db)

    report = reviewer.analyze()
    
    # ── Pull synthesizer context for the week (shared journal.db) ──
    synth_context = ""
    try:
        from db_helper import get_shared_db
        shared = get_shared_db()
        rows = shared.execute("""
            SELECT created_at, regime, confluence_score, risk_factor, risk_severity,
                   commodity_bias, crypto_bias, ai_bias
            FROM synthesizer_snapshots
            WHERE created_at >= date('now','-7 days')
            ORDER BY created_at DESC LIMIT 10
        """).fetchall()
        if rows:
            regimes = [r["regime"] for r in rows]
            dominant = max(set(regimes), key=regimes.count) if regimes else "N/A"
            latest = rows[0]
            synth_context = f"\n\n## Synthesizer Context (Last 7 Days)\n"
            synth_context += f"- Dominant regime: **{dominant}**\n"
            synth_context += f"- Latest ({latest['created_at']}): regime={latest['regime']}, "
            synth_context += f"confluence={latest['confluence_score']}/5, risk={latest['risk_factor']} ({latest['risk_severity']})\n"
            synth_context += f"- Thesis biases: Commodity={latest['commodity_bias']}, Crypto={latest['crypto_bias']}, AI={latest['ai_bias']}\n"
    except Exception:
        pass  # synthesizer_snapshots table may not exist yet
    
    report["synth_context"] = synth_context
    review_md = reviewer.weekly_review_md(report)

    # Write weekly-review.md
    os.makedirs(LEARNING_DIR, exist_ok=True)
    with open(REVIEW_PATH, "w") as f:
        f.write(review_md)

    # Append learning log to rules.md
    log_entry = reviewer.learning_log_entry(report)
    with open(RULES_PATH, "a") as f:
        f.write(log_entry + "\n")

    # Output
    if summary_only:
        # Compact Telegram-ready summary
        lines = []
        lines.append("[COMMODITY] #weekly-review")
        lines.append("")
        eq_change = report.get("equity_change_pct", 0)
        arrow = "↑" if eq_change >= 0 else "↓"
        lines.append(f"📈 Equity: ${report.get('equity_end', 100000):,.0f} ({arrow}{eq_change:+.1f}%)")
        lines.append(f"📋 {report['open_positions']} open | {report['closed_this_week']} closed this week")
        if report["closed_this_week"] > 0:
            lines.append(f"📊 Win rate: {report.get('win_rate', 0):.0f}% | P&L: ${report['total_realized_pnl']:,.2f}")
        lines.append(f"📡 {report['signals_triggered']} signals triggered, {report['signals_executed']} executed, {report['signals_missed']} missed")

        patterns = reviewer.extract_patterns(report)
        if patterns:
            lines.append("")
            lines.append("💡 **Learnings:**")
            for p in patterns[:3]:
                lines.append(f"  {p}")
        print("\n".join(lines))
    else:
        print(review_md)

    db.close()


if __name__ == "__main__":
    main()
