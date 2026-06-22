# Gap 6 — Position Sizing: ATR-Based + Kelly + Correlation Penalty

Module: position-sizing
Signal Stack Position: Gap 6 (Dynamic Position Sizing)
Data Source: Computed from price data (ATR, volatility, correlation)
Status: v0.1 — DEFINED, formulas in rules.md, not yet automated

## Why This Matters

Position sizing is the most underrated edge in trading. Two traders with identical signals will have different outcomes based on how they size. Too small = leave money on the table. Too big = one bad trade wipes out gains. The sizing formula must account for:
1. **Volatility** — Wider stops in high vol. Smaller position.
2. **Conviction** — More confluence layers = more capital.
3. **Correlation** — Overlapping bets concentrated = reduce size.
4. **Drawdown** — Recovering from losses requires larger % gains.

This module answers "how much should I put on this trade?" — the question that separates gambling from risk management.

## Key Formulas

### 1. ATR-Based Sizing (Short-Term / Defined Target)

```
Position Size = Risk Amount / (ATR × Multiplier)

Where:
  Risk Amount = % of portfolio you're willing to lose on this trade (e.g., 1%)
  ATR = Average True Range (14-period) in dollar terms
  Multiplier = How many ATRs away is your stop? (typically 2-3)
```

Example: $100K portfolio, 1% risk = $1,000. ATR = $2,000 on BTC. Stop at 2x ATR = $4,000.
  Position = $1,000 / ($2,000 × 2) = 0.25 BTC = ~$25,000 position size.
  If stopped out at 2x ATR, loss = $1,000 = 1% of portfolio. ✓

### 2. Kelly-Inspired Sizing (Thesis Entries)

```
f* = (p × b - q) / b    [Full Kelly — aggressive]

Simplified for thesis entries (half-Kelly):
  f = f* / 2

Where:
  f* = Optimal fraction of capital
  p  = Probability of winning (estimated from backtest or signal win rate)
  b  = Win/loss ratio (avg win / avg loss)
  q  = 1 - p

Constraint: f capped at 25% per entry, 50% per thesis total.
```

Example: Signal win rate = 60% (p=0.6), avg win = $5K, avg loss = $3K (b=1.67).
  f* = (0.6 × 1.67 - 0.4) / 1.67 = 0.36 → Half-Kelly = 18%.
  Capped at 25%. Enter at 18%.

### 3. Volatility-Adjusted Sizing

```
Adjusted Size = Base Size × (Target Vol / Current Vol)

Where:
  Target Vol = Desired daily % volatility (typically 2%)
  Current Vol = Actual daily % volatility (ATR% = ATR/Price × 100)
```

Example: Signal calls for $25K entry. Current ATR% = 4% (high vol). Target = 2%.
  Adjusted = $25K × (2/4) = $12.5K. Half the size in high vol.

### 4. Correlation Penalty

```
If Position A and Position B have correlation > 0.7:
  Combined max = 125% of single-position max (not 200%)

Example: Single position max = $25K. Two correlated positions:
  Allowed = min($25K + $25K, $25K × 1.25) = $31.25K total
  (Not $50K. Overlapping risk = concentrated exposure.)
```

## Sizing Table (Quick Reference)

| Regime | VIX/ATR | Conviction | Max Size | Notes |
|--------|---------|-----------|----------|-------|
| QUIET BULL/BEAR | VIX < 20 | HIGH (🟢) | 25% | Max thesis allocation |
| QUIET BULL/BEAR | VIX < 20 | MIXED (🟡) | 15% | Reduced on lower confidence |
| STRONG BULL/BEAR | VIX 20-25 | HIGH | 20% | Trend is strong but vol implies caution |
| STRONG BULL/BEAR | VIX 20-25 | MIXED | 10% | Trend-follow, reduced conviction |
| HIGH-VOL RANGE | VIX > 25 | Any | 0% | No entries in hostile regime |
| LOW-VOL RANGE | VIX < 15 | Any | 10% | Range trades only, smaller size |
| PANIC | VIX > 35 | Any | 0% | Cash only |

## Confluence Rules

### With Regime Module
```
IF regime = QUIET BULL + confluence = HIGH (🟢)
   → Full Kelly up to 25% max. Best possible setup.

IF regime = STRONG BULL + confluence = HIGH
   → 0.75 × Kelly. Trend is strong but vol means wider stops.

IF regime = LOW-VOL RANGE
   → 0.5 × Kelly max. Range trades have lower hit rate.
```

### With Correlation Module
```
IF BTC/SPY correlation > 0.7 AND also holding XLE/XLK positions
   → All risk-on positions are correlated. Reduce combined size.

IF ETH/BTC ratio rising (>0.06) AND holding both BTC + ETH
   → ETH outperforming = diversification benefit. Correlation penalty waived.
```

### With Session-Clock Module
```
IF entering during Asia session (low volume)
   → 0.5 × calculated size. Thin books = more slippage.

IF entering during London/NY overlap (max volume)
   → Full calculated size. Deepest liquidity.
```

### With Macro Module
```
IF VIX > 25 (elevated fear)
   → 0.5 × calculated size. Wider stops needed. Larger gap risk.

IF VIX < 15 (complacency)
   → 1.0 × calculated size. But be ready for vol expansion.
```

## Divergence Signals

```
⚠️ POSITION SIZE > 25% OF PORTFOLIO
   → Overconcentrated. Violates rules. Reduce immediately.
   → Exception: Only if single thesis with 100% allocation allowed.

⚠️ CORRELATED POSITIONS > 125% OF SINGLE MAX
   → Overlapping risk. One event hits both positions.
   → Reduce one or both positions.

⚠️ KELLY FORMULA RETURNS >40% BUT CAP IS 25%
   → High-conviction signal artificially capped.
   → Flag for review. May suggest increasing single-thesis cap.
```

## How to Compute (Python)

```python
import numpy as np
import yfinance as yf

def compute_position_size(portfolio: float, risk_pct: float,
                         entry_price: float, atr: float,
                         atr_multiplier: float = 2.0,
                         win_rate: float = 0.55,
                         avg_win_loss_ratio: float = 1.5,
                         vix: float = 20,
                         confluence_score: int = 3) -> dict:
    """
    Compute position size using ATR + Kelly + volatility adjustment.

    Returns dict with:
      - kelly_size: Kelly-derived fraction
      - atr_shares: Number of shares/contracts
      - position_value: Dollar amount
      - adjusted_value: After vol/confluence adjustments
      - max_loss: Worst case loss at stop
    """

    # 1. Kelly sizing
    p = win_rate
    b = avg_win_loss_ratio
    q = 1 - p
    kelly_full = max(0, (p * b - q) / b)
    kelly_half = kelly_full / 2

    # Cap at 25% per entry
    kelly_capped = min(kelly_half, 0.25)

    # 2. ATR stop distance
    stop_distance = atr * atr_multiplier
    risk_dollars = portfolio * (risk_pct / 100)

    # 3. Shares calculation
    if stop_distance > 0:
        shares = risk_dollars / stop_distance
    else:
        shares = 0

    position_value = shares * entry_price

    # 4. Volatility adjustment (ATR as % of price)
    atr_pct = (atr / entry_price) * 100
    target_vol = 2.0  # target 2% daily vol

    if atr_pct > 0:
        vol_adj = min(target_vol / atr_pct, 1.5)  # cap at 1.5x
    else:
        vol_adj = 1.0

    # 5. Confluence adjustment
    confluence_mult = {6: 1.0, 5: 0.9, 4: 0.75, 3: 0.6, 2: 0.4, 1: 0.2, 0: 0}
    conf_adj = confluence_mult.get(confluence_score, 0.5)

    # 6. VIX adjustment
    if vix < 15:
        vix_adj = 1.0
    elif vix < 25:
        vix_adj = 1.0
    elif vix < 35:
        vix_adj = 0.5
    else:
        vix_adj = 0.0  # no entries

    # 7. Final adjusted value
    kelly_value = portfolio * kelly_capped
    adjusted_value = min(kelly_value, position_value) * vol_adj * conf_adj * vix_adj

    return {
        "kelly_pct": round(kelly_capped * 100, 1),
        "atr_shares": round(shares, 4),
        "position_value": round(position_value, 2),
        "adjusted_value": round(adjusted_value, 2),
        "adjusted_pct": round(adjusted_value / portfolio * 100, 1),
        "stop_price": round(entry_price - stop_distance, 2),
        "max_loss": round(stop_distance * shares, 2),
    }


# Example: $100K portfolio, BTC entry
btc = yf.download("BTC-USD", period="30d", progress=False)
atr = (btc["High"] - btc["Low"]).rolling(14).mean().iloc[-1]
btc_price = btc["Close"].iloc[-1]

size = compute_position_size(
    portfolio=100_000, risk_pct=1.0,
    entry_price=btc_price, atr=atr,
    win_rate=0.55, avg_win_loss_ratio=1.5,
    vix=20, confluence_score=4
)

for k, v in size.items():
    print(f"  {k}: {v}")
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual calculation using formulas above |
| v1 | position_sizer() function in engine.py — auto-computes on each entry signal |
| v2 | Correlation check: auto-detect overlapping positions, cap combined size |
| v3 | Drawdown-aware sizing: reduce size after -10% drawdown, freeze at -25% |
| v4 | Backtest optimal sizing parameters per thesis (win rate, avg W/L ratio) |

## Integration with Thesis Checklist

- [ ] Add `compute_position_size()` to engine.py — called on every execute_entry()
- [ ] Pass current VIX, ATR, confluence_score to sizing function
- [ ] Implement correlation penalty: check existing positions before sizing new
- [ ] Log sizing parameters with each trade in journal.db notes
- [ ] Weekly review: compare actual vs Kelly-recommended sizes

## Notes

- Full Kelly is aggressive and volatile. Half-Kelly is standard. Quarter-Kelly for new/untested strategies.
- ATR is NOT the same as your stop distance. Your stop = ATR × multiplier (usually 2-3). ATR alone is too tight.
- The most important sizing rule: NEVER increase size after a loss to "make it back." This is the fastest way to blow up.
- Crypto ATRs are 2-5x larger than equity ATRs (as % of price). Adjust target vol accordingly.
- Position sizing is where most traders fail. Not signal generation. A good signal with bad sizing = net loser.
- Correlation penalty only applies when correlation > 0.7. Below that, positions are sufficiently independent.
