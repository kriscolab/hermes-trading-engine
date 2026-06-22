# Trading Platform — Complete System Reference

Version: v11.0
Last updated: May 24, 2026 19:15 IST
Status: PLATFORM CONSOLIDATED — 21 fixes, Hyperliquid migration, Kalman filter, edge-gen→execution, standalone engines, signal fidelity monitor active

---

## 1. DIRECTORY STRUCTURE

```
vault/wiki/trading/
├── ARCHITECTURE.md                    ← THIS FILE — complete reference
├── AGENTS.md                          ← schema, design rules, phase plan
├── VERSION_AUDIT.md                   ← single source of truth for version history
├── SIGNAL_NAMES.md                    ← naming convention
│
├── theses/                            ← strategy registry
│   ├── index.md                       ← catalog (3 active theses)
│   ├── commodity-super-cycle/         ← Currie "Mag7→Mun7" — LIVE
│   ├── ai-supercycle/                 ← Aschenbrenner "AGI 2027"
│   └── crypto-native/                 ← 6-layer confluence
│
├── modules/                           ← 14 analysis modules (markdown reference)
│   ├── price-action.md, volume-profile.md       ← L1: market structure
│   ├── derivatives.md, options.md               ← L2-L3: positioning
│   ├── liquidation.md, on-chain.md              ← L4-L5: leverage + flows
│   ├── macro.md, fundamental.md                 ← L6: macro + equity
│   ├── regime.md, session-clock.md              ← Gap 1-2: context
│   ├── sentiment.md, correlation.md             ← Gap 3-4: narrative
│   ├── position-sizing.md, smart-contracts.md   ← Gap 6: sizing + DeFi
│   └── airdrop-scanner.md                       ← Standalone: yield
│
├── paper-trader/                      ← execution engine
│   ├── engine.py                      ← 67KB: 3 thesis engines, 29 signals, cross-thesis allocation
│   ├── rules.md                       ← 10 global rules + Learning Log
│   └── journal.db                     ← SQLite: trades, signal_log, portfolio_snapshots, synthesizer_snapshots
│
├── learning/                          ← feedback loops
│   ├── weekly-review.py               ← reads journal + synth_snapshots → weekly-review.md
│   ├── missed-audit.py                ← backtests unexecuted signals w/ regime correlation (v10.3)
│   ├── backtester.py                  ← walk-forward validation w/ real dates + regime (v10.3)
│   ├── weekly-review.md, missed-opportunities.md, backtest-report.md
│
├── synthesis/                         ← strategic layer
│   ├── synthesizer.py                 ← v2.0 programmatic: regime, confluence, risk, thesis bias (370 lines)
│   ├── edge-generator.py              ← v1.1: unified quant+thesis+crypto scores → /tmp/edge_generator.json
│   ├── risk-engine.py                 ← v1.0: TP/SL alerts, position risk monitoring → /tmp/risk_alerts.json
│   ├── correlator.py                  ← cross-thesis link analysis (10 patterns)
│   ├── airdrop-scanner.py             ← 5-dimension scoring
│   ├── sanity-audit.py                ← 6-check platform health verification
│   ├── daily_state.json + archive/    ← daily market state + historical snapshots
│   └── schema.json                    ← strict JSON contract
│
├── crypto-engine/quant/               ← 10 quant modules (all standalone, run by aggregator)
│   ├── mean-reversion.py              ← #1: BB, RSI, Z-score
│   ├── momentum.py                    ← #2: EMA, ADX, Donchian, MACD
│   ├── correlation.py                 ← #3: cross-asset + cross-crypto matrix
│   ├── stat-arbitrage.py              ← #4: pair trading, spread Z-score
│   ├── monte-carlo.py                 ← #5: 500-sim validation + direction-aware (v10.1, wired v10.5)
│   ├── volatility-arbitrage.py        ← #6: Parkinson vol, vol-of-vol
│   ├── ml-signals.py                  ← #7: ADX regime detection, anomaly scoring
│   ├── event-driven.py                ← #8: OKX funding/liquidations/OI events
│   ├── market-making.py               ← #9: spread/vol ratio, depth proxy
│   ├── microstructure.py              ← #10: Amihud, OFI, VWAP deviation
│   └── ensemble-meta.py               ← meta: weighted avg of all 10 modules, adaptive weights
│
├── delivery/                          ← output + interface
│   ├── streamlit_dashboard.py         ← v3.1: 6-tab dashboard (port 8501, tmux session)
│   ├── formatter.py                   ← 3 modes: alert, digest, report
│   └── dashboard.py                   ← (deprecated: headless version)
│
├── scripts/                           ← data pipeline
│   ├── polling-daemon.py              ← 7-step 5-min cycle (tmux: polling)
│   ├── crypto-data-fetch.py           ← OKX+Deribit+DeFiLlama+CoinGecko+alt.me+KuCoin
│   ├── fetch-prices.py                ← yfinance → /tmp/{live_market,portfolio,ai_tracker}_*.json
│   └── quant-aggregator.py            ← runs 10 quant modules + ensemble → /tmp/quant_signals.json
│
├── docs/                              ← 9-file documentation suite
│   ├── MASTER_GUIDE.md, README.md, START_HERE.txt
│   ├── QUICK_REFERENCE.md, INTEGRATION_GUIDE.md
│   ├── ADVANCED_PATTERNS.md, EXTENSIONS_GUIDE.md, INDEX.md
│
└── /tmp/ output files (all consumers)
    ├── crypto_module_data.json         ← crypto-data-fetch.py → quant, edge, dashboard, engine
    ├── live_market_data.json           ← fetch-prices.py → synthesizer, edge, engine
    ├── portfolio_prices.json           ← fetch-prices.py → dashboard (position P&L)
    ├── ai_tracker_prices.json          ← fetch-prices.py → synthesizer, engine
    ├── quant_signals.json              ← quant-aggregator.py → dashboard, edge, ensemble
    ├── edge_generator.json             ← edge-generator.py → dashboard (Edge Lab)
    ├── risk_alerts.json                ← risk-engine.py → dashboard (risk monitoring)
    └── data_freshness.json             ← polling-daemon.py → dashboard (data age)
```

---

## 2. THREE THESES

### Commodity Super Cycle (Currie) — LIVE
```
Engine:  python3 engine.py --thesis commodity (default)
Position: SHORT GLD 11.98 @ $417.29 [E4S]
Signals:  E1-E4 entry, X1-X5 exit (9 total)
Data:    yfinance (Brent, gold, DXY, XLE, XLK, VIX)
Crons:   Daily 9:00 AM signal check, Sun 8:00 PM weekly tracker
```

### AI Supercycle (Aschenbrenner) — DEFINED
```
Engine:  python3 engine.py --thesis ai
Position: None (all signals idle)
Signals: AI_E1-E5 entry, AI_X1-X5 exit (10 total)
Data:    yfinance (SOXX, IGV, DTCR, TAN, XLC, INTC, CRWV, BE, CORZ)
Crons:   Daily 9:15 AM signal check, Sun 8:30 PM weekly tracker
```

### Crypto Accumulation — DEFINED
```
Engine:  python3 engine.py --thesis crypto
Position: None (all signals idle — data feeds pending)
Signals: CRYPTO_E1-E4 entry, CRYPTO_X1-X5 exit (10 total)
Data:    Binance, Coinglass, Deribit, Glassnode, Dune (all free tiers)
Crons:   Daily 9:20 AM signal check, Sun 8:45 PM weekly tracker
Confluence: 0-6 layer scoring per check
```

---

## 3. 6-LAYER SIGNAL STACK (Crypto)

```
L1  MARKET STRUCTURE   price-action + volume-profile      ○ deferred
L2  DERIVATIVES        funding + OI (Coinglass)            ✅ built
L3  OPTIONS            IV skew + term (Deribit)            ✅ built
L4  LIQUIDATIONS       heatmaps (Coinglass/Hyblock)        ✅ built
L5  ON-CHAIN           flows + whales (Glassnode/Dune)     ✅ built
L6  MACRO/SENTIMENT    DXY, VIX, Fear & Greed              ✅ built

Gaps filled:
  G1  Regime           ADX/ATR classifier                  ✅ built
  G2  Session Clock    Asia/London/NY                      ✅ built
  G3  Sentiment        Fear & Greed + Polymarket           ✅ built
  G4  Correlation      BTC.D, ETH/BTC, BTC/SPY             ✅ built
  G5  Trade Journal    journal.db                          ✅ built
  G6  Position Sizing  ATR/Kelly/correlation penalty       ✅ built

Modules deferred (harder data requirements):
  price-action.md, volume-profile.md, fundamental.md
```

---

## 4. ENGINE (engine.py)

```
Commands:
  python3 engine.py --thesis commodity|ai|crypto
  python3 engine.py --data /tmp/live_market_data.json
  python3 engine.py --summary --prices '{"GLD":417}'
  python3 engine.py --recommend
  python3 engine.py --execute
  python3 engine.py --history

Classes:
  Portfolio      — cash, positions, P&L
  SignalChecker  — evaluates 29 signals across 3 theses
  TradeExecutor  — idempotent 30-day dedup, exit-before-entry
  ConfluenceAnalyzer — cross-layer confidence scoring (🟢🟡🔴)
  JournalDB      — SQLite: trades, signal_log, portfolio_snapshots

Database (journal.db):
  trades:              id, trade_date, symbol, direction, entry_price,
                       shares, entry_signal, exit_date, exit_price,
                       exit_signal, pnl_realized, status, notes, thesis_id
  
  signal_log:          id, check_date, signal_id, triggered,
                       executed, notes, thesis_id
  
  portfolio_snapshots: id, snap_date, cash, deployed, equity,
                       realized_pnl, open_positions, thesis_id
```

---

## 5. DATA PIPELINE

```
fetch-prices.py (yfinance, free)
  ↓
/tmp/live_market_data.json     → engine.py --data
/tmp/portfolio_prices.json     → engine.py --summary --prices
/tmp/tracker_prices.json       → weekly tracker (21 instruments)
/tmp/ai_tracker_prices.json    → AI weekly tracker (10 instruments)
```

### Data Sources (all free)

| Source | What | Rate Limit |
|--------|------|-----------|
| yfinance | Stocks, ETFs, commodities | No limit (fair use) |
| Binance API | BTC/ETH price | No key needed |
| Coinglass | Funding, OI, liquidations | 30 req/min (key pending) |
| Deribit API | Options IV, skew | 20 req/sec (no key) |
| Glassnode | On-chain flows | 1 req/sec (key pending) |
| DeFiLlama | TVL, protocols | Generous (no key) |
| alternative.me | Fear & Greed | 60 req/min (no key) |
| Whale Alert | Large transactions | 10 req/min (key pending) |
| Dune Analytics | Pre-built dashboards | No key needed |
| Polymarket | Event probabilities | No key needed |

### Known Limitations
- Commodity futures: 15-min delayed (yfinance free tier)
- Energy sector weight: fixed at ~4.1% (no free real-time source)
- Real rates: TIP ETF proxy, may fail (network-dependent)
- Hormuz/capex news: manual triggers
- Crypto module data: pending API keys

---

## 6. SYNTHESIS LAYER

```
synthesizer.py (25KB, 7 components):
  1. ModuleScanner    — reads 12 markdown modules
  2. ThesisScanner    — reads journal.db signals + positions
  3. MarketFetcher    — runs fetch-prices.py
  4. ContextBuilder   — single structured prompt (~2.2K tokens)
  5. ModelInterface   — system prompt + schema → agent generates JSON
  6. Validator        — JSON validation + safe fallback state
  7. Writer           — daily_state.json + archive

Output: synthesis/daily_state.json
  - market_regime (RISK_ON/CAUTIOUS/etc)
  - composite_confluence_score (-5 to +5)
  - primary_risk_factor
  - divergences (gold vs DXY, real rates gap, etc)
  - thesis_recommendations (per thesis: bias, action, size_adjustment)
  - data_gaps

Cron: 16f3064fe579 — daily 8:30 AM IST (silent, feeds 9 AM checks)
```

---

## 7. CRON DELIVERY SCHEDULE

```
DM (@Tejahermes1bot):
  9:00 AM  System health heartbeat
  9:15 AM  Daily catch-up digest + trading one-liner
 10:00 AM  arXiv digest
 12:30 AM  Nightly author blog
  Mon 4 PM Monday pending projects review

@hermestradingdesk (-1003894402844):
  DAILY:
    7:30 AM  Airdrop ranking
    8:30 AM  Strategy Synthesizer (silent)
    9:00 AM  Commodity signal check
    9:15 AM  AI signal check
    9:20 AM  Crypto signal check

  SUNDAY:
    8:00 PM  Commodity weekly tracker
    8:30 PM  AI weekly tracker
    8:45 PM  Crypto weekly tracker
    9:00 PM  Weekly review / learning loop
    9:15 PM  Cross-thesis correlation
    9:30 PM  Missed opportunity audit
```

---

## 8. VERSION HISTORY

```
v0  ✅ May 16   Thesis codified, tracker cron live
v1  ✅ May 16   9 entry/exit signals, $100K portfolio
v2a ✅ May 16   derivatives.md + on-chain.md
v2b ✅ May 17   options.md + liquidation.md
v3  ✅ May 17   Paper-trader engine + journal.db + rules.md
v4  ✅ May 17   Confluence analyzer + agent recommendations
v5  ✅ May 17   Learning loop + weekly review script
v6  ✅ May 17   AI Supercycle live in engine (thesis_id, 10 signals)
v7  ✅ May 17   Crypto thesis (6-layer, 10 signals, confluence scoring)
v8a ✅ PAUSED   7/10 modules built, 3 deferred
v8b ✅ May 17   Strategy Synthesizer (synthesizer.py + schema.json)
v8c ✅ May 17   Missed Opportunity Audit (missed-audit.py)
v8d ✅ May 17   Delivery Module (formatter.py, 3 modes)
v8e ✅ May 17   AI + Crypto crons (4 new, 14 total)
v8f ✅ May 17   Cross-Thesis Correlator (10 patterns)
v8g ✅ May 17   Airdrop Scanner (5-dimension scoring)
v8h ✅ May 17   Sanity Audit (6 checks, platform verified)
```

---

## 9. QUICK COMMANDS

```
# Signal checks
cd ~/vault/wiki/trading/paper-trader
python3 engine.py --thesis commodity --data /tmp/live_market_data.json
python3 engine.py --thesis ai --data /tmp/live_market_data.json
python3 engine.py --thesis crypto --data /tmp/live_market_data.json

# Portfolio
python3 engine.py --summary --prices '{"GLD":417.29,"XLE":59.44}'

# Fetch prices
cd ~/vault/wiki/trading
python3 scripts/fetch-prices.py --portfolio
python3 scripts/fetch-prices.py --all

# Synthesis
python3 synthesis/synthesizer.py
python3 synthesis/sanity-audit.py --summary

# Learning
python3 learning/weekly-review.py --summary
python3 learning/missed-audit.py --summary

# Delivery
python3 delivery/formatter.py
```
