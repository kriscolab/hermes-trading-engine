# Hermes Trading Platform — README

> Multi-thesis automated trading research & execution platform
> v8h · May 2026 · 3 theses · 12 modules · 29 signals · 14 crons

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| Multi-thesis engine | ✅ LIVE | 3 theses: commodity, AI, crypto |
| Paper trading | ✅ LIVE | SQLite journal, idempotent signals, $100K portfolio |
| 6-layer crypto stack | ✅ BUILT | Derivatives, options, liquidation, on-chain, sentiment, macro |
| Strategy synthesizer | ✅ LIVE | Daily unified market state JSON |
| Confluence analyzer | ✅ LIVE | Cross-layer confidence scoring (🟢🟡🔴) |
| Learning loop | ✅ LIVE | Weekly review + missed opportunity audit |
| Cross-thesis correlator | ✅ LIVE | 10 cross-link patterns between theses |
| Airdrop scanner | ✅ LIVE | 5-dimension scoring, daily ranking |
| Telegram delivery | ✅ LIVE | 14 cron jobs → @hermestradingdesk + DM |
| Sanity audit | ✅ LIVE | Platform-wide data→usage→delivery verification |

## Signal Stack

```
COMMODITY:  Brent, gold, DXY, XLE, XLK, VIX
AI:         SOXX, IGV, DTCR, TAN, XLC, INTC, CRWV, BE, CORZ
CRYPTO:     BTC, ETH + 6-layer confluence (derivatives, options, liquidation, on-chain, sentiment, macro)
```

## Data Sources (All Free)

yfinance · Coinglass · Deribit · Glassnode · DeFiLlama · alternative.me · Binance · Whale Alert · Dune · Polymarket

## Engine Commands

```bash
python3 engine.py --thesis commodity|ai|crypto
python3 engine.py --summary --prices '{"GLD":417}'
python3 engine.py --recommend
python3 engine.py --execute
python3 engine.py --history
```

## Performance

- First trade executed: **E4S Gold Short** — 11.98 GLD @ $417.29 (5% allocation)
- All 29 signals across 3 theses idempotent (30-day dedup)
- Daily market state generated in ~2.2K tokens
- 14 cron jobs delivering to Telegram with standardized formatting

## Documentation

See [MASTER_GUIDE.md](MASTER_GUIDE.md) for overview, [ARCHITECTURE.md](../ARCHITECTURE.md) for deep dive.
