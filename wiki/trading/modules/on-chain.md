# Layer 5 — On-Chain: Exchange Flows + Whale Tracking

Module: on-chain
Signal Stack Position: Layer 5 (On-Chain Data)
Data Source: DeFiLlama + Dune Analytics + CoinGecko (all free, global)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (DeFiLlama+Dune+CoinGecko)

## Why This Matters

On-chain data is a leading indicator. Exchange flows reveal intent before it hits the order book. Whale movements show where institutional cost bases sit. Stablecoin supply acts as dry powder. This layer answers "are smart hands accumulating or distributing?"

## Data Sources

### DeFiLlama + Dune Analytics (Free, Global)
- DeFiLlama: `https://api.llama.fi/` — TVL, protocol data, chains. Generous rate limit.
- Dune: `https://dune.com/` — public dashboards for exchange flows, stablecoin supply
- No API keys needed for either
- Glassnode API has no free tier. CryptoQuant and Whale Alert are paid.
  We use DeFiLlama TVL as on-chain proxy + Dune exchange flow dashboards.
- Key metrics: TVL trends, exchange reserves (via Dune dashboards), stablecoin mcap

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| Exchange Inflows | Coins moving TO exchanges. Ready to sell. | Bearish |
| Exchange Outflows | Coins leaving exchanges. Moving to cold storage. | Bullish (accumulation) |
| Exchange Netflow | Outflow - Inflow. Positive = accumulation. | Directional bias |
| Exchange Reserve | Total BTC on exchanges. Falling = supply shock building. | Long-term bullish |
| Stablecoin Supply (ERC-20) | USDT/USDC on exchanges. Rising = dry powder. | Bullish |
| Whale Wallet Balance | Top 100 non-exchange wallets. Accumulating or distributing? | Institutional intent |
| Miner Outflow | Miners sending BTC to exchanges. Selling pressure. | Short-term bearish |
| Active Addresses | Network usage. Rising = adoption. | Long-term bullish |

## Confluence Rules

### With Layer 1 (Price Action / TPO)
```
IF price at TPO support (VAL or POC)
   AND exchange outflows spiking (>2σ above 30-day avg)
   AND stablecoin supply rising
   → HIGH CONVICTION accumulation zone
   → Not just a technical bounce — structural buying
```

### With Layer 2 (Funding Rates)
```
IF funding rate negative (crowded short)
   AND exchange outflows surging
   → Shorts are trapped. Supply being absorbed.
   → Squeeze setup has fuel.
```

### With Layer 5 Companion (Smart Contracts / DeFi)
```
IF exchange reserves falling
   AND DeFi TVL rising (coins moving to protocols, not cold storage)
   → Distinguish: accumulation vs yield farming
   → TVL rise + reserve fall = neutral (coins just moved venue)
   → No TVL rise + reserve fall = true accumulation
```

## Divergence Signals (Higher Priority)

```
🔴 PRICE ↑ (new highs) BUT exchange inflows SURGING
   → Distribution disguised as breakout
   → Smart money selling into retail euphoria
   → Fade the breakout

🔴 PRICE ↓ (crashing) BUT exchange outflows SURGING
   → Panic buyers absorbing the dump OR
   → Whales moving coins off exchange during low prices
   → Check whale wallet data: if top wallets are buying = accumulation

🔴 STABLECOIN SUPPLY ↑ but PRICE ↓
   → Dry powder building. Buyers waiting.
   → Capitulation likely near.
   → Once supply deploys, reversal is violent.

🔴 WHALE WALLETS accumulating while PRICE sideways
   → Institutional cost basis forming
   → Strong support zone. They won't let price below their entry.
   → Track the level — it becomes structural support.
```

## How to Query (Python)

```python
import requests

# DeFiLlama — TVL + protocol data (free, global, no key)
url = "https://api.llama.fi/protocol/bitcoin"
r = requests.get(url)
tvl_data = r.json()

# Dune — public dashboard (no key)
# Use pre-built queries from https://dune.com/browse/dashboards
# Search for: "Exchange Flows", "BTC Reserve", "Stablecoin Supply"

# Dune — public query (no key)
# Use: https://dune.com/queries/<query_id>/export/csv
# Find pre-built queries at https://dune.com/browse/dashboards

# Whale tracking via Lookonchain (free, web-based)
# URL: https://lookonchain.com/ — tracks large transactions with entity labels
# No API key needed. Manual check or use Arkham free tier for programmatic access.
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via Dune dashboards during signal review |
| v1 | Python script pulls Glassnode netflow + exchange reserve → vault tracker |
| v2 | Integrated into daily signal check (adds on-chain line) |
| v3 | Auto-flag when accumulation/distribution pattern detected |
| v4 | Whale wallet clustering tracked weekly, mapped to support/resistance |

## Integration with Thesis Checklist

When a crypto-native thesis uses this layer:
- [ ] DeFiLlama + Dune — no keys needed. Already live in crypto-data-fetch.py.
- [ ] Bookmark 3-5 Dune dashboards for quick manual checks
- [ ] Define thresholds: what counts as "spiking" outflows? (2σ above 30d avg)
- [ ] Add on-chain metrics columns to thesis tracker
- [ ] Define entry signals: accumulation zone confirmed by 2 of {outflows, stablecoin supply, whale buying}

## Notes

- On-chain data has 1-4 hour lag. Not for scalping — for confirming structural moves.
- Exchange reserve data: some exchanges obfuscate wallet addresses. Use aggregate across 5+ exchanges.
- Whale wallets: exclude exchange wallets and known protocol addresses. Use Glassnode's labeled data.
- Stablecoin supply: USDT on Tron has different dynamics than ERC-20 USDT. Prefer ERC-20 for quality.
- Miner flows: halving events change miner economics. Adjust thresholds post-halving.
