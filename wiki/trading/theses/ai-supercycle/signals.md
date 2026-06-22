# Signals — AI Supercycle Thesis

Version: v0
Status: DEFINED — NOT YET LIVE
Last updated: May 17, 2026

## Thesis Claims (from thesis.md)

For each claim, a falsifiable trigger. Signals checked weekly (future cron TBD).

---

## Entry Signals

### E1 — AI Capex Acceleration
**Claim:** Compute demand grows exponentially.
**Trigger:** Any Mag7 company announces >20% increase in AI capex guidance quarter-over-quarter.
**Action:** Enter 25% of thesis allocation into AI-BASKET (5 ETF equal-weight).
**Rationale:** Capex acceleration = thesis validation. Physical infrastructure build-out is the bet.

### E2 — Power Deal Announcement
**Claim:** Power is the binding constraint.
**Trigger:** Major data center power deal announced (>1 GW, new natural gas/solar/nuclear dedicated to AI compute).
**Action:** Enter 25% into DTCR + TAN (electrons layer overweight).
**Rationale:** Power deals unlock GPU deployment that's currently queued. Leading indicator for compute layer.

### E3 — Intel Turnaround Signal
**Claim:** Intel is undervalued.
**Trigger:** Intel 18A process node confirmed customer win OR Intel market cap crosses $200B (from ~$150B).
**Action:** Enter 10% into INTC directly.
**Rationale:** Aschenbrenner's most patient position. If thesis plays out, INTC is the highest-upside single name.

### E4 — GPU Capacity Milestone
**Claim:** GPU cloud operators outperform GPU suppliers.
**Trigger:** CoreWeave/CRWV publicly announces 100K+ GPU cluster deployed OR Core Scientific/CORZ AI revenue exceeds crypto mining revenue for 2 consecutive quarters.
**Action:** Enter remaining 25% into AI-BASKET if not yet fully allocated.
**Rationale:** The rotation from GPU suppliers (NVDA) to GPU operators (CRWV, CORZ) is a core thesis claim.

### E5 — AI Revenue Breakout
**Claim:** Markets mispricing AI exponential.
**Trigger:** Combined AI revenue from MSFT Azure AI + GOOGL Cloud AI + AMZN AWS AI exceeds $50B annual run rate.
**Action:** If not yet fully allocated, enter 25% on this signal.
**Rationale:** Revenue validates the capex. When AI services generate real money, the infrastructure thesis is proven.

---

## Exit Signals (Thesis Invalidation)

### X1 — Jevons Paradox (Efficiency Breakthrough)
**Trigger:** Open-source model achieves frontier performance at <10% of expected compute cost (DeepSeek-style efficiency breakthrough that reduces, not increases, total compute demand).
**Action:** Exit 50% of AI-BASKET immediately.
**Rationale:** If efficiency gains outpace demand growth, the "exponential compute demand" thesis breaks. This is the single most important risk.

### X2 — AI Revenue Deceleration
**Trigger:** Combined AI revenue growth rate drops below 30% year-over-year for 2 consecutive quarters.
**Action:** Exit 50% immediately, remaining 50% over 4 weeks.
**Rationale:** Markets will reprice AI infrastructure if end-user demand doesn't materialize.

### X3 — Power Grid Expansion Accelerates
**Trigger:** US data center interconnection queue drops >30% year-over-year (grid capacity catching up).
**Action:** Scale out of DTCR + TAN — 25% per quarter.
**Rationale:** The power bottleneck thesis weakens if grid capacity expands faster than expected.

### X4 — Aschenbrenner Exits Conviction Stocks
**Trigger:** CoreWeave (CRWV) OR Bloom Energy (BE) fully exited from 13F filing.
**Action:** Exit AI-BASKET 50%. Exit that specific stock 100%.
**Rationale:** If the thesis author exits his largest positions, the thesis has changed.

### X5 — GPU Export Controls Tighten
**Trigger:** US government restricts GPU exports to key markets (Saudi, UAE, India) OR imposes >30% tariff on GPU imports/exports.
**Action:** Exit 50% of AI-BASKET.
**Rationale:** GPU supply chain disruption breaks the compute scaling thesis.

---

## Position Sizing

| Phase | Allocation (% of thesis paper capital) | Condition |
|-------|----------------------------------------|-----------|
| Initial | 25% | E1 triggered (capex acceleration) |
| Add (power) | 25% | E2 triggered (power deal) |
| Add (Intel) | 10% | E3 triggered (Intel turnaround) |
| Full | 25% | E4 triggered (GPU milestone) |
| Late entry | 25% | E5 triggered (revenue breakout) |
| Max | 110% | All five entry signals fired (allows slight overweight on Intel) |

**Note:** This thesis is allocated 50% of total paper portfolio ($50K of $100K) when live alongside the commodity thesis. Currently NOT LIVE — commodity thesis running solo at 100%.

---

## What to Monitor (future Weekly Cron)

| Check | Data Source | Action if Triggered |
|-------|------------|---------------------|
| Mag7 AI capex guidance | Earnings calls / web_search | Flag E1 |
| Data center power deals | web_search "data center power deal gigawatt" | Flag E2 |
| Intel 18A progress | web_search "Intel 18A customer" | Flag E3 |
| CoreWeave GPU cluster size | web_search "CoreWeave GPU cluster" | Flag E4 |
| Core Scientific AI vs mining revenue | Core Scientific quarterly report | Flag E4 |
| AI revenue run rate (MSFT+GOOGL+AMZN) | Earnings calls | Flag E5 |
| Open-source efficiency breakthrough | web_search "open source model efficiency breakthrough" | Flag X1 |
| 13F filing (quarterly) | SEC EDGAR / web_search "Situational Awareness 13F" | Flag X4 |
| GPU export controls | web_search "GPU export restriction" | Flag X5 |

---

## Logging

| Date | Signal | Status | Notes |
|------|--------|--------|-------|
| May 17, 2026 | — | v0 defined | Thesis codified. Signals defined. Not yet live. No tracker cron. |

---

## Notes

- This thesis is NOT yet integrated with the paper-trader engine. Engine currently serves commodity thesis only.
- At v6 of the trading module: add thesis_id to journal.db, wire this thesis into engine.py.
- Weekly tracker cron will be created when thesis goes live (v6 or earlier if user accelerates).
- Aschenbrenner's 13F changes quarterly. Re-evaluate signals after each filing.
