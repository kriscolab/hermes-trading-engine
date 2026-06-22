#!/usr/bin/env python3
"""
Intraday Engine v1.0 — Short-Term Crypto Trading
===================================================
Uses the base system's ticker screening (ensemble scores, MC validation, regime)
to select top candidates, then runs technical analysis on 5-min candles for
intraday entry signals.

Pipeline:
  1. Screen: Top 3 tickers by ensemble score (must have MC passed)
  2. Regime filter: Only TRENDING or RISK_ON
  3. Fetch: 5-min candles for last 4 hours
  4. TA: VWAP, Support/Resistance, RSI(14), Volume ratio
  5. Signal: Pullback-to-VWAP (bullish) or breakout-above-resistance
  6. Risk: -2% stop, +3% TP, 4-hour max hold, 5% allocation

Output: /tmp/intraday_signals.json — consumed by engine.py (INTRADAY signals)

Usage:
    python3 intraday-engine.py              # Full scan → signal generation
    python3 intraday-engine.py --summary    # Compact output
    python3 intraday-engine.py --json       # JSON only
"""

import sys
import json
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yfinance as yf
except ImportError:
    print("yfinance required: pip install yfinance", file=sys.stderr)
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    pd = None  # will be imported later in main() if needed

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent.parent
QUANT_PATH = Path("/tmp/quant_signals.json")
SYNTH_PATH = TRADING_DIR / "synthesis" / "daily_state.json"
SIGNAL_PATH = Path("/tmp/intraday_signals.json")

# ── Parameters ──
TOP_N = 3              # Top N tickers by ensemble score
CANDLE_INTERVAL = "5m" # 5-minute candles
LOOKBACK_HOURS = 4     # How many hours of data to fetch
RSI_PERIOD = 14        # RSI lookback
STOP_PCT = -0.02       # -2% stop
TP_PCT = 0.03          # +3% take profit
ALLOC_PCT = 0.05       # 5% per trade
VWAP_BAND = 0.01       # Within 1% of VWAP for pullback entry


def screen_tickers() -> List[Dict]:
    """Select top N tickers from ensemble with MC passed, regime filter."""
    candidates = []
    
    # Read ensemble
    if not QUANT_PATH.exists():
        return candidates
    qd = json.loads(QUANT_PATH.read_text())
    ens = qd.get("ensemble", {}).get("signals", {})
    qs = qd.get("signals", {})
    
    # Read regime
    regime = "NEUTRAL"
    if SYNTH_PATH.exists():
        try:
            synth = json.loads(SYNTH_PATH.read_text())
            regime = synth.get("market_regime", {}).get("primary", "NEUTRAL")
        except Exception: pass
    
    # Regime-aware filtering (v1.1): 
    # ALL regimes now allow trading — the direction is regime-adaptive.
    # RISK_OFF → short-only. MEAN_REVERTING → long+short. TRENDING/RISK_ON → all.
    short_only = (regime == "RISK_OFF")
    
    # Score tickers
    scored = []
    for ticker, meta in ens.items():
        score = meta.get("ensemble_score", 0)
        direction = meta.get("direction", "NEUTRAL")
        # Check MC gate — relaxed: TA entries have their own validation
        mc = qs.get(ticker, {}).get("monte-carlo", {})
        mc_passed = mc.get("is_significant", True)  # default True for TA-based entries
        
        # v1.2: Lowered from 0.2→0.05 (May 30) — quant ensemble producing weaker scores in current regime
        if abs(score) >= 0.05 and direction != "NEUTRAL":
            scored.append((score, ticker, direction, mc_passed))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    
    for score, ticker, direction, mc_pass in scored[:TOP_N]:
        # Regime-adaptive direction filter
        if short_only and direction != "BEARISH":
            continue  # RISK_OFF: only short candidates
        candidates.append({
            "ticker": ticker,
            "ensemble_score": score,
            "direction": direction,
            "mc_passed": mc_pass,
            "regime": regime,
        })
    
    return candidates


def fetch_candles(symbol: str) -> Optional[Dict]:
    """Fetch 5-min candles for a ticker."""
    try:
        ticker_yf = f"{symbol}-USD" if "-" not in symbol else symbol
        df = yf.download(ticker_yf, period="1d", interval=CANDLE_INTERVAL,
                        progress=False, auto_adjust=True)
        if df.empty or len(df) < RSI_PERIOD + 5:
            return None
        
        # Flatten multi-index
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        closes = df["Close"].values
        highs = df["High"].values
        lows = df["Low"].values
        volumes = df["Volume"].values
        
        return {
            "close": closes,
            "high": highs,
            "low": lows,
            "volume": volumes,
            "current": float(closes[-1]),
        }
    except Exception:
        return None


def compute_vwap(candles: Dict) -> float:
    """Compute VWAP from candles."""
    closes = candles["close"]
    highs = candles["high"]
    lows = candles["low"]
    volumes = candles["volume"]
    
    typical = (highs + lows + closes) / 3
    vwap = np.sum(typical * volumes) / np.sum(volumes) if np.sum(volumes) > 0 else closes[-1]
    return float(vwap)


def compute_rsi(closes: np.ndarray, period: int = RSI_PERIOD) -> float:
    """Compute RSI(14)."""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-period-1:])
    gains = np.sum(deltas[deltas > 0]) if np.any(deltas > 0) else 0
    losses = -np.sum(deltas[deltas < 0]) if np.any(deltas < 0) else 0
    if losses == 0:
        return 100.0
    rs = gains / losses
    return float(100 - (100 / (1 + rs)))


def compute_sr_levels(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> Dict:
    """Find support and resistance from recent price action."""
    recent = closes[-20:] if len(closes) >= 20 else closes
    support = float(np.min(lows[-20:])) if len(lows) >= 20 else float(np.min(lows))
    resistance = float(np.max(highs[-20:])) if len(highs) >= 20 else float(np.max(highs))
    return {"support": support, "resistance": resistance}


def analyze_ticker(ticker: str, direction: str) -> Optional[Dict]:
    """Run technical analysis and generate signals."""
    candles = fetch_candles(ticker)
    if candles is None:
        return None
    
    current = candles["current"]
    closes = candles["close"]
    highs = candles["high"]
    lows = candles["low"]
    
    vwap = compute_vwap(candles)
    rsi = compute_rsi(closes)
    sr = compute_sr_levels(highs, lows, closes)
    
    # Volume check
    avg_vol = float(np.mean(candles["volume"][-20:])) if len(candles["volume"]) >= 20 else float(np.mean(candles["volume"]))
    last_vol = float(candles["volume"][-1])
    vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0
    
    # Signal logic
    signal = None
    entry_price = current
    reasoning = ""
    
    if direction == "BULLISH":
        # Entry: pullback to VWAP (within 1%)
        near_vwap = abs(current - vwap) / vwap < VWAP_BAND
        # Entry: breakout above resistance
        breakout = current > sr["resistance"] * 0.995
        
        if near_vwap and rsi < 50 and vol_ratio > 0.8:
            signal = "INTRADAY_LONG"
            entry_price = current
            reasoning = f"Bullish pullback to VWAP (RSI={rsi:.0f}, vol={vol_ratio:.1f}x)"
        elif breakout and vol_ratio > 1.2:
            signal = "INTRADAY_LONG"
            entry_price = current
            reasoning = f"Breakout above resistance ${sr['resistance']:.2f} (vol={vol_ratio:.1f}x)"
    
    elif direction == "BEARISH":
        near_vwap = abs(current - vwap) / vwap < VWAP_BAND
        breakdown = current < sr["support"] * 1.005
        
        if near_vwap and rsi > 50 and vol_ratio > 0.8:
            signal = "INTRADAY_SHORT"
            entry_price = current
            reasoning = f"Bearish rejection at VWAP (RSI={rsi:.0f}, vol={vol_ratio:.1f}x)"
        elif breakdown and vol_ratio > 1.2:
            signal = "INTRADAY_SHORT"
            entry_price = current
            reasoning = f"Breakdown below support ${sr['support']:.2f} (vol={vol_ratio:.1f}x)"
    
    if signal is None:
        return None
    
    return {
        "ticker": ticker,
        "signal": signal,
        "entry_price": round(entry_price, 2),
        "vwap": round(vwap, 2),
        "rsi": round(rsi, 1),
        "support": round(sr["support"], 2),
        "resistance": round(sr["resistance"], 2),
        "vol_ratio": round(vol_ratio, 2),
        "stop_loss": round(entry_price * (1 + STOP_PCT), 2),
        "take_profit": round(entry_price * (1 + TP_PCT), 2),
        "max_hold_hours": 4,
        "allocation_pct": ALLOC_PCT * 100,
        "reasoning": reasoning,
    }


def generate_signals() -> Dict:
    """Main: screen tickers, run TA, produce signals."""
    candidates = screen_tickers()
    signals = []
    
    for c in candidates:
        result = analyze_ticker(c["ticker"], c["direction"])
        if result:
            result["ensemble_score"] = c["ensemble_score"]
            result["regime"] = c["regime"]
            signals.append(result)
    
    output = {
        "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "candidates_screened": len(candidates),
        "signals_generated": len(signals),
        "signals": signals,
    }
    
    SIGNAL_PATH.write_text(json.dumps(output, indent=2))
    return output


def main():
    import pandas as pd  # needed by yfinance internals
    
    output = generate_signals()
    
    if "--json" in sys.argv:
        print(json.dumps(output, indent=2))
        return
    
    print(f"⚡ Intraday Engine v1.0")
    print(f"   Screened: {output['candidates_screened']} | Signals: {output['signals_generated']}")
    
    if not output["candidates_screened"]:
        print("   No candidates — no tickers passed ensemble threshold or regime filter")
        return
    
    for s in output["signals"]:
        icon = "🟢" if "LONG" in s["signal"] else "🔴"
        print(f"   {icon} {s['ticker']:>6s} {s['signal']:16s} @ ${s['entry_price']:,.2f}")
        print(f"      VWAP=${s['vwap']:,.2f} RSI={s['rsi']:.0f} S/R=${s['support']:,.2f}/${s['resistance']:,.2f}")
        print(f"      Stop=${s['stop_loss']:,.2f} TP=${s['take_profit']:,.2f} | {s['reasoning']}")


if __name__ == "__main__":
    main()
