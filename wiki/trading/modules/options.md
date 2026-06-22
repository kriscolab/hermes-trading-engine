# Layer 3 — Options: IV Skew + Term Structure

Module: options
Signal Stack Position: Layer 3 (Options Market)
Data Source: Deribit API (public, no key needed)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (Deribit)

## Why This Matters

Options are the "smart money" layer. While spot traders react to price, options traders position ahead of it. IV skew reveals tail-risk pricing. Term structure shows whether fear is near-dated or far-dated. Max pain acts as a magnetic strike. This layer answers "what is the market pricing in, not just reacting to?"

Crypto options have one structural advantage over equity options: they trade 24/7, no expiration Fridays, no pin risk from monthly OPEX. The data is cleaner.

## Data Sources

### Deribit API (Free, Public)
- Endpoint: `https://www.deribit.com/api/v2/public/`
- No API key needed for public endpoints
- Coverage: BTC, ETH (90%+ of crypto options OI)
- Rate limit: 20 req/sec (public), generous for analysis
- Key endpoints:
  - `get_instruments` — list all options (strikes, expiries)
  - `get_book_summary_by_currency` — IV, greeks, OI per instrument
  - `get_index` — underlying spot index price
  - `get_historical_volatility` — realized vol for comparison

### Alternative / Complementary
- **Amberdata** (free tier): Aggregated options data across Deribit, OKX, Binance. Broader but rate-limited.
- **Laevitas** (free tier): Pre-computed skew, term structure charts. No API — manual check.

### Data Format (Deribit get_book_summary_by_currency)

```json
{
  "result": [{
    "instrument_name": "BTC-28JUN26-100000-C",
    "option_type": "call",
    "strike": 100000,
    "expiration_timestamp": 1779000000000,
    "mark_iv": 62.5,
    "open_interest": 123.4,
    "volume": 45.6,
    "greeks": {"delta": 0.55, "gamma": 0.0001, "vega": 120.5, "theta": -35.2}
  }]
}
```

## Key Metrics

| Metric | What It Tells You | How to Read |
|--------|------------------|-------------|
| 25-Delta IV Skew | Call IV - Put IV (at 25-delta). Positive = calls bid, bullish. Negative = puts bid, bearish. | >5% = euphoric; <-5% = fearful |
| Term Structure (Contango/Backwardation) | Near-dated IV vs far-dated IV. Contango = normal. Backwardation = event fear. | Curve shape matters more than level |
| Put/Call Ratio (OI) | Total put OI / call OI. >0.7 = bearish positioning. <0.4 = bullish. | Open interest, not volume |
| Max Pain | Strike where most option value expires worthless. Price gravitates here. | Check Friday 8 AM UTC (BTC expiry) |
| Gamma Exposure (GEX) | Net dealer gamma. Positive = stabilizing. Negative = amplifying moves. | Flip to negative = volatility incoming |
| IV vs RV (Vol Premium) | IV minus realized vol. High premium = options expensive. | >20% = sell vol opportunities |
| Volume-Weighted IV | IV of most actively traded strikes. More signal than ATM IV alone. | Where is the actual flow? |
| Large Trades / Block Flows | Single trades >100 BTC notional. Reveals institutional positioning. | Deribit public: `get_last_trades_by_currency` |

## Confluence Rules

### With Layer 1 (Price Action / TPO)
```
IF price at TPO VAH (Value Area High)
   AND IV skew is bearish (puts bid) — put skew >5%
   → Fade the breakout. Smart money buying protection at the highs.
   → NOT breakout — distribution disguised.

IF price at TPO VAL (Value Area Low)
   AND IV skew is bullish (calls bid) — call skew >5%
   → Dip being bought with conviction. Accumulation zone.
   → Long entries validated.
```

### With Layer 2 (Funding Rates + OI)
```
IF funding rate extreme positive (>0.05%)
   AND IV skew also bullish (call skew high)
   → Euphoric leverage + euphoric options. Coincident = dangerous.
   → Contrarian signal. Crowd is all-in one direction.

IF funding rate extreme positive
   BUT IV skew bearish (puts expensive)
   → Perp traders euphoric, options traders hedging.
   → DIVERGENCE. Options traders are smarter. Fade the rally.
```

### With Layer 4 (Liquidations)
```
IF large liquidation cluster below current price
   AND put skew elevated (fear priced in)
   AND term structure backwardated (near-dated vol high)
   → Fear + fuel loaded. Expect sweep of liquidation cluster.
   → After sweep: IV crush (vol drops). Good entry on the reversal.
```

### With Macro Layer (Layer 6)
```
IF macro event (CPI, FOMC) within 7 days
   AND term structure backwardated (near-dated IV spike)
   → Event risk priced. Don't fade the vol — it's justified.
   → Wait for event, then trade the IV crush.
```

## Divergence Signals (Higher Priority)

```
🔴 PRICE ↑ (ATH/near highs) BUT IV SKEW turning bearish
   → Smart money buying crash protection at the top
   → Insurance is cheap for them, expensive signal for us
   → Reduce long exposure within 2 weeks

🔴 PRICE ↓ (crashing) BUT CALL SKEW rising
   → Someone is accumulating upside optionality during panic
   → Could be whales building position via options, not spot
   → Check block trades: if large call buys → reversal signal

🔴 TERM STRUCTURE FLIPS to backwardation (near IV > far IV)
   → Market pricing imminent event risk
   → Not necessarily bearish — but volatility incoming
   → Reduce size, tighten stops, wait

🔴 MAX PAIN far from current price (<48h to expiry)
   → Price will be pulled toward max pain as expiry nears
   → Market makers delta-hedge to push price toward max pain
   → Contra-trend trade toward max pain strike (last 48h only)

🔴 GEX FLIPS NEGATIVE (dealers net short gamma)
   → Dealers amplify moves instead of dampening
   → Explosive price action incoming
   → Don't hold tight stops — they'll get hunted
```

## How to Query (Python)

```python
import requests

DERIBIT = "https://www.deribit.com/api/v2/public"

# Get all BTC options
r = requests.get(f"{DERIBIT}/get_instruments", params={
    "currency": "BTC", "kind": "option", "expired": "false"
})
instruments = r.json()["result"]

# Get IV, greeks, OI for all BTC options
r = requests.get(f"{DERIBIT}/get_book_summary_by_currency", params={
    "currency": "BTC", "kind": "option"
})
summaries = r.json()["result"]

# Compute 25-delta skew
calls_25d = [s for s in summaries if s["option_type"] == "call"
             and s.get("greeks", {}).get("delta", 0) > 0.2
             and s.get("greeks", {}).get("delta", 0) < 0.3]
puts_25d  = [s for s in summaries if s["option_type"] == "put"
             and s.get("greeks", {}).get("delta", 0) > -0.3
             and s.get("greeks", {}).get("delta", 0) < -0.2]

avg_call_iv = sum(c["mark_iv"] for c in calls_25d) / len(calls_25d)
avg_put_iv  = sum(p["mark_iv"] for p in puts_25d) / len(puts_25d)
skew = avg_call_iv - avg_put_iv  # positive = bullish

# Get recent large trades (institutional flow)
r = requests.get(f"{DERIBIT}/get_last_trades_by_currency", params={
    "currency": "BTC", "kind": "option", "count": 100
})
block_trades = [t for t in r.json()["result"]
                if t["amount"] * t["price"] > 100_000]  # >$100K notional
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via Deribit or Laevitas dashboard during signal review |
| v1 | Python script pulls 25-delta skew + term structure → vault tracker |
| v2 | Integrated into daily signal check (adds skew/term structure line) |
| v3 | Auto-flag skew divergence with funding rate and price action |
| v4 | Block trade alerts: >$1M single trade → flagged for review |

## Integration with Thesis Checklist

When a crypto-native thesis uses this layer:
- [ ] Bookmark Deribit public API docs (no key needed)
- [ ] Define asset-specific skew thresholds (BTC vs ETH options behave differently)
- [ ] Add IV skew + term structure columns to thesis tracker
- [ ] Define entry signals: skew divergence with price = contrarian entry
- [ ] Schedule check around monthly expiry (last Friday of month, 8 AM UTC)

## Notes

- Deribit dominates crypto options (90%+ OI). Data is complete, not fragmented.
- BTC and ETH options expire monthly (last Friday). Weekly expiries exist for BTC.
- Skew is most informative at 25-delta. ATM IV can be noisy.
- Options data is cleaner than perp data (no funding rate distortion). Trust it more.
- Block trades: single legs can be hedged. Look for multi-leg structures (spreads, butterflies) — those reveal actual directional bets.
- IV tends to mean-revert faster in crypto than equities (higher vol-of-vol).
- Weekend theta decay still counts. Options lose value over weekends too — don't hold long options through Friday if no weekend catalyst.
