# Layer 4 — Liquidations: Heatmaps + Liquidation Clusters

Module: liquidation
Signal Stack Position: Layer 4 (Leverage Flush)
Data Source: OKX public API (free, global, no key) — liquidation orders endpoint
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (OKX)

## Why This Matters

Liquidations are crypto's unique alpha layer. In equity markets, margin calls happen slowly, behind closed doors. In crypto, forced liquidations are visible on-chain and in real-time. You can see where leveraged positions will get wiped out before they do. Market makers know this and hunt these levels. So should we.

Liquidation clusters act as price magnets. When a large cluster sits below price, expect a sweep. When one sits above, expect a short squeeze to tag it. This layer answers "where is the fuel, and which direction will it burn?"

## Data Sources

### OKX Public API (Free, Global, No Key)
- Endpoint: `https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT&state=filled`
- Rate limit: 20 req/2s
- Coverage: BTC, ETH liquidations. Cross-exchange cascade data via public endpoint.
- Key fields: `posSide` (long/short), `sz` (size), `pnl`
- Alternative: Hyblock (free tier, delayed, requires key)

### Hyblock (Free Tier)
- Endpoint: `https://api.hyblockcapital.com/`
- Focus: Liquidation levels heatmap + CVD (cumulative volume delta)
- Free tier: delayed data, limited symbols, 5 calls/min
- Best for: Visual heatmap of where liquidations cluster at each price level

### Alternative
- **Binance public endpoints**: `fapi/v1/forceOrders` — recent forced liquidations. No API key, but limited to Binance only.
- **Bybit public**: `v5/market/liquidation` — recent liquidations. No key needed.

### Data Format (OKX liquidation order)

```json
{
  "data": {
    "longLiquidationList": [
      {"timestamp": 1779000000, "amount": 1234.56, "price": 98000}
    ],
    "shortLiquidationList": [
      {"timestamp": 1779000000, "amount": 567.89, "price": 102000}
    ]
  }
}
```

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| Aggregate Liquidation (24h) | Total forced closes. >$500M = capitulation event. | Spikes mark local tops/bottoms |
| Long/Short Liquidation Ratio | Which side is getting wiped. Longs wiped = bearish flush. Shorts wiped = squeeze. | >70% one-sided = extreme |
| Liquidation Clusters | Price levels where cumulative liquidations concentrate. | Magnets — price will revisit |
| Liquidation Heatmap | Visual of open leveraged positions at each price. Bright = dense leverage. | Where stops live |
| CVD (Cumulative Volume Delta) | Net buying/selling pressure. Divergence with price = reversal. | Hyblock provides this |
| Open Interest Post-Liquidation | Did OI reset or reload? Reload = same direction continues. | Critical: distinguishes flush from trend end |

## Confluence Rules

### With Layer 1 (Price Action / TPO)
```
IF price sweeps a liquidation cluster
   AND immediately reverses (long wick on the candle)
   → Liquidity grab. Market makers hunted stops, now reversing.
   → ENTER in the reversal direction.
   → Confirmation: next candle closes on other side of the sweep point.

IF price breaks through a liquidation cluster WITHOUT reversing
   → Genuine directional move. Stops were just fuel.
   → Trend continuation. Don't fade it.
```

### With Layer 2 (Funding Rates + OI)
```
IF large liquidation cluster exists below price
   AND funding rate extreme positive (>0.05%)
   AND OI at all-time highs
   → Overleveraged longs. Cluster WILL be hunted.
   → HIGH CONVICTION short (or fade longs).
   → Timeframe: within 24-72 hours.

IF price sweeps long liquidation cluster
   AND OI drops significantly (>15% in 24h)
   → Leverage flushed. Trend reset.
   → If funding resets to neutral → BUY the reset.
   → If funding stays negative → wait, more pain possible.

IF short liquidation cluster above price
   AND funding rate negative
   → Overleveraged shorts. Short squeeze fuel loaded.
   → Cluster is the target — expect price to tag it.
```

### With Layer 3 (Options)
```
IF put skew elevated (fear priced)
   AND long liquidation spike just occurred
   → Capitulation event. Fear + forced selling = bottom.
   → Options traders buying protection AFTER the flush = late.
   → Contrarian long.
```

### With Macro Layer (Layer 6)
```
IF macro event (FOMC, CPI) triggering liquidations
   → Macro-driven flush, not technical
   → After flush: wait 24 hours for second wave
   → Second flush wicks are the entries
   → First flush is reaction, second flush is overreaction
```

## Divergence Signals (Higher Priority)

```
🔴 LONG LIQUIDATION SPIKE (>$200M in 1 hour) BUT PRICE not at new low
   → Forced selling absorbed. Someone is buying the bodies.
   → Capitulation without price capitulation = bullish absorption.
   → Accumulation signal.

🔴 SHORT LIQUIDATION SPIKE (>$200M in 1 hour) BUT PRICE not at new high
   → Short squeeze absorbed. Someone is selling into it.
   → Distribution signal.

🔴 OI REBUILDS QUICKLY after liquidation flush (<24 hours)
   → Same bet, new players. Leverage reloaded.
   → If funding is same direction → trend still has legs.
   → If funding flipped → reversal now has fuel.

🔴 HEATMAP SHOWS DENSE CLUSTER at round number ($100K, $10K)
   → Psychological + liquidation magnet combined.
   → Round numbers concentrate both limit orders and liquidations.
   → Stronger magnet than non-round clusters.

🔴 LIQUIDATION CLUSTER PERSISTS after being swept
   → New leveraged positions built at the same level.
   → Level still relevant. Price likely to revisit.
   → Track cluster persistence — true support/resistance.
```

## How to Query (Python)

```python
import requests

COINGLASS = "https://open-api-v3.coinglass.com/api/futures"
HEADERS = {"coinglassSecret": COINGLASS_API_KEY}

# 24h liquidation summary
r = requests.get(
    f"{COINGLASS}/liquidation/detail/chart",
    params={"symbol": "BTCUSDT", "interval": "1h"},
    headers=HEADERS
)
data = r.json()["data"]
long_liq = sum(d["amount"] for d in data["longLiquidationList"][-24:])
short_liq = sum(d["amount"] for d in data["shortLiquidationList"][-24:])

# Liquidation order levels (heatmap)
r = requests.get(
    f"{COINGLASS}/liquidation/order",
    params={"symbol": "BTCUSDT"},
    headers=HEADERS
)
# Returns liquidation levels by price — find dense clusters

# OKX liquidation orders (free, global, no key)
binance_url = "https://fapi.binance.com/fapi/v1/forceOrders"
r = requests.get(binance_url, params={"symbol": "BTCUSDT", "limit": 100})
force_orders = r.json()

# Hyblock liquidation levels (free tier)
hyblock_url = "https://api.hyblockcapital.com/v1/liquidation/levels"
r = requests.get(hyblock_url, params={
    "symbol": "BTCUSDT",
    "api_key": HYBLOCK_API_KEY
})
heatmap = r.json()
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via OKX or Hyblock dashboard during signal review |
| v1 | Python script pulls daily liquidation data → vault tracker (total liq, long/short ratio) |
| v2 | Liquidation cluster detection: identify dense zones (>$10M cumulative liq at level) |
| v3 | Integrated into daily signal check: alert when price approaches cluster (±2%) |
| v4 | Auto-flag confluence: cluster + extreme funding + OI high = imminent flush |

## Integration with Thesis Checklist

When a crypto-native thesis uses this layer:
- [ ] OKX public endpoints (no key needed). Hyblock optional for heatmap data.
- [ ] Set up Hyblock free account (delayed data acceptable for daily checks)
- [ ] Define "large liquidation" threshold: BTC >$200M/24h, ETH >$100M/24h, alts >$20M/24h
- [ ] Add liquidation columns to thesis tracker: daily total, long%, OI delta
- [ ] Define entry signals: flush-and-reverse pattern (sweep + wick reversal)

## Notes

- Liquidation data is delayed 5-15 minutes on free tiers. Not for scalping — for identifying zones.
- Single-exchange data (OKX only) misses the cross-exchange cascade. However this is the best free option. For full market liquidation data, paid Coinglass/Glassnode is needed.
- Weekend liquidations are more violent (thinner books, wider spreads). Cluster at round numbers.
- Altcoin liquidations cascade faster than BTC. One alt liquidation can trigger a sector-wide flush.
- "Liquidation cascade" = liquidated positions push price into more liquidations. These are the biggest one-day moves in crypto. They reverse 80%+ of the time within 72 hours.
- Don't front-run a liquidation cascade. Wait for it to finish (OI drops, price stabilizes), THEN enter.
- The best entries come 24-48h AFTER the cascade, not during.
