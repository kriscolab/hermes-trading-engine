# Paper Trader — Global Trading Rules

Version: v3
Status: ACTIVE
Last updated: May 17, 2026

These rules apply to ALL theses. Thesis-specific rules live in `theses/<name>/signals.md`.

---

## 1. Capital Allocation

| Rule | Detail |
|------|--------|
| Starting capital | $100,000 (paper) |
| Max per thesis | 100% when only 1 thesis active. Capped at 50% when 2+ theses active. |
| Max per position | 50% of thesis allocation (diversification within thesis) |
| Max per entry signal | As defined in signals.md (typically 25-50% of thesis allocation) |
| Rebalancing | Manual only. No automatic rebalancing between theses. |

## 2. Entry Rules

- **Scale in.** Never lump-sum. Minimum 2 entries, maximum 4 per thesis.
- **Pullback only.** Entries only on pullbacks to defined levels (MA, VWAP, value area). No chasing breakouts without confirmation.
- **Confirmation required.** Any entry needs at least one corroborating signal from an adjacent layer (e.g., price action + derivatives, or on-chain + options).
- **Weekend filter.** No entries on Friday after 4 PM IST. Wait for Monday open.
- **News blackout.** No entries within 2 hours of FOMC, CPI, or OPEC announcements.

## 3. Exit Rules

- **Thesis invalidation FIRST.** Exit signals in signals.md are the primary exit mechanism. No discretionary exits within 90 days of entry unless a thesis claim breaks.
- **Take profit in thirds.** At Target 1: exit 50%. At Target 2: exit 30%. Remaining 20% is runner — trail with 20% drawdown from peak.
- **No stop-loss hunting.** No hard price stops for long-duration theses. Price-based stops are for short-term trades only.
- **80/20 rule for short positions.** Cover shorts at 80% of target (the last 20% is never captured cleanly).

## 4. Position Sizing

- **ATR-based for short-term trades.** For any trade with a defined price target < 30 days, size = (risk_amount) / (ATR × multiplier).
- **Kelly-inspired for thesis entries.** Size = (edge × capital) / variance. Simplified: max 25% per entry, 50% total per thesis.
- **Correlation penalty.** If two positions have correlation > 0.7, combined size capped at 125% of single-position max.
- **Gold exception.** Gold tactical short (E4S) capped at 5% regardless of Kelly. Structural long (E4L) capped at 10%.

## 5. Risk Management

- **Max drawdown per thesis: 25%.** If a thesis drawdown exceeds 25%, freeze all new entries for that thesis. Review thesis claims manually.
- **Max portfolio drawdown: 30%.** If total portfolio drawdown exceeds 30%, freeze all new entries across all theses.
- **Concentration limit.** No single ticker > 20% of deployed capital (except XLE which is a basket).
- **Leverage prohibition.** Paper-trader does not use leverage. All positions are 1x cash. This is a research platform, not a prop trading desk.

## 6. Idempotency

- **One signal = one execution.** Running `engine.py --execute` twice on the same day must not double-enter. Signal log with 30-day dedup window.
- **Exit before entry.** Exit signals are processed before entry signals in every run.
- **Snapshot on every execution.** Portfolio snapshot is written to journal.db after every `--execute` run.

## 7. Data Quality

- **Price source:** yfinance for equities/ETFs, web scrape for commodities (Brent, gold).
- **Acceptable lag:** 24 hours for weekly checks, 1 hour for daily signal checks.
- **Missing data rule:** If any data point fails to fetch, log the gap. Do NOT execute on incomplete data.
- **Outlier filter:** Prices ±30% from previous close are rejected (data error, not signal).

## 8. Reporting

- **Daily signal check:** Runs via cron 144363e032bf at 9:00 AM IST. Reports all 9 signal statuses + portfolio snapshot to @hermestradingdesk.
- **Weekly tracker:** Runs via cron 35f039b1f202 at Sun 8 PM IST. Fetches all instrument prices, updates thesis tracker, reports Mun7 vs Mag7 comparison.
- **Monday review:** Runs via cron eb4f03bed9d8 at Mon 4 PM IST. Pending projects + trading thesis status to DM.
- **Trade log format:** `[COMMODITY] #trade | ENTRY/EXIT | Signal: X | Symbol: Y | Size: Z | Price: $W | Rationale: ...`

## 9. Journal Schema (journal.db)

```
trades:
  id, trade_date, symbol, direction, entry_price, shares,
  entry_signal, exit_date, exit_price, exit_signal,
  pnl_realized, status (open/closed/pending), notes

signal_log:
  id, check_date, signal_id, triggered, executed, notes

portfolio_snapshots:
  id, snap_date, cash, deployed, equity, realized_pnl, open_positions
```

## 10. Versioning

| Version | Date | What Changed |
|---------|------|-------------|
| v3 | May 17, 2026 | Initial rules. Engine live. SQLite journal schema defined. |
| v5 | May 17, 2026 | Added Learning Log. Weekly review script appends patterns below. |

## 11. Learning Log

Patterns from weekly reviews. Appended automatically by learning/weekly-review.py.

| Week | Closed Trades | Open | Learnings |
|------|--------------|------|-----------|
| 2026-05-17 | No closed trades | 1 open, 1 triggered | ⏳ 1 position aging. No exits hit. Thesis patience intact. |
| 2026-05-17 | 0 missed | 10 checks | ✅ No missed opportunities |

| 2026-05-17 | No closed trades | 1 open, 1 triggered | ⏳ 1 position(s) aging. No exits hit. Thesis patience intact. |
| 2026-05-17 | 0 missed | 10 checks | ✅ No missed opportunities |
| 2026-05-20 | 15 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-20 | 15 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-20 | 15 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-20 | 15 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-20 | 15 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-20 | 15 missed, 3W/0L | Hypothetical +$663 | Review execution threshold |
| 2026-05-20 | 15 missed, 3W/0L | Hypothetical +$596 | Review execution threshold |
| 2026-05-20 | 15 missed, 3W/0L | Hypothetical +$722 | Review execution threshold |

| 2026-05-20 | No closed trades | 9 open, 21 triggered | ⚠️ 15 signal(s) triggered but not executed — check delivery pipeline.; ⏳ 9 position(s) aging. No exits hit. Thesis patience intact. |
| 2026-05-20 | 15 missed, 10W/3L | Hypothetical +$7,052 | Review execution threshold |
| 2026-05-20 | 15 missed, 8W/3L | Hypothetical +$6,546 | Review execution threshold |

| 2026-05-24 | 16 closed, 38% win rate | 12 open, 289 triggered | ⚠️ 243 signal(s) triggered but not executed — check delivery pipeline.; ⚠️ Low win rate — review signal thresholds. May need tighter confluence requirements. |
| 2026-05-24 | 248 missed, 0W/5L | Hypothetical -$955 | Filter working correctly |

| 2026-05-31 | 10 closed, 50% win rate | 9 open, 95 triggered | ⚠️ 30 signal(s) triggered but not executed — check delivery pipeline. |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 30 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 6 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 6 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |
| 2026-05-31 | 4 missed, 0W/0L | Hypothetical +$0 | Filter working correctly |

| 2026-06-01 | 6 closed, 17% win rate | 7 open, 19 triggered | ⚠️ Low win rate — review signal thresholds. May need tighter confluence requirements. |

| 2026-06-07 | 4 closed, 0% win rate | 8 open, 724 triggered | ⚠️ 718 signal(s) triggered but not executed — check delivery pipeline.; ⚠️ Low win rate — review signal thresholds. May need tighter confluence requirements. |
| 2026-06-07 | 0 missed | 0 checks | ✅ No missed opportunities |

| 2026-06-14 | 7 closed, 0% win rate | 8 open, 2245 triggered | ⚠️ 2238 signal(s) triggered but not executed — check delivery pipeline.; ⚠️ Low win rate — review signal thresholds. May need tighter confluence requirements. |
| 2026-06-14 | 0 missed | 0 checks | ✅ No missed opportunities |

| 2026-06-21 | No closed trades | 8 open, 1680 triggered | ⚠️ 1680 signal(s) triggered but not executed — check delivery pipeline.; ⏳ 8 position(s) aging. No exits hit. Thesis patience intact. |
| 2026-06-21 | 0 missed | 0 checks | ✅ No missed opportunities |
