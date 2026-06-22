# Signals — Crypto Institutional Accumulation Thesis

Version: v0
Status: DEFINED — NOT YET LIVE
Last updated: May 17, 2026

---

## Thesis Claims (from thesis.md)

All signals require confluence from multiple layers. No single-layer entries.

---

## Entry Signals

### CRYPTO_E1 — Initial Accumulation Confirmed (3/6 Layers)
**Claim:** BTC in accumulation phase.
**Trigger:** At least 3 of these 6 conditions are met:
  - L2: Funding rate neutral (-0.01% to +0.03%) AND OI building on green candles
  - L3: 25-delta IV skew > 0 (calls bid)
  - L4: Short liquidation clusters > long clusters above current price
  - L5: Exchange netflow negative over 7 days
  - L5: Exchange reserve trending down (30-day low)
  - Macro: Fear & Greed Index between 20-60 (not extreme)
**Action:** Enter 25% of crypto allocation into BTC (60%) + ETH (40%).
**Rationale:** 3-layer confluence is the minimum threshold for structural accumulation. Less than 3 = noise.

### CRYPTO_E2 — Accumulation Strengthening (4/6 Layers)
**Claim:** Institutional flows are net buying.
**Trigger:** At least 4 of 6 conditions from E1 are met, AND:
  - L5: Whale wallets (top 100 non-exchange) increased holdings over 14 days
  - L2: Long/short ratio balanced (0.8–1.5), not crowded
**Action:** Add 25% of crypto allocation.
**Rationale:** 4+ layers with whale confirmation = conviction entry. The big money is positioned.

### CRYPTO_E3 — On-Chain Divergence (Price Down, Flows Up)
**Claim:** Smart money buying the dip while retail panics.
**Trigger:** BTC price down >5% over 7 days BUT:
  - L5: Exchange outflows surging (2σ above 30-day average)
  - L5: Stablecoin supply on exchanges rising
  - L2: Funding NOT extremely negative (not panic shorting)
**Action:** Add 25% of crypto allocation.
**Rationale:** This is the highest-conviction crypto-native signal. On-chain data reveals accumulation during fear. This divergence is invisible to equity traders.

### CRYPTO_E4 — Breakout with Confluence (5/6 Layers)
**Claim:** The next leg up is starting.
**Trigger:** BTC makes a new 30-day high AND:
  - L2: OI rising on the breakout (not falling — genuine demand)
  - L1: Volume 2x 30-day average on breakout candle
  - L3: IV skew remains bullish or improves (not "sell the news")
  - L5: Exchange reserves still falling (not distribution into strength)
  - L4: Short liquidations spiking (shorts getting squeezed = fuel)
**Action:** Enter remaining 25% of crypto allocation.
**Rationale:** Breakout with 5-layer confluence = trend initiation, not fakeout. The fuel is loaded.

---

## Exit Signals (Thesis Invalidation)

### CRYPTO_X1 — Exchange Reserves Rising Sharply
**Trigger:** BTC exchange reserves increase >5% over 14 days.
**Action:** Exit 50% immediately.
**Rationale:** Coins moving to exchanges = intent to sell. This is the single most important on-chain exit signal.

### CRYPTO_X2 — Whale Distribution
**Trigger:** Top 100 non-exchange wallets decrease holdings >3% over 14 days.
**Action:** Exit 50% immediately.
**Rationale:** Smart money exiting before retail notices. The thesis breaks if whales are selling.

### CRYPTO_X3 — Derivatives Overheating
**Trigger:** Funding rate >0.05% for 3 consecutive 8h windows AND OI at ATH.
**Action:** Exit 25%, re-enter on funding reset.
**Rationale:** Overleveraged longs = liquidation cascade incoming. This is a tactical exit, not thesis invalidation. Re-enter when funding resets.

### CRYPTO_X4 — BTC Correlation with SPY > 0.7
**Trigger:** 30-day rolling correlation of BTC/SPY >0.7.
**Action:** Exit 25% — crypto thesis becomes macro thesis.
**Rationale:** If BTC is just levered beta on equities, the crypto-native edge is gone. Re-evaluate thesis.

### CRYPTO_X5 — Regulatory Shock
**Trigger:** US SEC/CFTC announces enforcement action against major exchange or BTC/ETH classified as security.
**Action:** Exit 100% within 24 hours.
**Rationale:** Regulatory risk is the one external factor that overrides all on-chain signals. No confluence analysis needed — exit first, ask questions later.

---

## Confluence Scoring

Each signal check assigns a confluence score (0-6):

```
Layer 1 (Structure):    BTC > 200MA + higher lows         → +1
Layer 2 (Derivatives):  Funding neutral + OI healthy       → +1
Layer 3 (Options):      Skew bullish + term structure OK   → +1
Layer 4 (Liquidations): Short clusters > long clusters     → +1
Layer 5 (On-Chain):     Outflows + reserves down           → +1
Layer 6 (Sentiment):    Fear & Greed 20-60                 → +1

Score 0-2: WAIT — insufficient confluence
Score 3:   WATCH — minimum for CRYPTO_E1
Score 4:   ENTER — CRYPTO_E2 threshold
Score 5-6: STRONG ENTER — CRYPTO_E4 threshold
```

---

## What to Monitor (future Daily Cron)

| Check | Data Source | Frequency |
|-------|------------|-----------|
| BTC/ETH price + volume | Binance API (free) | Daily |
| BTC 200-day MA | Binance kline data | Daily |
| Funding rate (BTC/ETH) | Coinglass or Binance fapi | Daily |
| OI change (24h) | Coinglass | Daily |
| IV skew (25-delta) | Deribit API (free) | Daily |
| Liquidation clusters | Coinglass/Hyblock | Daily |
| Exchange netflow | Glassnode API (free tier) | Daily |
| Exchange reserves | CryptoQuant (free tier) | Weekly |
| Whale wallet balance | Whale Alert / Dune | Weekly |
| Stablecoin exchange supply | Dune | Weekly |
| Fear & Greed Index | alternative.me API | Daily |
| BTC/SPY correlation | Compute from yfinance | Weekly |

---

## Logging

| Date | Signal | Status | Confluence Score | Notes |
|------|--------|--------|-----------------|-------|
| May 17, 2026 | — | v0 defined | — | Thesis codified. Not yet live. No tracker cron. |

---

## Notes

- This thesis uses all 4 built crypto modules (derivatives, on-chain, options, liquidation) plus: session-clock (Asia/London/NY timing), position-sizing (ATR/Kelly formulas), smart-contracts (DeFiLlama TVL tracking), volume-profile (VWAP + volume confirmation for L1 confluence). The remaining planned modules provide supplementary data when built.
- Module data uses free API tiers. Rate limits may constrain daily checks to 1-2 requests per source.
- BTC and ETH move together >80% of the time. This is a directional thesis, not a pair trade.
- The confluence scoring system ensures no single indicator triggers an entry. Minimum 3-layer confirmation.
- Crypto markets never close. Signal checks can run any time of day. No weekend filter needed — but session-clock module defines optimal entry windows (London/NY overlap).
- Engine integration: add "crypto" to ALL_SIGNALS in engine.py, wire CRYPTO_E1-E4 and CRYPTO_X1-X5.
