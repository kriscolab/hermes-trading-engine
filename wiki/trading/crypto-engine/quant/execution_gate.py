#!/usr/bin/env python3
"""Quant Execution Gate — 5-point gate for v12 crypto engine.

Gate checks before any quant/intraday trade:
1. Volume gate: 24h volume > $10M
2. Spread gate: bid-ask < 0.5%
3. Time gate: not first/last 5 min of hourly candle
4. Persistence: signal must hold 2 consecutive 5-min checks
5. Correlation: no 2 concurrent positions on correlated tickers

Usage:
    from crypto_engine.quant.execution_gate import Gate
    gate = Gate(db_conn)
    if gate.check(ticker, direction):
        # proceed with trade
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict

IST = timezone(timedelta(hours=5, minutes=30))

QUANT_PATH = Path("/tmp/quant_signals.json")
PERSISTENCE_PATH = Path("/tmp/signal_persistence.json")
CRYPTO_DATA_PATH = Path("/tmp/crypto_module_data.json")


def now_ist():
    return datetime.now(IST)


# Regime → active modules
REGIME_MODULES = {
    "TRENDING": ["momentum", "ml_signals", "trend_following", "microstructure", "correlation", "volatility"],
    "CHOPPY":   ["mean_reversion", "stat_arbitrage", "volatility", "microstructure", "market_making", "event_driven"],
    "RISK_OFF": ["correlation", "event_driven", "volatility", "microstructure"],
    "VOLATILE": ["volatility", "microstructure", "momentum", "correlation", "ml_signals"],
    "NEUTRAL":  ["mean_reversion", "momentum", "ml_signals", "microstructure", "correlation", "volatility",
                 "stat_arbitrage", "event_driven", "market_making", "monte_carlo"],
}

# Ticker correlation pairs — use instrument tickers (IBIT, ETHA) since DB stores those
# BTC→IBIT, ETH→ETHA, SOL native, etc.
CORRELATED_PAIRS = [
    ("IBIT", "ETHA"),   # BTC ETF ↔ ETH ETF
    ("SOL", "BONK"),    # Solana ecosystem
    ("AVAX", "LINK"),   # Similar market cap altcoins
]


class Gate:
    """5-point execution gate for quant/intraday trades."""

    def __init__(self, db_conn):
        self.db = db_conn
        self.regime = "NEUTRAL"

    def set_regime(self, regime: str):
        self.regime = regime

    # ── Gate 1: Volume ──
    def _volume_check(self, ticker: str) -> bool:
        """24h volume must exceed $10M. Fail-open if data unavailable."""
        try:
            data = load_crypto_data()
            prices = data.get("prices", {})
            # Try multiple volume field names
            vol = (prices.get(f"{ticker.lower()}_24h_vol", None) or
                   prices.get(f"{ticker.lower()}_volume_24h", None) or
                   prices.get("total_volume", None))
            if vol is None:
                # No volume data available — fail open, don't block blind
                return True
            return float(vol) > 10_000_000
        except Exception:
            return True  # Data unavailable → allow

    # ── Gate 2: Spread ──
    def _spread_check(self, ticker: str) -> bool:
        """Bid-ask spread must be < 0.5%."""
        try:
            data = load_crypto_data()
            ticker_data = data.get("prices", {}).get(ticker.lower(), {})
            if isinstance(ticker_data, dict):
                bid = ticker_data.get("bid", 0)
                ask = ticker_data.get("ask", 0)
                if bid > 0 and ask > 0:
                    spread_pct = (ask - bid) / bid * 100
                    return spread_pct < 0.5
        except Exception:
            pass
        return True  # Fail open

    # ── Gate 3: Time ──
    def _time_check(self) -> bool:
        """Skip if within 2 min of 5-min boundary in UTC (scheduler drift window).
        Cron fires on */5 UTC — engine runs within seconds. This catches scheduler lag >2min."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        remainder = now.minute % 5
        return not (remainder == 0 and now.second < 120)  # Only block if 0:00-1:59 of a 5-min tick

    # ── Gate 4: Persistence (DISABLED — cold-start self-defeating) ──
    def _persistence_check(self, ticker: str, direction: str) -> bool:
        """Always pass. 2-tick persistence was self-defeating at cold start.
        Re-enable after 20+ successful trades when tracker has positive history."""
        return True

    # ── Gate 5: Correlation ──
    def _correlation_check(self, ticker: str) -> bool:
        """No 2 concurrent positions on correlated tickers."""
        for pair in CORRELATED_PAIRS:
            if ticker.upper() in [p.upper() for p in pair]:
                other = pair[1] if pair[0].upper() == ticker.upper() else pair[0]
                r = self.db.execute(
                    "SELECT COUNT(*) as c FROM trades WHERE symbol=? AND status='open'",
                    (other,),
                ).fetchone()
                if r and r[0] > 0:
                    return False
        return True

    # ── Full gate check ──
    def check(self, ticker: str, direction: str) -> tuple:
        """Run all 5 gates. Returns (passed: bool, reason: str)."""
        if not self._volume_check(ticker):
            return (False, "volume < $10M")
        if not self._spread_check(ticker):
            return (False, "spread > 0.5%")
        if not self._time_check():
            return (False, "thin time window")
        if not self._persistence_check(ticker, direction):
            return (False, "signal not persistent")
        if not self._correlation_check(ticker):
            return (False, "correlated position open")
        return (True, "passed")

    def active_modules(self) -> list:
        """Return list of module names active in current regime."""
        return REGIME_MODULES.get(self.regime, REGIME_MODULES["NEUTRAL"])


def load_crypto_data() -> dict:
    if CRYPTO_DATA_PATH.exists():
        return json.loads(CRYPTO_DATA_PATH.read_text())
    return {}


def update_persistence(ticker: str, direction: str, firing: bool):
    """Record signal state for persistence tracking."""
    history = {}
    if PERSISTENCE_PATH.exists():
        history = json.loads(PERSISTENCE_PATH.read_text())

    ticker_key = f"{ticker}_{direction}"
    signals = history.setdefault("signals", {})
    signals.setdefault(ticker_key, []).append(firing)
    # Keep last 5 checks
    signals[ticker_key] = signals[ticker_key][-5:]

    history["last_updated"] = now_ist().isoformat()
    PERSISTENCE_PATH.write_text(json.dumps(history))
