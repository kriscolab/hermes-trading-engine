# Advanced Patterns — Confluence, Sizing & Divergence

## 1. Confluence Scoring (Crypto Thesis)

The crypto thesis uses a 0-6 layer scoring system. Each layer contributes +1 when confirmation conditions are met:

```
Layer 1 (Structure):   BTC > 200MA + higher lows         → +1
Layer 2 (Derivatives): Funding neutral + OI healthy       → +1
Layer 3 (Options):     Skew bullish + term structure OK   → +1
Layer 4 (Liquidations): Short clusters > long clusters    → +1
Layer 5 (On-Chain):    Outflows + reserves down           → +1
Layer 6 (Sentiment):   Fear & Greed 20-60                 → +1

Score 0-2: WAIT — insufficient confluence
Score 3:   WATCH — minimum for CRYPTO_E1
Score 4:   ENTER — CRYPTO_E2 threshold
Score 5-6: STRONG ENTER — CRYPTO_E4 threshold
```

## 2. Position Sizing Patterns

### ATR-Based (Short-Term)
```python
Position = Risk_Amount / (ATR × Multiplier)
# $100K portfolio, 1% risk = $1,000
# BTC ATR = $2,000, stop at 2x = $4,000
# Position = $1,000 / $4,000 = 0.25 BTC
```

### Kelly-Inspired (Thesis Entries)
```python
f* = (p × b - q) / b          # Full Kelly
f = f* / 2                     # Half-Kelly (standard)
# Cap: 25% per entry, 50% per thesis
```

### Volatility-Adjusted
```python
Adjusted = Base × (Target_Vol / Current_Vol)
# Current ATR% = 4%, Target = 2%
# Adjusted = $25K × (2/4) = $12.5K (half in high vol)
```

### VIX-Based Sizing
```
VIX <15:   100% size (complacency)
VIX 15-25: 100% size (normal)
VIX 25-35:  50% size (elevated fear)
VIX >35:     0% size (panic — no entries)
```

## 3. Regime Override Rules

These apply to ALL theses, ALL signals:

```
HIGH-VOL RANGE (ADX<20, ATR>5%):    NO ENTRIES. Period.
TRANSITIONING (ADX 20-25):          NO ENTRIES. Wait for confirmation.
STRONG TREND (ADX>25):              Only in trend direction. No counter-trend.

VIOLATION: Counter-trend trade in STRONG BEAR because "signal looks good"
           = most common losing trade. Don't do it.
```

## 4. Divergence Patterns (Highest Priority)

```
🔴 GOLD VS DXY — Gold rising without DXY falling
   → Central bank buying or flight-to-safety
   → If DXY rises, gold short (E4S) benefits significantly

🔴 ON-CHAIN VS PRICE — Exchange reserves falling, BTC flat
   → Accumulation before move. Smart money buying quietly.
   → Position for breakout. Don't short.

🔴 FUNDING VS SENTIMENT — Funding neutral, F&G extreme
   → Crowd emotional but not leveraged. Reversal is violent.
   → Fade the sentiment extreme in the opposite direction.

🔴 OI SURGING, PRICE FLAT — Leverage building without direction
   → Coiling spring. Explosive move coming.
   → Direction given by funding rate extreme.

🔴 DEFI TVL ↑ BUT BTC ↓ — DeFi growing while BTC declines
   → Capital rotating to DeFi from BTC. Alt-season signal.
   → Reduce BTC exposure, consider ETH/DeFi positions.
```

## 5. Cross-Thesis Patterns

```
TRIPLE BULLISH (all 3 theses aligned):
  → Maximum risk-on. Size up across theses. Correlation benefit.

TRIPLE BEARISH (all 3 theses bearish):
  → Systemic risk-off. Cash is the position. Wait.

OIL + AI BOTH FIRING:
  → AI build-out confirmed from both molecule + electron sides.
  → Highest conviction for infrastructure supercycle.

GOLD SHORT + AI BULLISH (conflict):
  → Rising rates hurt AI (growth stocks) but help gold short.
  → Review DXY + real rates. One thesis is wrong.
```

## 6. Learning Loop Patterns

```
Pattern: "Energy stocks dump on OPEC headlines, recover within 72h"
  → Add rule: don't exit on OPEC news. Wait 3 days.

Pattern: "E4S (gold short) wins 80% when DXY > 99"
  → Add confluence bonus: +1 to E4S confidence when DXY > 99.

Pattern: "Missed signals cluster around cron delivery failures"
  → Add pre-flight health check before signal execution.
```

## Quick Decision Matrix

| Regime | VIX | Confluence | Action |
|--------|-----|-----------|--------|
| QUIET BULL | <20 | HIGH | Enter full size |
| STRONG BULL | 20-25 | HIGH | Enter 75% size |
| LOW-VOL RANGE | <15 | ANY | Range-trade only, 50% size |
| HIGH-VOL RANGE | >25 | ANY | NO ENTRIES |
| PANIC | >35 | ANY | Cash only |
