# Airdrop Scanner — Opportunity Scoring & Ranking

Module: airdrop-scanner
Category: DeFi / Yield
Data Source: Airdrop aggregators (DefiLlama, Airdrops.io, web scrape)
Status: v0.1 — DEFINED, scanner script built

## Why This Matters

Airdrops are crypto's unique yield source — free tokens distributed to early users. Some airdrops have been worth $10K+ (Uniswap, Arbitrum, Jito). Others are worth $0 and exist only to farm engagement. The difference between a $10K airdrop and a rug-pull is research.

This module scores and ranks airdrop opportunities across five dimensions so you can prioritize your time and capital. The goal is NOT to farm every airdrop — it's to identify the 2-3 highest-value, lowest-risk opportunities each week.

## Scoring System (0-100)

| Dimension | Weight | What It Measures | Score Range |
|-----------|--------|-----------------|-------------|
| Likelihood | 30% | How likely is the airdrop to happen? Confirmed > Likely > Rumored > Speculative. | 0-30 |
| Est. Value | 25% | Estimated value based on comparable projects, TVL, and funding raised. | 0-25 |
| Time-to-Claim | 15% | How long until the airdrop? <1 month = max score. >6 months = penalty. | 0-15 |
| Team/Backers | 15% | Quality of team, VC backers, and advisors. Known team + tier-1 VCs = max. | 0-15 |
| Rug Risk (inverse) | 15% | Risk of scam/rug. Audited + established = max. Anonymous + no audit = 0. | 0-15 |

## Rating Tiers

```
SCORE   TIER    ACTION
─────────────────────────────────────────
80-100  S       High priority. Actively farm. Allocate time + gas.
60-79   A       Worth farming. Set up wallet, complete tasks.
40-59   B       Monitor. Farm if low time commitment.
20-39   C       Low priority. Farm only if genuinely interested.
0-19    D       Skip. Likely rug or vaporware.
```

## Data Sources

### Primary
- **DefiLlama Airdrops:** Free, tracks protocol airdrop announcements. URL: `https://defillama.com/airdrops`
- **Airdrops.io:** Community-curated list. Free. URL: `https://airdrops.io/`

### Supplementary
- **Twitter/X:** Project announcements, founder tweets
- **Discord:** Community size, activity level
- **Dune Dashboards:** Airdrop eligibility tracking, TVL data
- **GitHub:** Project activity, audit reports

### Scoring Inputs (per opportunity)

| Field | Source | How to Score |
|-------|--------|-------------|
| Status | Project announcement | Confirmed=30, Likely=20, Rumored=10, Speculative=5 |
| TVL / Funding | DefiLlama, Crunchbase | >$500M TVL or >$50M raised = 25 |
| Airdrop Date | Project docs | <1 month = 15, 1-3 months = 10, 3-6 months = 5, >6 months = 2 |
| Team | LinkedIn, Twitter | Public team + tier-1 VCs = 15 |
| Audit | GitHub, CertiK | 3+ audits = 15, 1-2 = 10, none = 0 |
| Community | Discord, Twitter | >100K followers + active Discord = bonus |
| Tokenomics | Whitepaper | Clear allocation % for airdrop = bonus |

## Confluence Rules

### With Smart Contracts Module
```
IF protocol is in top 20 by TVL on DeFiLlama
   AND protocol has 3+ audits
   AND airdrop confirmed
   → HIGH confidence. Rug risk minimal.
```

### With On-Chain Module
```
IF protocol has growing TVL (>10% in 30 days)
   AND exchange outflows for protocol token rising
   → Airdrop likely to have real value. Users are accumulating.
```

### With Sentiment Module
```
IF Fear & Greed < 25 (extreme fear)
   AND airdrop announced during fear
   → Higher likelihood of being undervalued at launch.
   → Farm now, sell later when sentiment improves.
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual scraping of DefiLlama + Airdrops.io |
| v1 | Python script scrapes aggregators, scores, ranks daily |
| v2 | Auto-filter: only A-tier and above → Telegram digest |
| v3 | Historical tracking: which scores correlated with actual value |
| v4 | Integration with wallet: auto-check eligibility for top-ranked airdrops |

## Notes

- Airdrop farming requires time + gas fees. Don't farm D-tier airdrops — the gas alone may exceed the value.
- Airdrops are taxable in most jurisdictions. Track claimed value for tax reporting.
- Never share private keys or seed phrases for airdrop claims. Legitimate airdrops never ask for these.
- The best airdrops are often the ones nobody is talking about yet. Early discovery > popular consensus.
- Airdrop value is inversely correlated with the number of farmers. The more people farming, the smaller your share.
