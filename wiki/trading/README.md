# Hermes Trading Platform

**v10.7** — Multi-thesis automated paper trading system. 3 theses. 29 signals. 10 quant modules. Risk engine with auto-execute. Dashboard on port 8501.

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

**v10.7** (May 20, 2026). Full history: [VERSION_AUDIT.md](VERSION_AUDIT.md)

| File | Purpose |
|------|---------|
| `AGENTS.md` | Schema + design rules |
| `ARCHITECTURE.md` | Full system reference |
| `VERSION_AUDIT.md` | Version history |
| `paper-trader/rules.md` | Trading rules + learning log |

---

## Current State

```
28 Python files · 8-step polling · 10 quant modules + MC + ensemble
3 theses · 29 signals · Risk engine v1.1 · Dashboard v3.2
20 crons · 3 tmux sessions · 0 pending gaps
9 positions · $67.6K deployed
```
