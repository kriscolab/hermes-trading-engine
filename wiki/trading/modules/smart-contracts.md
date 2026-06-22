# DeFi — Smart Contracts: TVL, Protocol Risk, Oracle Risk

Module: smart-contracts
Signal Stack Position: DeFi Layer (supplementary to on-chain)
Data Source: DeFiLlama API (free, no key), Dune Analytics (free dashboards)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (DeFiLlama)

## Why This Matters

On-chain data (Layer 5) tells you about BTC and ETH flows. Smart contract data tells you about the DeFi ecosystem where those assets go. TVL (Total Value Locked) is the DeFi equivalent of AUM — it shows where capital is flowing within crypto. Protocol risk assessment tells you which DeFi platforms are safe to interact with vs which are ticking time bombs.

This layer is supplementary — it's not a primary signal for any thesis, but it provides context for crypto thesis entries and identifies systemic risks:
- Rising TVL across major protocols = ecosystem health, confidence
- Oracle manipulation events = systemic risk
- Protocol exploit history = which platforms to avoid

## Data Sources

### DeFiLlama (Primary — Free, No Key)
- Endpoint: `https://api.llama.fi/`
- Rate limit: Generous. No API key needed.
- Key endpoints:
  - `/protocols` — list all tracked protocols with TVL, chain, category
  - `/protocol/{slug}` — detailed TVL history for a protocol
  - `/charts` — aggregate DeFi TVL across all chains
  - `/chains` — TVL by blockchain
  - `/tvl/{slug}` — TVL over time

### Dune Analytics (Supplementary — Free)
- Pre-built dashboards for DeFi metrics
- Key dashboards: "DeFi TVL Trends", "Protocol Revenue", "Hacks & Exploits"
- No API key needed for public dashboards

### REKT Database (Exploit History — Free)
- URL: `https://rekt.news/leaderboard/`
- Tracks all major DeFi hacks with amounts lost
- Key metric: protocol "Rekt score" — total lost to exploits

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| Total DeFi TVL | Aggregate capital locked in DeFi protocols. Growing = ecosystem expanding. | Bullish for ETH and DeFi tokens |
| TVL by Chain | Which blockchains are gaining/losing market share. ETH dominance in DeFi >50% = ETH value accrual. | Chain rotation signals |
| Protocol TVL Change (7d) | Weekly capital flows into/out of specific protocols. Spikes = yield chasing. Drops = fear or better yields elsewhere. | Risk rotation signals |
| TVL / Market Cap Ratio | DeFi TVL relative to total crypto market cap. Rising = more capital actively deployed. | >30% = fully deployed. <15% = capital on sidelines. |
| Protocol Category Mix | Lending vs DEX vs Yield vs Liquid Staking. Shift toward lending = risk-on. Shift toward stablecoins = risk-off. | Category rotation = sentiment proxy |
| Exploit History | Total $ lost to hacks. Spikes in exploit activity = reduce DeFi exposure. | Risk indicator |
| Oracle Dependency | Protocols relying on single oracle = vulnerable. Multi-oracle = safer. | Protocol risk assessment |

## Protocol Risk Assessment

### Risk Factors (score 0-5 each, lower = riskier)

| Factor | Weight | How to Check |
|--------|--------|-------------|
| TVL | 25% | DeFiLlama: >$1B = 5, >$100M = 3, <$10M = 1 |
| Age | 15% | Launch date: >2 years = 5, >6 months = 3, <3 months = 1 |
| Audits | 20% | Number of reputable audits: 3+ = 5, 1-2 = 3, 0 = 1 |
| Exploit History | 20% | REKT: clean = 5, minor = 3, major = 1 |
| Oracle Model | 10% | Multi-oracle + TWAP = 5, single oracle = 2, no oracle = 0 |
| Admin Keys | 10% | Timelock + multisig = 5, multisig only = 3, single key = 0 |

### Risk Score Interpretation

```
SCORE   RISK LEVEL    ACTION
─────────────────────────────────────────
4.0-5.0 LOW           Safe for DeFi exposure
3.0-3.9 MEDIUM        Acceptable with reduced size
2.0-2.9 HIGH          Avoid unless deeply researched
0.0-1.9 CRITICAL      Do not interact. Likely to be exploited.
```

## Confluence Rules

### With Layer 5 (On-Chain)
```
IF exchange reserves falling (bullish)
   AND DeFi TVL rising
   → Distinguish: coins leaving exchanges for cold storage vs DeFi.
   → TVL rising + reserves falling = coins moving to DeFi (neutral-to-bullish, yield seeking)
   → TVL flat + reserves falling = true accumulation (bullish)

IF exchange reserves falling
   AND DeFi TVL also falling
   → Coins leaving both exchanges AND DeFi. True accumulation.
   → Most bullish on-chain signal. Smart money taking custody.
```

### With Layer 2 (Derivatives)
```
IF funding rate positive (crowded long)
   AND DeFi lending TVL surging
   → Leverage building across both centralized AND decentralized venues.
   → Systemic risk elevated. Reduce crypto exposure.

IF funding rate negative (crowded short)
   AND DeFi lending rates spiking
   → Shorts paying high borrow rates. Unsustainable.
   → Short squeeze likely. Fade the shorts.
```

### With Crypto Thesis
```
IF CRYPTO_E1-E4 signals firing (accumulation confirmed)
   AND DeFi TVL trending up across top 10 protocols
   → Ecosystem health confirms thesis. +1 confluence.
  
IF CRYPTO signals firing
   BUT DeFi exploits surging (hacks >$100M in past 30 days)
   → Systemic risk. Reduce crypto allocation by 25%.
   → Even if BTC is fine, DeFi contagion can spread.
```

### With Macro
```
IF macro regime = RISK-OFF (DXY↑, VIX>25)
   AND DeFi TVL dropping sharply (>20% in 30 days)
   → Risk-off confirmed by DeFi capital flight.
   → Aggressive position reduction. Crypto winter signal.
```

## Divergence Signals (Higher Priority)

```
🔴 BTC ↑ BUT DEFI TVL ↓
   → BTC rallying without DeFi participation. Institutional-only move.
   → Altcoins may not follow. BTC dominance likely to continue rising.
   → Focus on BTC, avoid alt/DeFi positions.

🔴 DEFI TVL ↑ BUT PROTOCOL EXPLOITS ↑
   → More capital entering a more dangerous environment.
   → Risk/reward deteriorating. Reduce DeFi-specific exposure.
   → BTC unaffected. Continue BTC positions.

🔴 SINGLE PROTOCOL TVL SURGING >100% IN 7 DAYS
   → Yield farming frenzy or ponzi dynamics.
   → Unsustainable. Will revert. Do not chase.
   → Signal to rotate OUT of that protocol, not in.

🔴 DEFI LENDING RATES SPIKING (USDC >20% APY)
   → Extreme leverage demand. Market is overheating.
   → Contrarian signal. Reduce long exposure.
   → These rates are never sustainable >2 weeks.
```

## How to Query (Python)

```python
import requests

# DeFiLlama — aggregate TVL
tvl = requests.get("https://api.llama.fi/charts").json()
current_tvl = tvl[-1]["totalLiquidityUSD"]
print(f"Total DeFi TVL: ${current_tvl:,.0f}")

# TVL by chain
chains = requests.get("https://api.llama.fi/chains").json()
for c in sorted(chains, key=lambda x: x.get("tvl", 0), reverse=True)[:5]:
    print(f"  {c['name']}: ${c['tvl']:,.0f}")

# Top protocols by TVL
protocols = requests.get("https://api.llama.fi/protocols").json()
for p in sorted(protocols, key=lambda x: x.get("tvl", 0), reverse=True)[:10]:
    tvl_7d_change = p.get("change_7d", 0)
    arrow = "↑" if tvl_7d_change > 0 else "↓"
    print(f"  {p['name']:20s} ${p['tvl']:>12,.0f} ({arrow}{tvl_7d_change:+.1f}%) "
          f"[{p['category']}]")

# Protocol detail (e.g., Aave)
aave = requests.get("https://api.llama.fi/protocol/aave").json()
print(f"\nAave TVL: ${aave['tvl'][-1]['totalLiquidityUSD']:,.0f}")
print(f"Category: {aave['category']}")
print(f"Chains: {', '.join(aave.get('chains', []))}")

# Protocol risk quick check
def assess_risk(protocol):
    score = 0
    tvl = protocol.get("tvl", 0) or 0
    
    # TVL score (0-25)
    if tvl > 1_000_000_000: score += 25
    elif tvl > 100_000_000: score += 15
    elif tvl > 10_000_000: score += 8
    else: score += 3
    
    # Category risk
    category = protocol.get("category", "").lower()
    if "liquid staking" in category: score += 15
    elif "lending" in category: score += 12
    elif "dex" in category: score += 10
    elif "yield" in category: score += 5
    else: score += 5
    
    return min(score, 40)  # out of 40 for these two dimensions
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via DeFiLlama dashboard |
| v1 | Python script fetches daily TVL + top protocol changes → vault |
| v2 | Protocol risk scorer integrated — flags high-risk protocols |
| v3 | DeFi exploit monitor — alerts on hacks >$50M |
| v4 | TVL/price divergence detection — early warning for DeFi winter |

## Integration with Thesis Checklist

- [ ] Add DeFi TVL trend to crypto signal check (weekly)
- [ ] Add protocol exploit monitor to risk management section
- [ ] Add TVL/price divergence check to confluence scoring:
  - +1 if TVL is rising with price (healthy)
  - -1 if TVL is falling while price rises (narrow rally)
- [ ] Integrate protocol risk scores into DeFi exposure decisions

## Notes

- DeFiLlama API is the gold standard for TVL data. Free, fast, comprehensive.
- TVL is denominated in USD but driven by token prices. Rising TVL can be price appreciation, not new deposits. Check both.
- TVL in native token terms (ETH locked, not USD) is a cleaner signal. DeFiLlama provides this.
- Protocol exploits are DeFi's systemic risk. 2022 had $3.8B in hacks. 2023 had $1.8B. Trend is down but risk remains.
- Oracle manipulation caused 60%+ of DeFi hacks. Check oracle model before using any protocol.
- Liquid staking (Lido, Rocket Pool) now dominates DeFi TVL. This is structural, not speculative.
- DeFi is Ethereum-centric. 55%+ of DeFi TVL is on Ethereum mainnet or L2s.
