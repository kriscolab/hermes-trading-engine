# Quick Reference — All Commands & Templates

## Engine (paper-trader/engine.py)

```bash
# Signal checks
python3 engine.py --data /tmp/live_market_data.json                    # commodity (default)
python3 engine.py --thesis ai --data /tmp/live_market_data.json        # AI thesis
python3 engine.py --thesis crypto --data /tmp/live_market_data.json    # crypto thesis

# Confluence recommendations
python3 engine.py --data /tmp/live_market_data.json --recommend

# Portfolio
python3 engine.py --summary                                             # entry prices only
python3 engine.py --summary --prices '{"GLD":417.29,"XLE":59.44}'      # mark-to-market

# Execution (with idempotency)
python3 engine.py --data /tmp/live_market_data.json --execute

# History
python3 engine.py --history
```

## Data Pipeline (scripts/fetch-prices.py)

```bash
python3 scripts/fetch-prices.py                    # market data → /tmp/live_market_data.json
python3 scripts/fetch-prices.py --portfolio        # + portfolio prices → /tmp/portfolio_prices.json
python3 scripts/fetch-prices.py --all              # + all tracker prices (Mun7, Mag7, AI)
```

## Synthesis Layer

```bash
python3 synthesis/synthesizer.py                    # full pipeline → stdout
python3 synthesis/sanity-audit.py --summary         # platform health check
python3 synthesis/correlator.py --summary           # cross-thesis links
python3 synthesis/airdrop-scanner.py --summary      # airdrop rankings
python3 synthesis/airdrop-scanner.py --live         # live scraping mode
```

## Learning Loop

```bash
python3 learning/weekly-review.py --summary         # weekly trade analysis
python3 learning/missed-audit.py --summary          # missed signals backtest
python3 learning/missed-audit.py --days 30          # look back 30 days
```

## Delivery

```bash
python3 delivery/formatter.py                       # test all formatting modes
```

## Market Data JSON Template

```json
{
  "brent_close": 109.26, "brent_50sma": 100.52,
  "gold": 4561.9, "dxy": 99.27, "dxy_rising": true,
  "vix": 18.43, "xle_price": 59.44, "xlk_price": 176.26,
  "mun7_fcf_yield": 0.155, "energy_weight": 0.041,
  "real_rates": "unknown", "cb_dovish": false,
  "hormuz_reopen_news": false, "mag7_capex_drop": 0.0,
  "brent_contango_4w": false, "brent_volume_surge": false,
  "mun7_price": 59.44
}
```

## Portfolio Prices Template

```json
{"GLD": 417.29, "XLE": 59.44}
```

## Journal.db Schema

```
trades:              id, trade_date, symbol, direction, entry_price,
                     shares, entry_signal, exit_date, exit_price,
                     exit_signal, pnl_realized, status, notes, thesis_id

signal_log:          id, check_date, signal_id, triggered, executed,
                     notes, thesis_id

portfolio_snapshots: id, snap_date, cash, deployed, equity,
                     realized_pnl, open_positions, thesis_id
```

## Cron Job Schedule

| Cron ID | Name | Schedule (IST) |
|---------|------|---------------|
| 595dce2af589 | Airdrop Ranking | Daily 7:30 AM |
| 16f3064fe579 | Strategy Synthesizer | Daily 8:30 AM |
| 144363e032bf | Commodity Signal Check | Daily 9:00 AM |
| 66895a17aab1 | AI Signal Check | Daily 9:15 AM |
| 35f88061bcfa | Daily Catch-Up Digest | Daily 9:15 AM |
| b9acf3720968 | Crypto Signal Check | Daily 9:20 AM |
| 9e15b384daa0 | arXiv Digest | Daily 10:00 AM |
| 35f039b1f202 | Commodity Weekly | Sun 8:00 PM |
| a82eb47ea34a | AI Weekly Tracker | Sun 8:30 PM |
| e55c9fb22f4b | Crypto Weekly Tracker | Sun 8:45 PM |
| cce17e8eebb0 | Weekly Review | Sun 9:00 PM |
| e4671b567c9f | Cross-Thesis | Sun 9:15 PM |
| 79441659c835 | Missed Audit | Sun 9:30 PM |
| eb4f03bed9d8 | Monday Review | Mon 4:00 PM |
