#!/usr/bin/env python3
"""Risk Manager — circuit breakers, position limits, daily loss limits.

Tracks per-engine risk events in journal_crypto.db.risk_events table.

Circuit breakers:
  3 consecutive losses → pause 30 min
  5 losses in a row → pause 2 hours
  Daily loss limit (2% of allocated capital) → PAUSE until next calendar day

Position limits:
  Max 3 concurrent positions
  Max 10 trades/day (combined quant + intraday)
  No overnight positions for intraday, no weekend positions

Usage:
    from crypto_engine.quant.risk_manager import RiskManager
    rm = RiskManager(db_conn, cap_alloc=40000)
    if rm.can_trade():
        ...
    rm.record_result(pnl)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    return datetime.now(IST)


class RiskManager:
    """Circuit breakers and position limits for quant/intraday trading."""

    def __init__(self, db_conn, cap_alloc: float = 40_000, max_positions: int = 3, max_trades_day: int = 10):
        self.db = db_conn
        self.cap_alloc = cap_alloc
        self.max_positions = max_positions
        self.max_trades_day = max_trades_day
        self.daily_loss_limit = cap_alloc * 0.02  # 2%

    def _consecutive_losses(self) -> int:
        """Count consecutive losing trades (most recent first)."""
        rows = self.db.execute(
            "SELECT pnl_realized FROM trades WHERE status='closed' AND exit_signal LIKE 'TACTICAL_%' "
            "ORDER BY exit_date DESC LIMIT 10"
        ).fetchall()
        count = 0
        for r in rows:
            if r[0] is not None and r[0] <= 0:
                count += 1
            else:
                break
        return count

    def _trades_today(self) -> int:
        """Count trades executed today."""
        today = now_ist().strftime("%Y-%m-%d")
        r = self.db.execute(
            "SELECT COUNT(*) FROM trades WHERE entry_timestamp LIKE ?",
            (f"{today}%",),
        ).fetchone()
        return r[0] if r else 0

    def _daily_loss(self) -> float:
        """Total realized loss today."""
        today = now_ist().strftime("%Y-%m-%d")
        r = self.db.execute(
            "SELECT COALESCE(SUM(pnl_realized), 0) FROM trades "
            "WHERE status='closed' AND exit_date LIKE ?",
            (f"{today}%",),
        ).fetchone()
        return float(r[0]) if r else 0.0

    def _concurrent_positions(self) -> int:
        r = self.db.execute(
            "SELECT COUNT(*) FROM trades WHERE status='open' AND entry_signal LIKE 'TACTICAL_%'"
        ).fetchone()
        return r[0] if r else 0

    def can_trade(self) -> tuple:
        """Check if trading is allowed. Returns (allowed: bool, reason: str)."""
        # Position limit
        if self._concurrent_positions() >= self.max_positions:
            return (False, f"max {self.max_positions} positions")

        # Daily trade limit
        if self._trades_today() >= self.max_trades_day:
            return (False, f"max {self.max_trades_day} trades/day")

        # Daily loss limit
        loss = self._daily_loss()
        if loss <= -self.daily_loss_limit:
            self._log_event("daily_loss_limit", f"loss=${loss:.2f} exceeds limit=${self.daily_loss_limit:.2f}")
            return (False, f"daily loss limit hit (${loss:.2f})")

        # Consecutive losses
        consec = self._consecutive_losses()
        if consec >= 5:
            self._log_event("circuit_breaker", f"{consec} consecutive losses — 2h pause")
            return (False, f"{consec} consecutive losses")

        return (True, "ok")

    def record_result(self, pnl: float, trade_id: int):
        """Record trade result. Logs risk events if thresholds breached."""
        consec = self._consecutive_losses()

        if consec == 3:
            self._log_event("pause_30m", f"{consec} consecutive losses — 30min pause", trade_id)
        elif consec == 5:
            self._log_event("pause_2h", f"{consec} consecutive losses — 2h pause", trade_id)

        daily_loss = self._daily_loss()
        if daily_loss <= -self.daily_loss_limit * 0.8:
            self._log_event("loss_warning", f"approaching daily limit: ${daily_loss:.2f}", trade_id)

    def _log_event(self, event_type: str, detail: str, trade_id: Optional[int] = None):
        """Log risk event to risk_events table."""
        t = now_ist().isoformat()
        self.db.execute(
            "INSERT INTO risk_events (event_at, event_type, detail, positions_closed) VALUES (?,?,?,?)",
            (t, event_type, detail, 0),
        )
        self.db.commit()

    def is_weekend(self) -> bool:
        """No weekend positions for intraday."""
        return now_ist().weekday() >= 5  # 5=Sat, 6=Sun

    def is_overnight_window(self) -> bool:
        """Close positions by 3:55 PM IST. No overnight."""
        h, m = now_ist().hour, now_ist().minute
        return h >= 15 and m >= 55  # Past 3:55 PM IST
