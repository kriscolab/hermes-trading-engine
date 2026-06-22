# Crypto-Native Engine — v0 Plan

Version: v0
Status: PLANNING — v9-crypto 5/10 quant modules built. Monte Carlo validating edges.
Built: mean-reversion, correlation, momentum, monte-carlo, stat-arbitrage.
Next: volatility-arbitrage, event-driven, ML, market-making, microstructure.
CCXT: queued for execution layer (v9+).
Created: May 18, 2026

## PENDING: Old System Cron Study

The pre-wipe system (before May 3) had 20+ crypto-specific cron jobs. These contained:
- CCXT-based exchange integrations
- Multi-signal confluence (funding + sentiment + screener)
- Backtesting and strategy learning loops
- On-chain data pipelines
- Smart contract / DEX tracking

v0 architecture is FROZEN until old cron jobs are fully studied, ingested, and questioned. The old system likely had solutions to problems we're re-encountering.

## Proposed Scope (Tentative, Subject to Old System Findings)

### Crypto-Native Engine
- Separate from tradfi engine.py
- CCXT unified exchange API as foundation
- DEX routing (Hyperliquid, dYdX, GMX public APIs)
- Risk-isolated execution

### Quant Layer (Expanded Beyond Mean Reversion)
- Mean reversion (Bollinger, RSI, Stoch)
- Momentum / trend following
- Statistical arbitrage (pair trading, cointegration)
- Market making (spread capture, inventory management)
- Correlation-based rotation
- Volatility regime switching
- Monte Carlo edge validation
- Kelly position sizing
- Market microstructure (order book imbalance, flow toxicity)

### Discovery Layer
- Low-cap screening (MCap + volume + whale inflow)
- DeFi yield optimization (lending, LP, vault APY)
- Prediction market arbitrage (Polymarket)
- Narrative / sentiment tracking (CT, Discord)

### Data Feeds Already Built
- 6-layer crypto data (crypto-data-fetch.py)
- OKX (funding, OI, liquidations), Deribit (options), DeFiLlama (TVL), CoinGecko (prices, BTC.D), alternative.me (F&G), KuCoin (backup)

## Old System Questions to Answer
1. What exchange APIs were integrated? (CCXT suggests Binance, Bybit, OKX, KuCoin)
2. What specific cron jobs existed? (screener, funding, sentiment, confluence are mentioned)
3. What signal confluence rules were encoded?
4. What backtesting infrastructure existed?
5. What failed and why? (learning for v1)
