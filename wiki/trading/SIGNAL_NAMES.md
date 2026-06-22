# SIGNAL NAMES — Quick Reference

Version: v2
Updated: May 18, 2026

## 6-Layer Signal Stack (What Each Layer Includes)

| Layer | Name | What It Tracks | Data Source |
|-------|------|---------------|-------------|
| **L1** | Market Structure | Price Action (candlestick patterns), Volume Profile (VWAP, volume surges) | yfinance OHLCV |
| **L2** | Derivatives | Funding Rate (% per 8h), Open Interest ($), OI change 24h | OKX public API |
| **L3** | Options | IV Skew (% 25-delta), Term Structure, Max Pain | Deribit public API |
| **L4** | Liquidations | Recent liquidation count, Long/Short ratio, Cascade detection | OKX public API |
| **L5** | On-Chain | DeFi TVL ($B), Exchange netflows, Whale moves, BTC.D | DeFiLlama + CoinGecko |
| **L6** | Macro/Sentiment | DXY, VIX, Real Rates, Fear & Greed Index | yfinance + alt.me |

---

## Commodity Thesis (Currie "Mag7→Mun7 Rotation")

```
CO-BRENT     Brent Breakout (weekly close > 50-SMA)     → 50% into Mun7
CO-PULLBACK  Brent Pullback to Value Zone                → 25% into Mun7
CO-ROTATE    Rotation Signal (XLE/XLK ratio rising)     → 25% into Mun7
CO-GOLD-S    Gold Short (GLD > $4,200 + DXY > 99)       → 5% into GLD short
CO-GOLD-L    Gold Long (GLD structural, DXY < 95)       → 5% into GLD long

CO-HORMUZ    EXIT: Hormuz Reopens                        → close all energy
CO-CAPEX     EXIT: Mag7 Capex Collapse (<10% YoY)        → close all energy
CO-WEIGHT    EXIT: Energy Weight > 10% S&P               → close all energy
CO-CONTANGO  EXIT: Brent Futures Contango                → close all energy
CO-FCF       EXIT: Mun7 FCF Yield < 3%                   → close all energy
```

## AI Supercycle Thesis (Aschenbrenner "AGI 2027")

```
AI-CAPEX      Capex Acceleration (hyperscaler capex QoQ >20%)    → 25% into AI basket
AI-FRONTIER   Next Frontier Model (new model >10x compute)       → 25% into AI basket
AI-POWER      Power Deal (grid constraint benefits AI infra)     → 25% into AI basket
AI-FAB        Semi Fab Cluster (new cluster >100K GPUs)          → 25% into AI basket
AI-DC         DC Consolidation (hyperscaler DC concentration)    → 25% into AI basket

AI-JEVONS     EXIT: Jevons Paradox (open-source = 10% compute)   → close all AI
AI-REV-DECEL  EXIT: Revenue Deceleration (<30% YoY, 2Q)          → close all AI
AI-GRID       EXIT: Grid Expansion (>30% YoY drop in queue)      → close all AI
AI-EXIT       EXIT: Aschenbrenner Exits (13F: CRWV/BE sold)      → close all AI
AI-EXPORT     EXIT: GPU Export Controls (restrictions imposed)    → close all AI
```

## Crypto Thesis (6-Layer Confluence — Institutional Accumulation)

```
C-ACCUM-3L    Accumulation 3-Layer (confluence ≥ 3/6)     → 15% into BTC/ETH
C-ACCUM-4L    Accumulation 4-Layer (confluence ≥ 4/6)     → 25% into BTC/ETH
C-ONCHAIN     On-Chain Divergence (price↓ reserves↓ 5%)    → 15% into BTC
C-VOL-BRK     Volume Breakout (vol 2x + price > VWAP)     → 15% into BTC

C-DISTRIB     EXIT: Distribution (exchange reserves +5% 7d)  → close all crypto
C-WHALE-OUT   EXIT: Whale Outflow (single TX >$50M)          → close all crypto  
C-OVERHEAT    EXIT: Overheating (F&G >80 or funding >0.1%)   → close all crypto
C-BTC-SPY     EXIT: BTC/SPY Correlation (>0.7 30d)           → close all crypto
C-REG         EXIT: Regulatory Shock (major action)           → close all crypto
```

## Quant Edge Signals

```
Q-MR-BTC       Mean Reversion BTC   (BB + RSI + Z-score, edge ≥ 40)
Q-MR-ETH       Mean Reversion ETH   (BB + RSI + Z-score, edge ≥ 40)
Q-MR-SOL       Mean Reversion SOL   (BB + RSI + Z-score, edge ≥ 40)
Q-MO-BTC       Momentum BTC         (EMA/ADX/Donchian, edge ≥ 55)
Q-MO-ETH       Momentum ETH         (EMA/ADX/Donchian, edge ≥ 55)
Q-MO-SOL       Momentum SOL         (EMA/ADX/Donchian, edge ≥ 55)
Q-SA-BTCETH    Stat Arb BTC/ETH     (Spread Z-score > 2.0)
Q-SA-ETHSOL    Stat Arb ETH/SOL     (Spread Z-score > 2.0)
Q-CORR-DECOUP  Decoupling           (BTC/SPY 14d corr < 0.3)
Q-CORR-COUPLE  High Correlation     (BTC/SPY 14d corr > 0.7)
```

## Price Action & Volume Signals

```
PA-DOJI         Doji candle (indecision, body <10% range)
PA-ENGULF-BULL  Bullish Engulfing (reversal up)
PA-ENGULF-BEAR  Bearish Engulfing (reversal down)
PA-HAMMER       Hammer (bottom reversal, lower shadow 2x body)
PA-SHOOTING     Shooting Star (top reversal)

VW-SURGE        Volume Surge (vol > 2x 20d avg)
VW-ABOVE        Price Above VWAP (bullish structure)
VW-BELOW        Price Below VWAP (bearish structure)
```
