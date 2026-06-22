# Gap 4 — Correlation: BTC.D, ETH/BTC, BTC/SPY

Module: correlation
Signal Stack Position: Gap 4 (Inter-Market Correlation)
Data Source: Computed from price data (yfinance, KuCoin — both free, global)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (CoinGecko)

## Why This Matters

Correlation tells you whether crypto is trading on its own fundamentals or as levered beta on equities. When BTC/SPY correlation is high (>0.7), crypto trades like a tech stock — the crypto-native edge is gone, and your thesis becomes a macro thesis. When correlation is low (<0.3), crypto is in its own world — crypto-native signals (on-chain, derivatives, options) have maximum edge.

BTC Dominance (BTC.D) tells you whether capital is rotating into BTC (safety, institutional) or into alts (risk-on, retail speculation). ETH/BTC ratio is the single best indicator of "alt-season" — when it's rising, alts outperform BTC.

## Data Sources

### BTC Dominance (BTC.D)
- Computed as: BTC Market Cap / Total Crypto Market Cap
- Source: CoinGecko API (free): `https://api.coingecko.com/api/v3/global`
- Alternatively: TradingView BTC.D symbol via yfinance (`BTC.D` on TradingView)

### ETH/BTC Ratio
- Computed as: ETH Price / BTC Price
- Source: KuCoin API (free, global): `api.kucoin.com/api/v1/market/orderbook/level1?symbol=ETH-BTC`
- Alternatively: yfinance `ETH-BTC`

### BTC/SPY Correlation
- Computed: 30-day rolling Pearson correlation of daily returns
- Source: yfinance for both BTC-USD and SPY

### Stablecoin Dominance
- USDT.D + USDC.D: Stablecoin market cap / total crypto market cap
- Rising = dry powder building. Falling = capital deploying into crypto assets.
- Source: CoinGecko API or Dune dashboards

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| BTC.D (BTC Dominance) | BTC's share of total crypto market cap. Rising = risk-off, BTC safety. Falling = alt-season. | >55% = BTC regime. <45% = alt-season. |
| ETH/BTC Ratio | ETH outperformance vs BTC. Rising = smart contract demand, DeFi/NFT activity. | >0.06 = ETH strong. <0.04 = BTC dominance. |
| BTC/SPY 30d Correlation | How much BTC moves with equities. >0.7 = levered beta. <0.3 = crypto-native. | High = trust macro. Low = trust crypto signals. |
| Stablecoin Supply Ratio (SSR) | BTC market cap / stablecoin market cap. Low = more dry powder available. | <10 = bullish (plenty of ammo). >30 = fully deployed. |
| USDT.D (Tether Dominance) | USDT's share of total crypto market cap. Rising = capital in sidelines. | >7% = fear/capitulation. <3% = fully deployed. |
| ETH/BTC + BTC.D Divergence | BTC.D falling + ETH/BTC rising = true alt-season. BTC.D falling + ETH/BTC flat = BTC profit-taking only. | Divergence defines alt-season quality. |

## Confluence Rules

### With Layer 5 (On-Chain)
```
IF BTC/SPY correlation < 0.3
   AND on-chain signals are bullish (outflows, reserves down)
   → Maximum crypto-native edge. Trust on-chain over macro.
   → Size up on crypto entry signals.

IF BTC/SPY correlation > 0.7
   AND macro signals are bearish (DXY rising, VIX > 25)
   → Crypto is levered beta. Macro risk flows through to crypto.
   → Reduce crypto position size by 50%. Trust macro over crypto signals.
```

### With Layer 2 (Derivatives)
```
IF BTC.D rising (>55%) AND funding rates neutral
   → Institutional accumulation, not retail pump
   → Healthy BTC uptrend. Long BTC, avoid alts.

IF BTC.D falling (<45%) AND altcoin funding rates spiking
   → Retail speculation in alts. Euphoria signal.
   → Rotate from alts to BTC or stablecoins.
```

### With Layer 3 (Options)
```
IF BTC/SPY correlation < 0.3
   AND IV skew bullish
   → Crypto-specific bullishness, not macro-driven
   → High conviction on crypto directional bets.

IF BTC/SPY correlation > 0.7
   AND IV skew bearish (puts expensive)
   → Fear is macro-driven, not crypto-specific
   → The fear may be overpriced for crypto. Potential opportunity.
```

### With Crypto Thesis
```
IF CRYPTO_E1 (3/6 layers confirm accumulation)
   AND BTC/SPY correlation < 0.3
   → +1 to confluence score. Crypto-native signal, not macro noise.

IF BTC.D > 55% AND stablecoin supply rising
   → Dry powder building in BTC specifically. Bullish for BTC entries.
```

## Divergence Signals (Higher Priority)

```
🔴 BTC ↑ BUT BTC.D ↓
   → BTC is rising but alts are rising faster. Alt-season.
   → Rotate 40% of BTC position to ETH or ETH proxy.

🔴 BTC ↓ BUT BTC.D ↑
   → Alts are crashing harder than BTC. Flight to safety.
   → Reduce/exit alt positions. Hold BTC. Stablecoins if BTC.D > 60%.

🔴 BTC/SPY CORRELATION rising sharply (>0.3 → >0.7 in 30 days)
   → Crypto losing its independence. Macro is taking over.
   → Transition from crypto thesis to macro thesis. Adjust signals.

🔴 ETH/BTC RISING BUT BTC.D NOT FALLING
   → ETH outperforming but not in alt-season. Specific ETH catalyst.
   → Check ETH-specific news (ETF flows, network upgrades). Don't bet on broad alt-season.

🔴 STABLECOIN SUPPLY SURGING BUT PRICE FLAT
   → Massive dry powder sitting idle. When it deploys, move will be explosive.
   → Long volatility. Position for breakout in either direction — size on the breakout.
```

## How to Query (Python)

```python
import requests
import yfinance as yf
import numpy as np

# ETH/BTC ratio
ethbtc = requests.get("https://api.binance.com/api/v3/ticker/price",
                       params={"symbol": "ETHBTC"}).json()
ratio = float(ethbtc["price"])
print(f"ETH/BTC: {ratio:.6f}")

# BTC Dominance via CoinGecko
cg = requests.get("https://api.coingecko.com/api/v3/global").json()
btc_dom = cg["data"]["market_cap_percentage"]["btc"]
print(f"BTC.D: {btc_dom:.1f}%")

# BTC/SPY 30-day correlation
btc = yf.download("BTC-USD", period="60d", progress=False)["Close"]
spy = yf.download("SPY", period="60d", progress=False)["Close"]
btc_ret = btc.pct_change().dropna()
spy_ret = spy.pct_change().dropna()
common_idx = btc_ret.index.intersection(spy_ret.index)
corr = np.corrcoef(btc_ret[common_idx].iloc[-30:],
                    spy_ret[common_idx].iloc[-30:])[0, 1]
print(f"BTC/SPY 30d correlation: {corr:.3f}")
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via CoinGecko + TradingView |
| v1 | Python script computes daily BTC.D, ETH/BTC, BTC/SPY corr → vault tracker |
| v2 | Integrated into daily signal check (adds correlation line) |
| v3 | Auto-flag when BTC/SPY correlation crosses 0.7 threshold |
| v4 | Stablecoin supply tracker — SSR computed weekly from CoinGecko/Dune |

## Integration with Thesis Checklist

When a crypto thesis uses this layer:
- [ ] Add BTC.D, ETH/BTC, BTC/SPY correlation to daily signal check
- [ ] Define thesis-specific thresholds (commodity thesis ignores this layer)
- [ ] Add "correlation regime" to confluence scoring:
  - +1 if BTC/SPY < 0.3 (crypto-native edge)
  - 0 if 0.3-0.7
  - -1 if > 0.7 (macro dominates)

## Notes

- BTC/SPY correlation is cyclical. Periods of low correlation (0.1-0.3) last 3-6 months on average.
- BTC.D below 40% historically marks alt-season peaks. BTC.D above 60% marks BTC dominance phases.
- ETH/BTC above 0.08 has only happened twice (Jan 2018, Nov 2021). Both were cycle tops.
- Stablecoin market cap is a leading indicator — changes precede price moves by 2-4 weeks.
- CoinGecko free tier: 10-30 calls/min. Caching recommended for sub-daily checks.
