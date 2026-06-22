# Layer 2 — Derivatives: Funding Rates + Open Interest

Module: derivatives
Signal Stack Position: Layer 2 (Positioning)
Data Source: OKX public API (free, global, no key)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (OKX)

## Why This Matters

Funding rates and open interest give real-time positioning data that equity traders don't have. You can see whether the crowd is overleveraged long or short before the liquidation cascade hits.

## Data Sources

### OKX Public API (Free, Global, No Key)
- Endpoint: `https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP`
- Rate limit: 20 req/2s (generous for free)
- Coverage: BTC, ETH, 200+ perps
- Key fields: `fundingRate`, `instId`, `fundingTime`
- Alternative: KuCoin futures (may need auth). Note: Binance geo-blocked from this VPS.

### Key Metrics

| Metric | What It Tells You | Unit |
|--------|------------------|------|
| Funding Rate | Cost of holding a position. Positive = longs pay shorts. | % per 8h |
| Open Interest (OI) | Total outstanding contracts. Rising = new money. Falling = closing. | USD or BTC |
| OI Delta | Change in OI over N periods. +OI on rally = trend strength. +OI on drop = capitulation. | % |
| Long/Short Ratio | Aggregate positioning. >2.0 = crowded long. <0.7 = crowded short. | ratio |
| OI-Weighted Funding | Funding × OI. Identifies where the big money is positioned. | weighted % |

### Data Format (OKX funding rate response)

```json
{
  "data": [{
    "symbol": "BTCUSDT",
    "exchangeName": "Binance",
    "fundingRate": 0.0001,
    "nextFundingTime": 1779000000000,
    "openInterest": 12345.67,
    "oiValue": 987654321,
    "longShortRatio": 1.23
  }]
}
```

## Confluence Rules

### With Layer 1 (Price Action / TPO)
```
IF price at TPO POC/VAH/VAL
   AND funding rate extreme (>0.05% for longs, <-0.03% for shorts)
   → HIGH CONVICTION mean reversion setup
   → The crowd is leaning too hard one way at a key level.
```

### With Layer 3 (Options)
```
IF IV skew bullish (call skew positive)
   AND funding rate neutral (-0.01% to +0.01%)
   → GENUINE buying interest, not leverage-driven pump
```

### With Layer 4 (Liquidations)
```
IF large liquidation cluster exists at level X
   AND funding rate is extreme in that direction
   → Fuel is loaded. Price gravitates toward the cluster.
   → Market makers profit from triggering these.
```

## Divergence Signals (Higher Priority)

```
🔴 PRICE ↑ but FUNDING ↓ (going negative)
   → Shorts building into the rally
   → Absorption OR squeeze incoming
   → Fade the breakout until funding confirms

🔴 PRICE ↓ but FUNDING ↑ (going positive)
   → Longs buying the dip aggressively
   → Could be a trap — check OI
   → If OI also falling = forced liquidation, not dip-buying

🔴 OI SURGING but PRICE flat
   → Leverage building without direction
   → Coiling spring — expect explosive move
   → Direction given by funding rate extreme
```

## How to Query (Python)

```python
import requests

# OKX funding rate (free, global, no key)
url = "https://www.okx.com/api/v5/public/funding-rate"
params = {"instId": "BTC-USDT-SWAP", "limit": 10}

# KuCoin (free, global — Binance geo-blocked from this VPS)
url = "https://api.kucoin.com/api/v1/market/orderbook/level1"
r = requests.get(b_url, params={"symbol": "BTCUSDT", "limit": 10})
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via web during signal review |
| v1 | Python script pulls Coinglass data daily → writes to vault |
| v2 | Integrated into daily signal check cron (adds funding/OI line) |
| v3 | Auto-flag when confluence with TPO or liquidation layers detected |

## Integration with Thesis Checklist

When a crypto-native thesis uses this layer:
- [ ] Define asset-specific funding thresholds (BTC vs altcoins)
- [ ] OKX public endpoints — no key needed. Already live in crypto-data-fetch.py.
- [ ] Add funding/OI columns to thesis tracker
- [ ] Define entry/exit signals using derivatives data

## Notes

- Funding rates reset every 8 hours. Best read: 15 min before reset.
- Altcoin funding rates are more volatile than BTC. Adjust thresholds.
- OI changes mid-week are more reliable than weekend moves (lower volume).
- OKX free: 20 req/2s. No key. Sufficient for daily checks. Use OKX public API for everything.
