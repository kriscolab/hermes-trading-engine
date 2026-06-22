# Layer 1 — Price Action: Candlestick Patterns + Support/Resistance

Module: price-action
Signal Stack Position: Layer 1 (Market Structure — Primary)
Data Source: yfinance (OHLCV, free) + Twelve Data (indicators, free tier 800 calls/day)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (yfinance computation)

## Why This Matters

Price action is the foundation. Every other layer — derivatives, options, on-chain — is derivative data. The chart itself tells you supply/demand in real time. Candlestick patterns encode market psychology. Support/resistance levels show where institutions are positioned. This layer catches reversals and breakouts before derivatives data even updates.

For crypto specifically: crypto markets are technically driven. No earnings, no Fed meetings. Patterns matter more here than in equities.

## Data Sources

| Source | What | Rate Limit | Key Needed |
|--------|------|-----------|------------|
| yfinance | OHLCV (daily, 1h) | No limit | None |
| Twelve Data | RSI, MACD, BB, ATR, Stoch | 800/day | None (free apikey) |

Note: True tick-level intraday data is not available for free. Daily and 1h candles are sufficient for swing trading theses (days-to-weeks hold). For scalping, paid data needed.

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| Doji | Indecision. Reversal possible if at S/R. | Watch for reversal |
| Engulfing (bull) | Buyers overwhelmed sellers. Trend reversal up. | Long signal if at support |
| Engulfing (bear) | Sellers overwhelmed buyers. Trend reversal down. | Short/exit signal if at resistance |
| Hammer | Rejection of lower prices. Bullish reversal. | Long signal if after downtrend |
| Shooting Star | Rejection of higher prices. Bearish reversal. | Short signal if after uptrend |
| Morning Star | 3-bar bottom reversal. Strongest bullish pattern. | Long signal |
| Evening Star | 3-bar top reversal. Strongest bearish pattern. | Short/exit signal |
| S/R Break | Price breaks support or resistance with volume | Directional entry |
| S/R Hold | Price bounces off S/R level | Mean-reversion entry |

## Confluence Rules

### With Regime Module (Gap 1)
```
IF regime = STRONG_TREND AND pattern = engulfing WITH trend
   → High confidence. Trend-confirming pattern.

IF regime = LOW_VOL_RANGE AND pattern at S/R boundary
   → Range trade. Buy at support, sell at resistance.
```

### With Session Clock (Gap 2)
```
IF pattern fires during London/NY overlap
   → Higher volume confirmation. Trust the pattern more.
IF pattern fires during Asia session only
   → Lower conviction. Wait for London confirmation.
```

### With Volume Profile (L1)
```
IF engulfing pattern AND volume > 2x 20-day average
   → HIGH conviction. Volume confirms the move.
IF pattern fires on low volume
   → LOW conviction. Fade or ignore.
```

### With Derivatives (L2)
```
IF bullish engulfing at support AND funding rate negative
   → Contrarian long. Crowd is short, price is reversing.
```

## Divergence Signals

```
🔴 PRICE MAKES HIGHER HIGH, RSI MAKES LOWER HIGH
   → Bearish divergence. Momentum weakening. Prepare to exit longs.

🟢 PRICE MAKES LOWER LOW, RSI MAKES HIGHER LOW
   → Bullish divergence. Momentum building. Prepare to enter longs.

🔴 MULTIPLE DOJIS AT RESISTANCE
   → Sellers defending. Resistance holding. Short or exit longs.

🟢 HAMMER AT SUPPORT WITH VOLUME
   → Buyers stepping in. Support confirmed. Long entry.
```

## How to Query (Python)

```python
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def fetch_ohlcv(symbol, period="60d", interval="1d"):
    """Fetch OHLCV from yfinance (free)."""
    df = yf.download(symbol, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if df.empty:
        return None
    df.columns = [c.lower() for c in df.columns]
    return df

def detect_patterns(df):
    """Detect common candlestick patterns."""
    patterns = {}
    o, h, l, c = df['open'], df['high'], df['low'], df['close']

    # Doji
    body = abs(c - o)
    range_hl = h - l
    patterns['doji'] = body <= range_hl * 0.1

    # Bullish Engulfing
    patterns['engulfing_bull'] = (
        (c > o) & (c.shift(1) < o.shift(1)) &
        (o <= c.shift(1)) & (c >= o.shift(1))
    )

    # Bearish Engulfing
    patterns['engulfing_bear'] = (
        (c < o) & (c.shift(1) > o.shift(1)) &
        (o >= c.shift(1)) & (c <= o.shift(1))
    )

    # Hammer
    lower_shadow = o - l  # for bullish candle
    patterns['hammer'] = (
        (lower_shadow > body * 2) & ((h - c) < body * 0.5)
    )

    # Shooting Star
    upper_shadow = h - o
    patterns['shooting_star'] = (
        (upper_shadow > body * 2) & ((c - l) < body * 0.5)
    )

    # Morning Star (simplified 3-bar)
    patterns['morning_star'] = (
        (c.shift(2) < o.shift(2)) &  # bar 1: bearish
        (body.shift(1) < body.median()) &  # bar 2: small body
        (c > o) & (c > (o.shift(2) + c.shift(2)) / 2)  # bar 3: bullish close above midpoint
    )

    return pd.DataFrame(patterns, index=df.index)

def find_support_resistance(df, window=20):
    """Find S/R levels using rolling pivot points."""
    highs = df['high'].rolling(window).max()
    lows = df['low'].rolling(window).min()

    resistance = highs[highs.diff() == 0].dropna()
    support = lows[lows.diff() == 0].dropna()

    return {
        'support': sorted(support.unique())[-3:],
        'resistance': sorted(resistance.unique())[-3:],
    }

def compute_rsi(df, period=14):
    """Compute RSI."""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def compute_sma(df, period):
    """Compute Simple Moving Average."""
    return df['close'].rolling(period).mean()
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Python functions (above). Manual checks. |
| v1 | Fetch daily OHLCV, detect patterns, store to /tmp |
| v2 | Twisted: cron runs daily, patterns fed to engine |
| v3 | TradingView webhooks for real-time intraday patterns |
| v4 | Monte Carlo backtesting of pattern-based entries |

## Integration with Thesis Checklist

- [ ] Commodity thesis: Brent/XLE patterns for E1/E2 confirmation
- [ ] AI thesis: SOXX/XLK patterns for rotation signals
- [ ] Crypto thesis: BTC/ETH patterns + S/R levels for L1 confluence

## Notes

- Candlestick patterns have ~55-60% win rate on their own. Confluence is essential.
- S/R levels from pivots are noisy. Use weekly/monthly pivots for stronger levels.
- Intraday patterns need TradingView webhooks for real-time data.
- Morning/Evening Stars are rare but high-conviction when they fire.
- Always check volume. A pattern without volume is noise.
