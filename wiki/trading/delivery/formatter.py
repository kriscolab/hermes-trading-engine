#!/usr/bin/env python3
"""
Delivery Formatter — v8d
==========================
Standardized message formatting for all cron outputs.
Three modes: alert (urgent), digest (daily), report (weekly).

Usage:
    from delivery.formatter import DeliveryFormatter
    fmt = DeliveryFormatter()
    msg = fmt.signal_check(entry_signals, exit_signals, confluence, portfolio)
    # Returns a Telegram-ready formatted string.

Principles:
  - Consistent tag system: [CATEGORY] #hashtag
  - Emoji legend same across all messages
  - Automatic IST timestamps
  - Truncation at Telegram's 4096 char limit
  - Configurable destination (group vs DM vs vault)
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ── Constants ──
TELEGRAM_CHAR_LIMIT = 3800  # Conservative (4096 max, leave buffer)
SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━━━━"


class DeliveryFormatter:
    """Standardized message formatting for all platform outputs."""

    # Category → tag mapping
    CATEGORY_TAGS = {
        "signal":     "[SIGNAL] #signal-check",
        "trader":     "[COMMODITY] #weekly-tracker",
        "portfolio":  "[COMMODITY] #portfolio-summary",
        "confluence": "[SIGNAL] #confluence-analysis",
        "review":     "[COMMODITY] #weekly-review",
        "audit":      "[AUDIT] #missed-opportunities",
        "synthesis":  "[SYNTHESIS] #daily-state",
        "alert":      "[ALERT] #urgent",
        "system":     "[SYSTEM] #status",
        "ai":         "[AI] #ai-supercycle",
        "crypto":     "[CRYPTO] #crypto-native",
    }

    # Emoji legend — consistent across all messages
    EMOJI = {
        "firing": "🔴",
        "watching": "🟡",
        "idle": "🟢",
        "done": "✅",
        "alert": "🚨",
        "urgent": "🔴",
        "info": "💡",
        "win": "✅",
        "loss": "❌",
        "flat": "➖",
        "up": "↑",
        "down": "↓",
        "long": "🟢",
        "short": "🔴",
        "bullish": "📈",
        "bearish": "📉",
        "neutral": "➡️",
        "risk": "⚠️",
        "gap": "📭",
    }

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _ist_now() -> str:
        """Return current time in IST format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M IST")

    @staticmethod
    def _ist_date() -> str:
        """Return current date in IST format."""
        return datetime.now().strftime("%A, %B %d, %Y")

    @staticmethod
    def _truncate(text: str, limit: int = TELEGRAM_CHAR_LIMIT) -> str:
        """Truncate to Telegram-safe length."""
        if len(text) <= limit:
            return text
        return text[:limit - 20] + "\n\n... (truncated)"

    @staticmethod
    def _tag(category: str) -> str:
        """Get the standardized tag for a category."""
        return DeliveryFormatter.CATEGORY_TAGS.get(category, f"[{category.upper()}]")

    # ── Mode: ALERT (urgent, short, high-priority) ───────────────────

    def alert(self, title: str, body: str, level: str = "info",
              category: str = "alert") -> str:
        """
        Urgent alert format. For X1 (Hormuz), X5 (regulatory), etc.
        """
        emoji = self.EMOJI.get(level, "💡")
        lines = [
            f"{emoji} {self._tag(category)}",
            f"**{title}**",
            "",
            body,
            "",
            f"_{self._ist_now()}_",
        ]
        return self._truncate("\n".join(lines))

    # ── Mode: DIGEST (daily summary, multiple sections) ──────────────

    def digest(self, sections: List[Tuple[str, str]], title: str = None,
               category: str = "signal") -> str:
        """
        Daily digest with multiple sections.
        sections: list of (section_header, section_body) tuples.
        """
        date = self._ist_date()
        header = title or f"📡 Daily Check — {date}"

        lines = [header, SEPARATOR, self._tag(category), ""]

        for header, body in sections:
            if body:
                lines.append(f"{header}")
                lines.append(body)
                lines.append("")

        lines.append(f"💡 _Generated {self._ist_now()}_")
        return self._truncate("\n".join(lines))

    # ── Mode: REPORT (weekly detailed, full analysis) ────────────────

    def report(self, title: str, blocks: List[Tuple[str, str]],
               category: str = "review") -> str:
        """
        Weekly full report. blocks: list of (block_title, block_content).
        Each block gets a separator.
        """
        date = self._ist_date()
        lines = [
            f"📊 {title} — {date}",
            SEPARATOR,
            self._tag(category),
            "",
        ]

        for block_title, block_content in blocks:
            lines.append(f"─── {block_title} ───")
            lines.append(block_content)
            lines.append("")

        lines.append(f"_Generated {self._ist_now()}_")
        return self._truncate("\n".join(lines))

    # ── Specialized Formatters ───────────────────────────────────────

    def signal_check(self, entry_signals: Dict[str, str],
                     exit_signals: Dict[str, str],
                     confluence: Optional[str] = None,
                     portfolio: Optional[str] = None,
                     note: str = "") -> str:
        """
        Daily signal check format.
        
        entry_signals: {"E1": "🟢 idle", "E2": "🟡 WATCH", ...}
        exit_signals:  {"X1": "🟢 idle", "X2": "🟢 idle", ...}
        """
        date = self._ist_date()
        lines = [f"📡 Daily Signal Check — {date}", SEPARATOR, self._tag("signal"), ""]

        # Entry
        lines.append("**ENTRY:**")
        entry_str = " | ".join(f"{icon} {sig}" for sig, icon in entry_signals.items())
        lines.append(entry_str)

        # Exit
        lines.append("")
        lines.append("**EXIT:**")
        exit_str = " | ".join(f"{icon} {sig}" for sig, icon in exit_signals.items())
        lines.append(exit_str)

        # Confluence
        if confluence:
            lines.append("")
            lines.append("─── Confluence ───")
            lines.append(confluence)

        # Portfolio
        if portfolio:
            lines.append("")
            lines.append("─── Portfolio ───")
            lines.append(portfolio)

        # Note
        if note:
            lines.append("")
            lines.append(f"💡 {note}")

        lines.append("")
        lines.append(f"_{self._ist_now()}_")
        return self._truncate("\n".join(lines))

    def weekly_tracker(self, mun7_pct: float, mag7_pct: float,
                       winner: str, spread: float,
                       brent: float, brent_change: float,
                       gold: float, dxy: float, dxy_dir: str,
                       signals: Optional[str] = None,
                       portfolio: Optional[str] = None,
                       note: str = "") -> str:
        """Weekly price tracker format."""
        date = self._ist_date()
        winner_emoji = "🏆" if "Mun7" in winner else "🔵"

        lines = [
            f"📊 Weekly Tracker — {date}",
            SEPARATOR,
            self._tag("trader"),
            "",
            f"🔴 **MUN7 BASKET:** {mun7_pct:+.1f}%",
            f"🔵 **MAG7 BASKET:** {mag7_pct:+.1f}%",
            "",
            f"{winner_emoji} **Winner: {winner}** by {spread:.1f}pp",
            "",
            f"🛢 Brent: ${brent:,.2f} ({brent_change:+.1f}%)",
            f"🥇 Gold: ${gold:,.0f} | DXY: {dxy:.2f} ({dxy_dir})",
        ]

        if signals:
            lines.append("")
            lines.append("─── Signals ───")
            lines.append(signals)

        if portfolio:
            lines.append("")
            lines.append("─── Portfolio ───")
            lines.append(portfolio)

        if note:
            lines.append("")
            lines.append(f"💡 {note}")

        return self._truncate("\n".join(lines))

    def confluence_report(self, signal_id: str, name: str,
                          confidence: str, checks: List[Tuple[str, str]],
                          recommendation: str) -> str:
        """Confluence analysis block (used within signal check)."""
        lines = [
            f"**{signal_id} — {name}**",
            f"Confidence: {confidence}",
            "",
        ]
        for icon, msg in checks:
            lines.append(f"  {icon} {msg}")
        lines.append("")
        lines.append(recommendation)
        return "\n".join(lines)

    def portfolio_snapshot(self, cash: float, deployed: float,
                           equity: float, realized: float = 0,
                           unrealized: float = 0,
                           positions: List[str] = None) -> str:
        """Portfolio snapshot block."""
        deploy_pct = (deployed / (cash + deployed)) * 100 if (cash + deployed) > 0 else 0
        upnl_str = f"${unrealized:+,.2f}"

        lines = [
            f"💰 Cash ${cash:,.0f} | Deployed ${deployed:,.0f} ({deploy_pct:.0f}%)",
            f"💵 Realized ${realized:+,.0f} | 📉 Unrealized {upnl_str}",
            f"📈 Equity ${equity:,.0f}",
        ]

        if positions:
            lines.append("")
            for p in positions:
                lines.append(p)

        return "\n".join(lines)

    def position_line(self, direction: str, symbol: str, shares: float,
                      entry_price: float, current_price: float = None,
                      signal: str = "", unrealized_pnl: float = None) -> str:
        """Single position line with optional mark-to-market."""
        dir_emoji = self.EMOJI.get(direction.lower(), "🟢")
        line = f"{dir_emoji} {direction.upper()} {symbol}: {shares:.2f} sh @ ${entry_price:,.2f}"

        if current_price:
            change_pct = ((current_price - entry_price) / entry_price * 100)
            if direction.lower() == "short":
                change_pct = -change_pct
            arrow = self.EMOJI["up"] if (
                (direction.lower() == "long" and current_price >= entry_price) or
                (direction.lower() == "short" and current_price <= entry_price)
            ) else self.EMOJI["down"]

            line += f" → ${current_price:,.2f} ({arrow} {change_pct:+.1f}%)"

        if unrealized_pnl is not None:
            upnl_str = f"+${unrealized_pnl:,.2f}" if unrealized_pnl >= 0 else f"-${abs(unrealized_pnl):,.2f}"
            line += f" [{upnl_str}]"

        if signal:
            line += f" [{signal}]"

        return line

    def missed_audit(self, missed_count: int, total_checks: int,
                     wins: int = 0, losses: int = 0,
                     missed_pnl: float = 0,
                     opportunities: List[str] = None) -> str:
        """Missed opportunity audit format."""
        missed_rate = missed_count / total_checks * 100 if total_checks > 0 else 0
        icon = "🔴" if missed_rate > 10 else ("🟡" if missed_rate > 5 else "🟢")

        lines = [
            self._tag("audit"),
            "",
            f"{icon} **{missed_count} missed** / {total_checks} checks ({missed_rate:.0f}%)",
        ]

        if missed_count > 0:
            pnl_str = f"+${missed_pnl:,.2f}" if missed_pnl >= 0 else f"-${abs(missed_pnl):,.2f}"
            lines.append(f"Backtest: {wins}W / {losses}L — hypothetical P&L: {pnl_str}")

            if opportunities:
                lines.append("")
                for opp in opportunities[:5]:
                    lines.append(f"   {opp}")

            if wins > losses and missed_pnl > 0:
                lines.append("")
                lines.append("💡 Consider lowering execution threshold.")
            elif losses > wins:
                lines.append("")
                lines.append("💡 Filter working correctly — missed losses avoidable.")

        return "\n".join(lines)

    def learning_summary(self, equity_change: float, open_count: int,
                         closed_count: int, win_rate: float = 0,
                         signals_triggered: int = 0,
                         signals_missed: int = 0,
                         patterns: List[str] = None) -> str:
        """Weekly learning loop summary."""
        arrow = self.EMOJI["up"] if equity_change >= 0 else self.EMOJI["down"]
        lines = [
            self._tag("review"),
            "",
            f"📈 Equity: {arrow}{equity_change:+.1f}%",
            f"📋 {open_count} open | {closed_count} closed",
        ]

        if closed_count > 0:
            lines.append(f"📊 Win rate: {win_rate:.0f}%")

        lines.append(f"📡 {signals_triggered} triggered, {signals_missed} missed")

        if patterns:
            lines.append("")
            lines.append("💡 **Learnings:**")
            for p in patterns[:3]:
                lines.append(f"  {p}")

        return "\n".join(lines)

    def daily_synthesis(self, regime: str, composite: int,
                        risk: str, risk_severity: str,
                        thesis_actions: Dict[str, str],
                        divergences: int = 0,
                        data_gaps: int = 0) -> str:
        """Daily state synthesis summary."""
        score_icon = "📈" if composite > 0 else ("📉" if composite < 0 else "➡️")

        lines = [
            self._tag("synthesis"),
            "",
            f"🌍 Regime: **{regime}** | Score: {score_icon} **{composite:+d}**",
            f"{self.EMOJI['risk']} Risk: **{risk}** ({risk_severity})",
            "",
        ]

        for thesis, action in thesis_actions.items():
            lines.append(f"  {thesis}: {action}")

        if divergences > 0:
            lines.append(f"  Divergences: {divergences}")
        if data_gaps > 0:
            lines.append(f"  Data gaps: {data_gaps}")

        return "\n".join(lines)


# ── CLI (for testing) ──────────────────────────────────────────────────

def main():
    fmt = DeliveryFormatter()

    # Test signal check
    print("=== SIGNAL CHECK ===")
    print(fmt.signal_check(
        entry_signals={"E1": "🟢", "E2": "🟡", "E3": "🟢", "E4S": "✅", "E4L": "🟢"},
        exit_signals={"X1": "🟢", "X2": "🟢", "X3": "🟢", "X4": "🟢", "X5": "🟢"},
        portfolio=fmt.portfolio_snapshot(95001, 4999, 100000, unrealized=0,
            positions=[fmt.position_line("short", "GLD", 11.98, 417.29, 417.29, "E4S")]),
        note="No new triggers. E2 Brent $0.74 from $110 breakout."
    ))
    print()

    # Test alert
    print("=== ALERT ===")
    print(fmt.alert("Hormuz Reopens", "Credible reports of Strait of Hormuz reopening. Exit all Mun7 positions.", "urgent"))
    print()

    # Test weekly tracker
    print("=== WEEKLY ===")
    print(fmt.weekly_tracker(2.3, -1.8, "Mun7", 4.1, 109.26, 1.2, 4561, 99.27, "→"))


if __name__ == "__main__":
    main()
