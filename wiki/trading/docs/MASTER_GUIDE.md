# Master Guide — Hermes Trading Platform

Platform: Multi-thesis automated trading research & execution
Version: v8h (complete)
Last updated: May 17, 2026

## What This Platform Does

This is a 3-thesis trading research platform that:
1. **Tracks** 3 investment theses (commodities, AI, crypto) using real market data
2. **Scores** confluence across 12 data modules before any trade
3. **Executes** paper trades via a journaled engine with idempotent signals
4. **Learns** from outcomes via weekly reviews and missed-opportunity audits
5. **Synthesizes** a daily unified market state (composite score, regime, risks)
6. **Delivers** all output to Telegram via standardized formatting

## What You Need Before Starting

### API Keys (4 free signups, ~15 min)
- [ ] Coinglass API key (coinglass.com) — crypto derivatives data
- [ ] Glassnode API key (glassnode.com) — on-chain flows
- [ ] Whale Alert API key (whale-alert.io) — whale tracking
- [ ] CryptoQuant account (cryptoquant.com) — exchange reserves

### System Requirements
- Python 3.12+ with yfinance, requests, sqlite3
- Playwright + Chromium (for Browser Use scraping)
- ~/vault/ directory structure (LLM Wiki pattern)

## Architecture at a Glance

```
DATA → MODULES → ENGINE → SYNTHESIS → DELIVERY
  │        │        │         │           │
  │   12 analysis  Paper     Daily     Telegram
  │   modules     Trader    State      @hermestradingdesk
  │              journal    JSON
  │
fetch-prices.py (yfinance, free)
```

## The Three Theses

| Thesis | Engine Flag | Status | Active Position |
|--------|-----------|--------|----------------|
| Commodity Super Cycle | `--thesis commodity` | LIVE | SHORT GLD 11.98 @ $417.29 |
| AI Supercycle | `--thesis ai` | DEFINED | None (watching) |
| Crypto Accumulation | `--thesis crypto` | DEFINED | None (data feeds pending) |

## Quick Start — 3 Commands to Know

```bash
# 1. Fetch live prices
cd ~/vault/wiki/trading
python3 scripts/fetch-prices.py --portfolio

# 2. Check commodity thesis signals
cd paper-trader
python3 engine.py --thesis commodity --data /tmp/live_market_data.json

# 3. See portfolio with mark-to-market
python3 engine.py --summary --prices '{"GLD":417.29}'
```

## Daily Cron Schedule (All Times IST)

```
7:30 AM  Airdrop ranking          → @hermestradingdesk
8:30 AM  Strategy Synthesizer     → daily_state.json
9:00 AM  Commodity signal check   → @hermestradingdesk
9:15 AM  AI signal check          → @hermestradingdesk
9:20 AM  Crypto signal check      → @hermestradingdesk
9:15 AM  Daily catch-up digest    → DM
```

## Weekly Cron Schedule (Sundays IST)

```
8:00 PM  Commodity weekly tracker
8:30 PM  AI weekly tracker
8:45 PM  Crypto weekly tracker
9:00 PM  Weekly review / learning
9:15 PM  Cross-thesis correlation
9:30 PM  Missed opportunity audit
```

## Documentation Map

| File | Read When |
|------|-----------|
| **MASTER_GUIDE.md** (this file) | First time — overview |
| **START_HERE.txt** | 30-second visual quick start |
| **README.md** | Feature inventory with status |
| **QUICK_REFERENCE.md** | Cheat sheet of all commands |
| **ARCHITECTURE.md** | Design, data flow, directory map |
| **INTEGRATION_GUIDE.md** | How to add a thesis/module/cron |
| **ADVANCED_PATTERNS.md** | Confluence patterns, sizing rules |
| **EXTENSIONS_GUIDE.md** | Browser Use, API configuration |
| **INDEX.md** | File navigation map |

## Health Check

```bash
cd ~/vault/wiki/trading
python3 synthesis/sanity-audit.py --summary
```

Expected output: ✅ All checks passed. Platform healthy.
