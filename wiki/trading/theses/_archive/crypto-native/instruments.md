# Instruments — Crypto Institutional Accumulation Thesis

Version: v0
Status: DEFINED
Last updated: May 17, 2026

---

## Core Instruments

### Spot (Primary)
| Ticker | Name | Role | Source |
|--------|------|------|--------|
| BTC | Bitcoin | Primary thesis vehicle | Binance, Coinbase, Kraken |
| ETH | Ethereum | Secondary vehicle | Binance, Coinbase, Kraken |

### ETFs (for traditional brokerage access)
| Ticker | Name | Role |
|--------|------|------|
| IBIT | iShares Bitcoin Trust | BTC exposure in equity accounts |
| FBTC | Fidelity Wise Origin Bitcoin | BTC alternative |
| ETHA | iShares Ethereum Trust | ETH exposure in equity accounts |

### Futures (for derivatives data, not trading)
| Symbol | Name | Exchange | Data Source |
|--------|------|----------|-------------|
| BTCUSDT | BTC Perpetual | Binance | Coinglass, Binance API |
| ETHUSDT | ETH Perpetual | Binance | Coinglass, Binance API |
| BTC-期权 | BTC Options | Deribit | Deribit API |
| ETH-期权 | ETH Options | Deribit | Deribit API |

### On-Chain Data Sources (for module data, not instruments)
| Metric | Source | API |
|--------|--------|-----|
| Exchange flows | Glassnode | glassnode.com API |
| Exchange reserves | CryptoQuant | cryptoquant.com API |
| Whale wallets | Whale Alert, Dune | whale-alert.io, dune.com |
| Stablecoin supply | Dune Analytics | dune.com |
| Active addresses | Glassnode | glassnode.com API |

---

## Position Sizing

| Phase | Allocation (% of crypto paper capital) | Condition |
|-------|----------------------------------------|-----------|
| Initial | 25% | CRYPTO_E1 triggered (3/6 layers confirm accumulation) |
| Add | 25% | CRYPTO_E2 triggered (4/6 layers confirm) |
| Add | 25% | CRYPTO_E3 triggered (on-chain divergence from price) |
| Full | 25% | CRYPTO_E4 triggered (breakout with volume + OI confirmation) |
| Max | 100% | All four entry signals fired |

**Note:** This thesis is allocated 33% of total paper portfolio ($33K of $100K) when all 3 theses are live. Currently NOT LIVE.

---

## Basket Allocation

When the thesis is entered, capital is split:
- 60% BTC (or IBIT as proxy)
- 40% ETH (or ETHA as proxy)

This reflects BTC's larger market cap and lower volatility. Rebalanced only on full entries.

---

## Pricing Sources

| Asset | Source | Method |
|-------|--------|--------|
| BTC/USD | Binance API (public) | `api.binance.com/api/v3/ticker/price?symbol=BTCUSDT` |
| ETH/USD | Binance API (public) | `api.binance.com/api/v3/ticker/price?symbol=ETHUSDT` |
| IBIT, FBTC, ETHA | yfinance | `yf.download(ticker)` |
| BTC 200-day MA | Binance API (kline data) | Compute from daily closes |
| Fear & Greed | alternative.me API | `api.alternative.me/fng/` |

---

## Notes

- Binance API is free, no key needed for public endpoints.
- Crypto markets trade 24/7. Signal checks can run any time.
- BTC and ETH are highly correlated (>0.8). This thesis is a directional bet, not a pair trade.
- Alt-season is a potential v2 expansion — but requires BTC dominance breaking down first.
- CME gap risk: BTC futures gaps on weekends. Monitor Monday opens.
