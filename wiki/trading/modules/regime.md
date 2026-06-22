# Gap 1 — Regime Detection: Trend / Range / Volatility Classifier

Module: regime
Signal Stack Position: Gap 1 (Regime Detection)
Data Source: Computed from OHLCV data (yfinance, KuCoin — both free, global)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (yfinance computation)

## Why This Matters

All signals are noisy without regime context. A bullish divergence in a bear trend is a trap. A bearish divergence in a bull trend is noise. The regime classifier tells you WHAT kind of market you're in before you interpret any other signal.

Three orthogonal dimensions:
1. **Trend** — Is price making higher highs/lows or lower? (trending vs ranging)
2. **Volatility** — Is price moving a lot or a little? (explosive vs quiet)
3. **Momentum** — Is the trend accelerating or decelerating?

Answer these three questions first. Then interpret every other signal through that lens.

## Key Metrics

### Trend Detection (ADX — Average Directional Index)
| ADX Value | Regime | Meaning |
|-----------|--------|---------|
| 0-20 | Ranging / Choppy | No trend. Mean reversion strategies favored. Fade breakouts. |
| 20-25 | Trend emerging | Potential trend starting. Wait for confirmation (>25). |
| 25-40 | Strong trend | Trend-following strategies favored. Buy pullbacks in trend direction. |
| 40-60 | Very strong trend | Parabolic. Trail stops tightly. Trend exhaustion possible. |
| >60 | Rare — unsustainable | Trend about to break. Prepare for reversal or deep pullback. |

### Directional Bias (+DI vs -DI)
- +DI > -DI: Bullish trend direction
- -DI > +DI: Bearish trend direction
- Crossovers signal trend changes

### Volatility Regime (ATR — Average True Range)
- ATR as % of price: <2% = low vol, 2-5% = normal, >5% = high vol
- ATR expanding: volatility increasing — wider stops, smaller position size
- ATR contracting: volatility decreasing — tighter stops, breakout imminent

### Momentum (ADX Change)
- ADX rising: trend strengthening. Hold trending positions.
- ADX falling: trend weakening. Tighten stops. Prepare for regime change.
- ADX flat + low: persistent range. Play the range boundaries.

## Composite Regime Classification

```
REGIME           ADX    ATR/Price  +DI vs -DI    Strategy
─────────────────────────────────────────────────────────
STRONG BULL      25-40  Any        +DI > -DI     Trend-follow long. Buy pullbacks.
WEAK BULL        20-25  Any        +DI > -DI     Light long. Tight stops. Wait for ADX >25.
STRONG BEAR      25-40  Any        -DI > +DI     Trend-follow short. Sell rallies.
WEAK BEAR        20-25  Any        -DI > +DI     Light short. Tight stops.
HIGH-VOL RANGE   0-20   ATR > 5%   Near flat     Stay flat. Too choppy to trade.
LOW-VOL RANGE    0-20   ATR < 2%   Near flat     Mean reversion at support/resistance.
QUIET BULL       25-40  ATR < 2%   +DI > -DI     Steady uptrend. Best regime for entries. Size up.
QUIET BEAR       25-40  ATR < 2%   -DI > +DI     Steady downtrend. Size up on shorts.
VOLATILE BULL    25-40  ATR > 5%   +DI > -DI     Trending but wild. Reduce size 50%. Wide stops.
TRANSITIONING    20-25  Expanding   Crossover      Regime change. Wait. Don't trade the transition.
```

## Confluence Rules

### With Layer 2 (Derivatives)
```
IF regime = QUIET BULL (ADX 25-40, low vol, +DI > -DI)
   AND funding rate neutral (not crowded)
   → Best entry regime. Size up on pullbacks to MA.
   → This is where institutional accumulation happens quietly.

IF regime = HIGH-VOL RANGE
   AND funding rate extreme (>0.05% or <-0.03%)
   → Crowd is fighting. No edge for either side.
   → Stay flat. Don't trade. Preserve capital.
```

### With Layer 5 (On-Chain)
```
IF regime = STRONG BEAR (ADX 25-40, -DI > +DI)
   BUT exchange outflows surging, reserves falling
   → Regime says bear, on-chain says accumulation
   → DIVERGENCE. Smart money buying the dip. Prepare for reversal.
   → Don't short into this. Wait for ADX to roll over.

IF regime = LOW-VOL RANGE (ADX < 20, low vol)
   AND exchange reserves flat, no on-chain signal
   → Nothing is happening on-chain or in price.
   → Stay flat. Don't force a trade where there's no edge.
```

### With Layer 3 (Options)
```
IF regime = VOLATILE BULL (ADX 25-40, ATR > 5%)
   AND IV skew bullish (calls expensive)
   → Euphoric trend. IV is pricing continuation.
   → Reduce size. Trend can continue but risk/reward is worsening.

IF regime = LOW-VOL RANGE
   AND IV skew extreme in either direction
   → Options market pricing a breakout. Price not confirming yet.
   → Potential opportunity: buy straddle/strangle before breakout.
```

### With All Entry Signals (Universal Rule)
```
REGIME OVERRIDE (applies to ALL theses, ALL entry signals):

IF regime = HIGH-VOL RANGE → NO ENTRIES. Period.
IF regime = TRANSITIONING  → NO ENTRIES. Wait for confirmation.
IF regime = STRONG TREND   → Enter only in trend direction. No counter-trend.

VIOLATION: Entering a counter-trend trade in STRONG BEAR regime
           because "the signal looks good" = most common losing trade.
```

## Divergence Signals (Higher Priority)

```
🔴 PRICE ↑ (making new highs) BUT ADX falling
   → Trend is weakening from within. Divergence.
   → Reduce position. Trail stops. Don't add.

🔴 PRICE ↑ BUT ATR expanding rapidly
   → Blow-off top characteristics. Euphoria.
   → Exit 50%. The last 20% of a trend is the most dangerous.

🔴 ADX CROSSING BELOW 25 after being above 40
   → Strong trend ending. Regime change from trending to ranging.
   → Exit trend-following positions. Switch to range-trading or stay flat.

🔴 +DI/-DI CROSSOVER (bull→bear or bear→bull)
   → Trend reversal signal. Wait 2-3 candles for confirmation.
   → If confirmed, reverse position direction.

🔴 LOW-VOL RANGE PERSISTING >30 DAYS
   → Coiling spring. When it breaks, the move will be explosive.
   → Don't predict direction. Wait for breakout, THEN enter in breakout direction.
   → The first move out of a 30+ day range is the most reliable trade.
```

## How to Query (Python)

```python
import yfinance as yf
import numpy as np

def compute_adx(high, low, close, period=14):
    """Compute ADX, +DI, -DI."""
    tr = np.maximum(high - low,
                    np.maximum(abs(high - close.shift()),
                               abs(low - close.shift())))
    atr = tr.rolling(period).mean()

    up_move = high - high.shift()
    down_move = low.shift() - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()

    return adx, plus_di, minus_di

# Fetch data and compute regime
btc = yf.download("BTC-USD", period="60d", progress=False)
adx, plus_di, minus_di = compute_adx(btc["High"], btc["Low"], btc["Close"])

current_adx = adx.iloc[-1]
atr_pct = (tr.rolling(14).mean().iloc[-1] / btc["Close"].iloc[-1]) * 100
direction = "BULL" if plus_di.iloc[-1] > minus_di.iloc[-1] else "BEAR"

print(f"ADX: {current_adx:.1f} | ATR%: {atr_pct:.1f}% | Direction: {direction}")

# Classify regime
if current_adx < 20:
    regime = "HIGH-VOL RANGE" if atr_pct > 5 else "LOW-VOL RANGE"
elif current_adx < 25:
    regime = f"WEAK {direction} (transitioning)"
elif current_adx < 40:
    vol_adj = "QUIET" if atr_pct < 2 else ("VOLATILE" if atr_pct > 5 else "")
    regime = f"{vol_adj} {direction}".strip()
else:
    regime = f"STRONG {direction} (exhaustion risk)"
print(f"Regime: {regime}")
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via TradingView ADX indicator |
| v1 | Python script computes daily ADX/ATR regime → vault tracker |
| v2 | Integrated into daily signal check — header: "Regime: QUIET BULL" |
| v3 | Regime override in engine: HIGH-VOL RANGE + TRANSITIONING block all entries |
| v4 | Regime history tracked — backtest which regimes produce best signal performance |

## Integration with Thesis Checklist

When a thesis uses this layer:
- [ ] Add ADX/ATR computation to fetch-prices.py or daily data script
- [ ] Display regime as first line of daily signal check: `Regime: [STRONG BULL / LOW-VOL RANGE / etc]`
- [ ] Implement regime override in engine: block entries in hostile regimes
- [ ] Add "regime quality" to confluence scoring:
  - +1 if QUIET BULL/BEAR (best trading regimes)
  - 0 if STRONG BULL/BEAR or LOW-VOL RANGE
  - -1 if HIGH-VOL RANGE or TRANSITIONING

## Notes

- ADX uses 14 periods by default. For crypto, 10-period ADX may be more responsive.
- ADX tells you trend STRENGTH, not direction. Direction comes from +DI/-DI.
- ATR as % of price matters more than raw ATR. $1,000 ATR on $100K BTC = 1% (normal). $1,000 ATR on $5K ETH = 20% (wild).
- The most common trading mistake: trading trend-following signals in ranging regimes.
- Regime changes are where money is lost. When ADX drops below 25, exit trend positions.
- Crypto regimes change faster than equity regimes. A 14-day regime in crypto ≈ 2-month regime in equities.
