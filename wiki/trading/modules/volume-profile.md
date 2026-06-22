# Layer 1 — Volume Profile: VWAP + Volume-at-Price Estimation

Module: volume-profile
Signal Stack Position: Layer 1 (Market Structure — Secondary)
Data Source: yfinance (daily OHLCV, free) + Twelve Data (indicators)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (yfinance computation). TPO/PoC limited without tick data.

## Why This Matters

Volume shows where the market actually traded, not where it was quoted. VWAP tells you the fair value — institutions use it as their benchmark. Volume-at-price shows where the most conviction exists (Point of Control). This layer answers: "Is the current price above or below where most volume has traded?"

For crypto: VWAP is heavily used by institutional desks. A break above VWAP with volume = trend change. A failure at VWAP = continuation of prior trend.

## Data Limitation (Honest)

**True tick-level volume profile (TPO, Market Profile) requires paid data.** Free sources (yfinance) provide daily OHLCV with total volume but not tick-by-tick data. This module uses:

1. **VWAP (Volume-Weighted Average Price)** — Computable from OHLCV. Approximate.
2. **Volume-at-Price Estimation** — Binned from daily candles. Directional, not precise.
3. **Point of Control (PoC)** — Estimated from volume-at-price bins. Approximate.

These approximations are **directionally correct** but not tick-level precise. For a swing trading thesis (days-to-weeks), daily approximations are sufficient. For intraday scalping, this module would need paid tick data.

## Data Sources

| Source | What | Rate Limit | Key Needed |
|--------|------|-----------|------------|
| yfinance | Daily OHLCV (close, volume) | No limit | None |
| Twelve Data | ATR, VWAP indicator | 800/day | None (free apikey) |

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| VWAP | Fair value benchmark. Institutions use it. | Price > VWAP = bullish. Price < VWAP = bearish. |
| PoC (Point of Control) | Price level with most volume. Strong S/R. | Price near PoC = indecision. Break of PoC = directional. |
| Volume Surge | Unusually high volume relative to average. | >2x avg = institutional activity. Confirms any move. |
| Volume Dry-Up | Unusually low volume. Indecision before breakout. | <0.5x avg = coiling spring. Watch for breakout direction. |
| Volume Climax | Extreme volume at top/bottom. Exhaustion. | Reversal signal. Distribution/accumulation. |

## Confluence Rules

### With Price Action (L1)
```
IF bullish engulfing AND volume > 2x 20-day average
   → HIGH conviction. Volume confirms the pattern.

IF breakout above resistance AND volume surge
   → Valid breakout. Enter. Not a false breakout.

IF breakout on low volume
   → False breakout likely. Fade. Don't enter.
```

### With Regime (Gap 1)
```
IF regime = STRONG_TREND AND price > VWAP
   → Trend is valid. VWAP confirms direction. Size up.

IF regime = HIGH_VOL_RANGE AND price oscillates around VWAP
   → No edge. VWAP provides no direction. Stay out.
```

### With Derivatives (L2)
```
IF price breaks VWAP upward AND funding rate neutral
   → Spot-driven rally. Real buying, not leverage. Strong.
IF price breaks VWAP upward AND funding extremely positive
   → Leverage-driven. Fragile. Short squeeze potential.
```

### With Session Clock (Gap 2)
```
IF volume surge during London/NY overlap
   → Institutional flow. Trust the direction.
IF volume surge during Asia only
   → Retail-driven. May reverse during London.
```

## Divergence Signals

```
🔴 PRICE RISING, VOLUME FALLING
   → Bearish divergence. Rally losing steam. Distribution.
   → Momentum weakening. Prepare to exit or reduce longs.

🟢 PRICE FALLING, VOLUME FALLING
   → Selling exhaustion. No more sellers. Accumulation zone.
   → Prepare for reversal entry.

🔴 VOLUME CLIMAX AT RESISTANCE
   → Vertical blow-off top. Smart money distributing.
   → Exit longs. Potential short entry.

🟢 VOLUME CLIMAX AT SUPPORT
   → Capitulation. Smart money accumulating.
   → Long entry with stop below support.

🔴 VWAP FLAT, PRICE OSCILLATING
   → No directional edge. Market finding value.
   → Range trade only. Tight stops. No trend bets.
```

## How to Query (Python)

```python
import yfinance as yf
import numpy as np
import pandas as pd

def fetch_data(symbol, period="60d", interval="1d"):
    df = yf.download(symbol, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if df.empty:
        return None
    df.columns = [c.lower() for c in df.columns]
    return df

def compute_vwap(df):
    """Compute approximate VWAP from daily OHLCV (typical price * volume)."""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def compute_volume_profile(df, bins=20):
    """Estimate volume-at-price distribution from daily data.
    This is APPROXIMATE — true profile needs tick data."""
    prices = df[['open', 'high', 'low', 'close']].values.flatten()
    volumes = np.repeat(df['volume'].values, 4)

    price_bins = np.linspace(prices.min(), prices.max(), bins + 1)
    vol_profile = np.zeros(bins)

    for i, p in enumerate(prices):
        bin_idx = np.digitize(p, price_bins) - 1
        if 0 <= bin_idx < bins:
            vol_profile[bin_idx] += volumes[i]

    # Point of Control (price level with most volume)
    poc_idx = np.argmax(vol_profile)
    poc = (price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2

    return {
        'bins': price_bins.tolist(),
        'profile': vol_profile.tolist(),
        'poc': round(poc, 2),
        'poc_volume': round(vol_profile[poc_idx], 0),
    }

def detect_volume_anomalies(df, window=20):
    """Detect volume surge and dry-up."""
    avg_vol = df['volume'].rolling(window).mean()
    vol_ratio = df['volume'] / avg_vol

    surge = vol_ratio > 2.0
    dry_up = vol_ratio < 0.5

    return {
        'volume_ratio_latest': round(vol_ratio.iloc[-1], 2),
        'surge': bool(surge.iloc[-1]) if len(surge) else False,
        'dry_up': bool(dry_up.iloc[-1]) if len(dry_up) else False,
        'avg_volume': round(avg_vol.iloc[-1], 0) if len(avg_vol) else 0,
    }

def compute_atr(df, period=14):
    """Compute Average True Range (volatility)."""
    high, low, close = df['high'], df['low'], df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Python functions (above). Manual checks. |
| v1 | Auto-fetch daily OHLCV, compute VWAP + volume anomalies |
| v2 | Integrate with engine: volume confirmation for signal entry |
| v3 | TradingView webhook: real-time Volume Profile indicator alerts |
| v4 | Tick data via paid provider for true TPO/PoC (future) |

## Integration with Thesis Checklist

- [ ] Commodity thesis: XLE/GLD volume confirmation for E1/E2/E4 entries
- [ ] Crypto thesis: BTC/ETH VWAP + volume surge for confluence
- [ ] AI thesis: SOXX volume confirmation for rotation signals

## Notes

- VWAP from daily data is a rough approximation. True VWAP is intraday.
- Volume-at-price from daily candles loses granularity. POC is approximate.
- Volume surge is the highest-confidence signal. It doesn't lie.
- Volume dry-up precedes breakouts. Watch for direction.
- If you ever get tick data access, upgrade PoC calculation for precision.
