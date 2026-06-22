# Hermes Trading Platform

**v11.0** (v12.0 PLANNING) — Multi-thesis automated paper trading system. 3 theses, 29 signals, 10 quant modules, 3 isolated $100K engines (crypto/commodity/AI). Risk engine with auto-execute. Dashboard on port 8501.

> **Version history:** [VERSION_AUDIT.md](VERSION_AUDIT.md) — v0→v12 chronicled with every decision, bug fix, and data source change. **AGENTS.md** for schema + phase plan. **ARCHITECTURE.md** for full system reference.

---

## Overview

An autonomous paper trading platform managing a $100K simulated portfolio across three investment theses. It fetches live market data every 5 minutes, runs 10 quantitative modules, synthesizes a unified market view, executes trades automatically, and learns from outcomes.

Built with free, open data sources — no paid APIs required.

---

## Quick Start

```bash
# Dashboard (port 8501)
tmux new-session -d -s dashboard "cd ~/vault/wiki/trading && streamlit run delivery/streamlit_dashboard.py --server.port 8501 --server.headless true"

# Polling daemon (5-min cycle)
tmux new-session -d -s polling "cd ~/vault/wiki/trading && python3 scripts/polling-daemon.py"

# Check health
python3 synthesis/sanity-audit.py
```

---

## Architecture

```
Data Layer        →  crypto fetch, price fetch, polling daemon
Quant Layer       →  10 modules (momentum, mean-rev, MC, etc.) + ensemble meta-model
Synthesis Layer   →  regime detection, edge scoring, risk monitoring
Execution Layer   →  engine.py — signal checks, trade execution, journaling
Learning Layer    →  backtester, missed-audit, weekly review
Delivery Layer    →  Streamlit dashboard (6 tabs), Telegram crons
```

### 7-Step Polling Cycle (every 5 min)

1. crypto-data-fetch → market data
2. fetch-prices → portfolio mark-to-market
3. fetch-prices → AI tracker prices
4. quant-aggregator → 10 quant modules + ensemble
5. edge-generator → unified scores per ticker
6. synthesizer → market regime + risk + thesis bias
7. risk-engine → position TP/SL monitoring + auto-execute

---

## Theses

| Thesis | Instruments | Signals | Positions |
|--------|------------|---------|-----------|
| 🛢️ Commodity | GLD, XLE | 5 entry + 5 exit | 2 |
| 🤖 AI Supercycle | SOXX, IGV, DTCR, TAN, XLC | 5 entry + 5 exit | 5 |
| 🪙 Crypto | IBIT (BTC), ETHA (ETH) | 4 entry + 5 exit | 2 |

---

## Risk Management

| Level | Trigger | Action |
|-------|---------|--------|
| T1 | +10% | Exit 50% of position |
| T2 | +20% | Exit 30% of original |
| Stop | -15% | Full close (crypto only) |

Commodity/AI theses are long-duration — no hard stops. Crypto has hard stop at -15%.

---

## Key Commands

```bash
python3 paper-trader/engine.py --summary           # Portfolio overview
python3 paper-trader/engine.py --thesis ai --execute  # Check + execute
python3 scripts/quant-aggregator.py                # Run all quant modules
python3 synthesis/synthesizer.py --summary         # Market regime + bias
python3 synthesis/risk-engine.py --execute         # Auto-close TP/SL breaches
python3 synthesis/sanity-audit.py                  # Platform health check
python3 learning/backtester.py --summary           # Walk-forward backtest
python3 learning/missed-audit.py --summary         # Missed opportunity audit
```

---

## Version

**v11.0** (May 24, 2026) — Platform consolidated: 21 fixes, Hyperliquid migration, Kalman filter, standalone engines, signal fidelity monitor.
**v12.0** — PLANNING: 3-isolated $100K engines, crypto thesis rebuilt (Fink "Institutional Inevitability"), quant+intraday complete redesign, per-engine meta-optimizers.

Full history: [VERSION_AUDIT.md](VERSION_AUDIT.md) — every session, decision, bug fix, and data source change from v0 (May 16) through v12 plan.

| File | Purpose |
|------|---------|
| `AGENTS.md` | Schema + design rules + phase plan |
| `ARCHITECTURE.md` | Full system reference |
| `VERSION_AUDIT.md` | Version history (single source of truth) |
| `paper-trader/rules.md` | Trading rules + learning log |

---

## Current State

```
v11.0 platform. 3 theses. 29 signals. 10 quant modules + MC + ensemble + Kalman.
3 standalone engines. 8-step polling. Risk engine v1.0. Dashboard v3.2.
21 fixes in v11.0 audit. Hyperliquid data layer. Standalone quant + intraday journals.
21 crons healthy. 0 pending gaps (P3 cosmetic items remain).
```
