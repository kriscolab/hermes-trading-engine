# Layer 6 — Macro: DXY, Rates, VIX, Cross-Asset Relationships

Module: macro
Signal Stack Position: Layer 6 (Macro / Cross-Asset)
Data Source: yfinance + FRED (both free)
Status: v0.1 — DEFINED, partially covered by fetch-prices.py + confluence analyzer

## Why This Matters

Macro is the tide that lifts or sinks all boats. When DXY is rising, all USD-denominated assets face headwinds. When real rates are rising, gold and crypto (zero-yield assets) underperform. When VIX spikes above 30, risk assets sell off regardless of individual fundamentals. This layer answers "is the macro environment supportive of our thesis direction?"

For commodity thesis: DXY and real rates are direct drivers. A falling DXY = structural commodity tailwind.
For AI thesis: Rate regime determines growth stock valuation. Rising rates crush high-multiple tech.
For crypto thesis: BTC/SPY correlation determines whether macro or crypto-native signals dominate.

## Data Sources

### DXY (US Dollar Index)
- Source: yfinance `DX-Y.NYB` — free, 15-min delayed
- Measures: USD vs basket (EUR, JPY, GBP, CAD, SEK, CHF)
- DXY > 105 = strong USD (headwind for all USD assets)
- DXY < 95 = weak USD (tailwind for commodities, crypto)

### US Treasury Yields (Real Rates)
- Source: yfinance `^TNX` (10Y), `^IRX` (3M) — free
- Real rate = Nominal yield - Inflation expectations (TIPS breakeven)
- Rising real rates = tightening financial conditions = risk-off
- Proxy: TIP ETF price. TIP falling = real rates rising.
- Key levels: 10Y > 5% = restrictive. 10Y < 3% = accommodative.

### VIX (Volatility Index)
- Source: yfinance `^VIX` — free
- VIX < 15: Complacency. Trend following works. Size up.
- VIX 15-25: Normal. Standard sizing.
- VIX 25-35: Elevated fear. Reduce size 50%. Tighter stops.
- VIX > 35: Panic. Stay flat or deep value entries only. Cash is a position.

### Additional Macro Indicators (FRED)
| Indicator | FRED Symbol | What It Tells You |
|-----------|------------|-------------------|
| Fed Funds Rate | DFF | Policy rate. Direction matters more than level. |
| 10Y-2Y Spread | T10Y2Y | Yield curve. Inverted = recession signal. |
| ISM Manufacturing PMI | — | Economic activity. <50 = contraction. |
| CPI YoY | CPIAUCSL | Inflation. >3% = Fed hawkish. |
| Unemployment Rate | UNRATE | Labor market. <4% = tight, wage pressure. |

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| DXY Direction | USD strength/weakness. Rising = headwind for all USD assets. | Crypto/commodities prefer falling DXY. |
| Real Rates Direction | Actual cost of money after inflation. Rising = tightening. | Gold longs hate rising real rates. Tech/AI hates rising rates. |
| VIX Level | Market fear. <15 = greed, >25 = fear, >35 = panic. | Size inversely with VIX. |
| 10Y Yield | Long-term rate expectations. Anchors all asset valuations. | Rising = growth stocks de-rate. Falling = growth re-rates higher. |
| DXY + VIX Combined | "Risk-off" = DXY up + VIX up. "Risk-on" = DXY down + VIX down. | Risk-on = all theses favorable. Risk-off = reduce all exposure. |
| Equities Trend (SPY) | Risk appetite proxy. Crypto follows SPY when correlation high. | SPY in uptrend = risk-on supportive. SPY in downtrend = caution. |

## Macro Regime Classification

```
REGIME          DXY     VIX    10Y     SPY Trend    Strategy
──────────────────────────────────────────────────────────
RISK-ON         ↓       <20    Stable  ↑           Full size. All theses favorable.
CAUTIOUS        →      20-25   Stable  →           Standard size. No leverage.
RISK-OFF        ↑       >25    Rising  ↓           Reduce size 50%. Tight stops.
PANIC           ↑↑      >35    Falling ↓↓          Cash only. No entries. Deep value watchlist.
STAGFLATION     ↑      20-25   Rising  →           Commodities favored. Gold favored. AI/crypto cautious.
GOLDILOCKS      ↓       <15    Falling ↑           Best regime. Size up. All assets benefit.
```

## Confluence Rules

### With Commodity Thesis
```
IF macro regime = RISK-ON (DXY↓, VIX<20, SPY↑)
   AND Brent near E1 pullback level
   → +1 confluence. Macro supports commodity long.
   → Enter at standard size.

IF macro regime = RISK-OFF (DXY↑, VIX>25)
   AND E2 Brent breakout firing
   → Macro contradicts. Reduce entry size to 50%.
   → Breakout may be supply-driven (valid) or macro-noise (fake).
```

### With AI Supercycle Thesis
```
IF 10Y yield rising (>4.5%)
   AND AI thesis signals firing
   → Rising rates hurt high-multiple growth. Reduce AI allocation.
   → Wait for rate stabilization before entering AI positions.

IF 10Y yield falling + DXY falling
   → Dovish regime. Growth stocks re-rate higher.
   → AI thesis gets +1 confluence in this regime.
```

### With Crypto Thesis
```
IF BTC/SPY correlation > 0.7
   AND macro regime = RISK-OFF
   → Crypto = levered beta. Reduce crypto exposure.
   → Trust macro signals over crypto-native signals.

IF BTC/SPY correlation < 0.3
   AND macro regime = RISK-OFF
   → Crypto decoupled. Macro risk-off irrelevant to BTC.
   → Trust crypto-native signals. +1 confluence score.
```

### With Gold Signals (E4S / E4L)
```
IF real rates rising (TIP ETF falling)
   AND DXY rising
   → +2 confluence for E4S Gold Short. Both macro factors aligned.
   → Maximum conviction for gold short.

IF real rates falling (TIP ETF rising)
   AND DXY falling
   → Contradicts E4S. Gold short thesis weakening.
   → Monitor for E4S cover signal. Or switch to E4L long.
```

## Divergence Signals (Higher Priority)

```
🔴 DXY ↑ BUT COMMODITIES ↑
   → Commodities rallying despite USD strength. Real supply shortage.
   → Bullish for commodity thesis. This is the strongest commodity signal.

🔴 DXY ↓ BUT GOLD ↓
   → Gold selling off despite USD weakness. Central bank selling likely.
   → Confirms E4S short thesis. Gold is under structural pressure.

🔴 VIX < 15 FOR 4+ WEEKS
   → Extreme complacency. Tail risk underpriced.
   → Don't add new positions. Prepare for vol expansion.
   → When VIX spikes from <15, move is violent and fast.

🔴 10Y-2Y SPREAD UN-INVERTING (moving from negative to positive)
   → Recession signal transitioning to recovery signal.
   → Historically bullish for risk assets 6-12 months out.
   → Early-cycle positioning: add risk. Commodities and crypto benefit first.

🔴 SPY CORRECTION (-10%) WITH VIX NOT SPIKING (>30)
   → Orderly selloff, not panic. Institutional rotation, not capitulation.
   → Buy the dip. This is healthy correction, not crash.
```

## How to Query (Python)

```python
import yfinance as yf

# Fetch macro dashboard
tickers = ["DX-Y.NYB", "^VIX", "^TNX", "SPY", "TIP"]
data = yf.download(tickers, period="5d", progress=False)["Close"]

dxy = data["DX-Y.NYB"].dropna().iloc[-1]
vix = data["^VIX"].dropna().iloc[-1]
tnx = data["^TNX"].dropna().iloc[-1]
spy = data["SPY"].dropna().iloc[-1]
tip = data["TIP"].dropna().iloc[-1]

# Direction checks
dxy_5d_ago = data["DX-Y.NYB"].dropna().iloc[-5] if len(data) >= 5 else dxy
vix_5d_ago = data["^VIX"].dropna().iloc[-5] if len(data) >= 5 else vix

dxy_direction = "↑" if dxy > dxy_5d_ago else "↓"
vix_direction = "↑" if vix > vix_5d_ago else "↓"
real_rates_direction = "↑" if tip < data["TIP"].dropna().iloc[-5] else "↓"

# Regime classification
if vix > 35:
    regime = "PANIC"
elif vix > 25 and dxy > dxy_5d_ago:
    regime = "RISK-OFF"
elif dxy > dxy_5d_ago and vix > 20:
    regime = "CAUTIOUS"
elif vix < 15:
    regime = "GOLDILOCKS"
else:
    regime = "RISK-ON"

print(f"DXY: {dxy:.2f} ({dxy_direction})")
print(f"VIX: {vix:.2f} ({vix_direction})")
print(f"10Y:  {tnx:.2f}%")
print(f"Real rates: {real_rates_direction}")
print(f"Regime: {regime}")
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual macro check via TradingView / Yahoo Finance |
| v1 | Already partially covered by fetch-prices.py (DXY, VIX, TIP) |
| v2 | Macro regime added to daily signal check header: `Macro: RISK-ON` |
| v3 | Auto-size adjustment based on VIX regime in engine |
| v4 | FRED data integration for yield curve, PMI, CPI |

## Integration with Thesis Checklist

- [ ] Add macro regime line to daily signal check header
- [ ] Implement VIX-based size adjustment in engine.py:
  - VIX <15: 100% size
  - VIX 15-25: 100% size
  - VIX 25-35: 50% size
  - VIX >35: 0% (no entries)
- [ ] Add macro confluence scoring:
  - +1 if regime supports thesis direction
  - 0 if neutral
  - -1 if contradicts

## Notes

- DXY is the single most important macro variable for commodity and crypto theses. Everything else flows from USD direction.
- VIX is mean-reverting. Spikes above 30 almost always come back down within 2-4 weeks. Buy when VIX is high.
- Real rates (not nominal) drive gold and crypto. TIP ETF is the easiest free proxy.
- 10Y-2Y inversion preceded every recession since 1970. Un-inversion precedes recovery.
- Macro data is backward-looking. Markets price the future. Don't trade the data — trade the market's reaction to the data.
- FOMC blackout: no entries 1h before/after FOMC decisions. The initial move is almost always wrong.
