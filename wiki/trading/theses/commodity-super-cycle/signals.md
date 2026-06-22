# Signals — Commodity Super Cycle Thesis

Version: v1
Status: ACTIVE
Last updated: May 16, 2026

## Thesis Claims (from thesis.md)

For each claim, a falsifiable trigger. All triggers are checked weekly by cron `35f039b1f202`.

---

## Entry Signals

### E1 — Brent Pullback to Value Zone
**Claim:** Oil will break past $105.
**Trigger:** Brent closes below its 50-day SMA on any weekly close, AND the weekly tracker confirms Mun7 FCF yield > 12%.
**Action:** Enter 25% of allocated paper capital into Mun7 equal-weight basket (or XLE if individual stock tracking is unavailable).
**Rationale:** Thesis is long-term structural. Dips are entries, not exits.

### E2 — Brent Breakout Confirmation
**Claim:** Oil breakout pending from $105 level.
**Trigger:** Brent weekly close > $110.
**Action:** Enter remaining 50% of allocated paper capital.
**Rationale:** Breakout confirms thesis. Don't chase intra-week — wait for weekly close.

### E3 — Rotation Signal (XLE/XLK Ratio)
**Claim:** Capital rotates from Tech (43%) toward Energy (6%).
**Trigger:** XLE/XLK ratio makes a higher low on the weekly chart OR Energy sector weight crosses above 4.5% of S&P 500.
**Action:** If not yet fully allocated, enter 25% on this signal.
**Rationale:** This is the thesis playing out in real time. Late entry but high conviction.

### E4 — Gold Tactical Short (Counter-Trade)
**Claim:** Gold short-term bearish (central banks forced-selling for energy), structural long 4000→10000.
**Trigger (short):** Gold > $3,800 AND DXY rising on weekly timeframe.
**Action:** Paper-short GLD or /GC with 5% of total paper portfolio. Cover if gold drops 10% OR DXY reverses.
**Trigger (long):** Gold drops below $3,000 OR central bank dovish pivot confirmed.
**Action:** Paper-long GLD or /GC with 10% of paper portfolio. No stop — structural position.

---

## Exit Signals (Thesis Invalidation)

### X1 — Hormuz Reopens
**Trigger:** Credible news of Strait of Hormuz reopening (diplomatic agreement, military de-escalation).
**Action:** Exit 100% of Mun7 positions within 2 weeks. The security premium evaporates.
**Note:** This is the single most important trigger. Monitor weekly.

### X2 — Mag7 Capex Collapse
**Trigger:** Combined Mag7 + Oracle quarterly capex drops >30% from $820B annual run-rate.
**Action:** Exit 50% immediately, remaining 50% over 4 weeks.
**Rationale:** The demand thesis breaks if hyperscalers stop building.

### X3 — Energy Weight Converges
**Trigger:** S&P 500 Energy sector weight crosses above 10% (from current ~4%).
**Action:** Begin scaling out — 25% per percentage point above 10%.
**Rationale:** At 10%+, the rotation is priced in. Thesis is fully valued.

### X4 — Brent Contango
**Trigger:** Brent futures curve flips from backwardation to contango (front month < 12-month) for 4 consecutive weeks.
**Action:** Exit 50%.
**Rationale:** Backwardation = physical scarcity. Contango = oversupply. Thesis breaks.

### X5 — Mun7 FCF Yield Collapse
**Trigger:** Mun7 aggregate FCF yield drops below 8% (from current ~15.5%).
**Action:** Exit 50%.
**Rationale:** Either oil prices collapsed or costs spiked. Either way, the value case is gone.

---

## Position Sizing

| Phase | Allocation (% of paper portfolio) | Condition |
|-------|-----------------------------------|-----------|
| Initial | 25% | E1 triggered (pullback entry) |
| Add | 25% | E3 triggered (rotation signal) |
| Full | 50% | E2 triggered (breakout confirmation) |
| Max | 100% | All three entry signals fired |

**Note:** Only one "initial" and one "full" allocation. The "add" is a middle phase. Total paper portfolio dedicated to this thesis: 100% at max (since it's our only active thesis). When thesis #2 launches, total across theses capped at 100%.

---

## Paper Portfolio Structure

```
paper-portfolio.md tracks:
├── cash: $100,000 (starting)
├── positions:
│   ├── MUN7-BASKET (XLE proxy): 0 shares
│   └── GOLD-SHORT (GLD put or /GC short): 0 contracts
├── trades: (date, signal, action, size, price, rationale)
└── P&L: (realized, unrealized, total)
```

---

## What to Monitor (Weekly Cron)

The existing cron `35f039b1f202` already fetches prices. Add these checks:

| Check | Data Source | Action if Triggered |
|-------|------------|---------------------|
| Brent vs 50-day SMA | yfinance / web | Flag E1 in Telegram summary |
| Brent weekly close > $110 | web | Flag E2 |
| XLE/XLK ratio | yfinance | Flag E3 |
| Gold > $3,800 + DXY | web | Flag E4 short |
| Hormuz news | web_search "Strait of Hormuz" | Flag X1 immediately |
| Mag7 capex (quarterly) | earnings calls | Flag X2 |
| Energy sector weight | web | Flag X3 |
| Brent futures curve | web | Flag X4 |

---

## Logging

Every signal trigger, even if not acted on (e.g., paper portfolio not yet live in v0), gets logged here with date, signal ID, and status:

| Date | Signal | Status | Notes |
|------|--------|--------|-------|
| May 16, 2026 | — | v1 defined | No triggers yet. First weekly check May 17. |
| May 17, 2026 | E4 | FIRED | Gold $4,540 + DXY 99.27 rising. Both short-entry conditions met. Paper-short 5% portfolio. |
| May 17, 2026 | E2 | WATCH | Brent $105.72, $4.28 from $110 breakout trigger. |
| May 17, 2026 | E3 | WATCH | XLE/XLK 0.337, Energy +2.32% vs XLK -1.81%. Rotation building. |
