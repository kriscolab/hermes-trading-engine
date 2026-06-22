# Trading Module — AGENTS.md

Schema version: v12.0 (3-engine re-architecture — June 1, 2026, v2 plan)
Updated: June 1, 2026 07:15 IST
Status: PLANNING — 3 isolated $100K engines, crypto thesis rebuilt (Fink "Institutional Inevitability"), quant+intraday complete redesign, per-engine meta-optimizers, Hyperliquid path

## Architecture

```
vault/wiki/trading/
├── AGENTS.md                          ← this file (schema + design rules)
├── ARCHITECTURE.md                    ← full system reference
├── docs/                              ← 9-file documentation suite
│   ├── MASTER_GUIDE.md, README.md, START_HERE.txt
│   ├── QUICK_REFERENCE.md, INTEGRATION_GUIDE.md
│   ├── ADVANCED_PATTERNS.md, EXTENSIONS_GUIDE.md, INDEX.md
├── theses/
│   ├── index.md                       ← 3 active theses registered
│   ├── commodity-super-cycle/         ← Currie "Mag7→Mun7" — LIVE
│   │   └── signals.md                 ← E1-E4, X1-X5
│   ├── ai-supercycle/                 ← Aschenbrenner "AGI 2027"
│   │   ├── thesis.md, instruments.md, signals.md
│   └── crypto-native/                 ← 6-layer confluence
│       ├── thesis.md, instruments.md, signals.md
├── modules/                           ← 14 analysis modules (ALL BUILT)
│   ├── price-action.md, volume-profile.md       ← L1: market structure
│   ├── derivatives.md, options.md               ← L2-L3: positioning
│   ├── liquidation.md, on-chain.md              ← L4-L5: leverage + flows
│   ├── macro.md, fundamental.md                 ← L6: macro + equity
│   ├── regime.md, session-clock.md              ← Gap 1-2: context
│   ├── sentiment.md, correlation.md             ← Gap 3-4: narrative
│   ├── position-sizing.md, smart-contracts.md   ← Gap 6: sizing + DeFi
│   └── airdrop-scanner.md                       ← Standalone: yield
├── paper-trader/
│   ├── engine.py                       ← 54KB: 3 thesis engines, 29 signals, cross-thesis allocation
│   ├── rules.md                        ← 10 global rules + Learning Log
│   └── journal.db                      ← SQLite: trades, signal_log, portfolio_snapshots (thesis_id)
├── learning/
│   ├── weekly-review.py                ← reads journal → patterns → rules.md
│   ├── missed-audit.py                 ← backtests unexecuted signals
│   └── backtester.py                   ← walk-forward signal validation
├── synthesis/
│   ├── synthesizer.py                  ← 7-component pipeline → daily_state.json
│   ├── schema.json                     ← strict JSON contract
│   ├── daily_state.json + archive/     ← daily market state
│   ├── correlator.py                   ← cross-thesis link analysis
│   ├── airdrop-scanner.py              ← 5-dimension scoring
│   └── sanity-audit.py                 ← platform health verification
├── delivery/
│   ├── formatter.py                    ← 3 modes: alert, digest, report
│   └── streamlit_dashboard.py          ← port 8501 (tmux session)
└── scripts/
    ├── fetch-prices.py                 ← yfinance → market data (commodity + AI)
    ├── crypto-data-fetch.py            ← OKX+Deribit+DeFiLlama+CoinGecko+alt.me+KuCoin
    ├── quant-aggregator.py             ← runs all 10 quant modules → /tmp/quant_signals.json
    └── polling-daemon.py               ← 6-step 5-min cycle (tmux: polling)
├── crypto-engine/quant/               ← 10 quant modules
│   ├── mean-reversion.py, momentum.py, correlation.py
│   ├── stat-arbitrage.py, monte-carlo.py, volatility-arbitrage.py
│   ├── ml-signals.py, event-driven.py, market-making.py
│   ├── microstructure.py, ensemble-meta.py  ← #10: weighted ensemble meta-model
```

## Design Principles

1. **Free data only.** All 14 modules use free global endpoints (OKX, Deribit, DeFiLlama, CoinGecko, alternative.me, KuCoin, yfinance, FRED). Coinglass/Glassnode/WhaleAlert are paid — not used.
2. **One thesis, one directory.** Self-contained with instruments, signals. All 3 share engine.py.
3. **Modules are reusable.** Written once, referenced by all theses. 14 built.
4. **Paper-trader is shared.** One engine serves all theses. Cross-thesis auto-allocation (50/50 split).
5. **Learning compounds.** Weekly review → journal.db → patterns → rules.md. Missed audit finds lost alpha. Backtester validates signal quality.
6. **Synthesis precedes execution.** Daily synthesizer runs at 8:30 AM IST. Generates daily_state.json before 9 AM signal checks.
7. **IST always.** All cron schedules, blog timelines, user-facing times in IST.

## Data Availability Notes (ALL FREE)

| Data Type | Source | Notes |
|-----------|--------|-------|
| Crypto funding, OI, liquidations | OKX public API | Global access, no key needed |
| Crypto options (IV skew) | Deribit public API | Global access, no key |
| DeFi TVL, protocols | DeFiLlama API | No key |
| Fear & Greed Index | alternative.me API | No key |
| BTC dominance, prices | CoinGecko API | Free tier |
| Backup crypto prices | KuCoin API | Global access |
| Equity/ETF prices, fundamentals | yfinance | Free, 15min delay on futures |
| Commodities (Brent, gold) | yfinance | Free, 15min delay |
| Macro (DXY, VIX, rates) | yfinance + FRED | Free |
| Energy sector weight | Fixed estimate ~4.1% | No free real-time source |
| Hyperliquid DEX | Public API | For future agentic trading |

## 6-Layer Signal Stack (Crypto Thesis)

```
L1  MARKET STRUCTURE   price-action + volume-profile      ✅ built
L2  DERIVATIVES        funding + OI (OKX)                 ✅ built
L3  OPTIONS            IV skew + term (Deribit)           ✅ built
L4  LIQUIDATIONS       liquidation data (OKX)             ✅ built
L5  ON-CHAIN           DeFi TVL proxy (DeFiLlama)         ✅ built
L6  MACRO/SENTIMENT    DXY, VIX, Fear & Greed             ✅ built
```

All 6 layers live via free global endpoints. Confluence scoring: 3/6 minimum for CRYPTO_E1 entry.

## Key Conventions

- Weekly crons run Sundays: tracker (8 PM), review (9 PM), correlation (9:15 PM), missed audit (9:30 PM) IST
- Daily crons: synthesizer (8:30 AM), commodity (9 AM), AI (9:15 AM), crypto (9:20 AM), airdrop (7:30 AM) IST
- All signals must be falsifiable (not "looks bullish" but "BTC funding rate crosses 0.01%")
- Journal.db: thesis_id on all tables for multi-thesis tracking
- Engine CLI: `python3 engine.py --thesis commodity|ai|crypto`
- Dashboard: port 8501, tmux session 'dashboard'

## Phase Plan

| Phase | What | Status |
|-------|------|--------|
| v0-v7 | Platform foundation — modules, theses, engine, signals, crons | ✅ DONE May 17 |
| v8a-h | Platform completion — 10 modules, synthesizer, audits, delivery | ✅ DONE May 17 |
| v11.0 | Full audit + consolidation — 21 fixes, Hyperliquid, Kalman, edge-gen→execution | ✅ DONE May 24 |
| v12.0 | 3-engine re-architecture — $100K isolated engines, crypto thesis v2 (Fink "Institutional Inevitability"), quant+intraday complete redesign (regime-gated, 5-point gate, risk mgmt), per-engine meta-optimizers (crypto ~100 params dedicated), 3 new quant modules, Hyperliquid path, hl.eco-inspired dashboard | 📋 PLANNING |
| Edge | AI Edge Generator — HMM regime detection, walk-forward validation, autonomous strategy discovery | ROADMAPPED |
