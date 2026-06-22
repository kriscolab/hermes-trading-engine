# Gap 3 — Sentiment: Fear & Greed + Polymarket

Module: sentiment
Signal Stack Position: Gap 3 (Sentiment / Narrative)
Data Source: Alternative.me API + Polymarket API (both free, no key)
Status: v0.1 — DEFINED, automated via crypto-data-fetch.py (alt.me)

## Why This Matters

Sentiment is the contrarian's edge. When Fear & Greed is extreme (>80 greed or <20 fear), mean reversion is statistically favored. Polymarket shows what people bet on, not what they say — revealed preference beats survey data. This layer answers "is the crowd positioned for what we expect, or is there a contrarian signal?"

For crypto: Fear & Greed extremes map to local tops and bottoms with ~70% reliability over 7-14 day windows.
For equity/commodity: Polymarket event contracts reveal real-time market-implied probabilities for macro events.

## Data Sources

### Fear & Greed Index (Alternative.me)
- Endpoint: `https://api.alternative.me/fng/`
- Rate limit: 60 req/min (generous free tier)
- No API key needed
- Returns: current value (0-100), classification (Extreme Fear/Fear/Neutral/Greed/Extreme Greed), timestamp
- Historical: `?limit=30` for 30 days of data
- Classification thresholds:
  - 0-24: Extreme Fear
  - 25-49: Fear
  - 50-74: Greed
  - 75-100: Extreme Greed

### Polymarket (Event-Driven Sentiment)
- Endpoint: `https://gamma-api.polymarket.com/events`
- No API key needed for public data
- Returns: event markets with probabilities derived from order book
- Filter by: volume, liquidity, closing date
- Key events to track:
  - Macro: FOMC rate decisions, recession probability, inflation targets
  - Crypto: ETF flows, regulatory actions, BTC price targets
  - AI: AGI timeline bets, AI regulation probability

### Alternative Sources
- **Crypto Fear & Greed (crypto-specific):** Also from alternative.me — same API, covers BTC only
- **AAII Sentiment Survey:** Equity investor sentiment (free, weekly). `https://www.aaii.com/sentimentsurvey`
- **Twitter/X sentiment:** Requires API key (paid). Not used. Free alternative: LunarCrush free tier.

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| Fear & Greed Value | Crowd emotion 0-100. <25 = capitulation. >75 = euphoria. | Contrarian: buy fear, sell greed |
| F&G 7-day Change | Trend in sentiment. Rising from fear = recovery. Falling from greed = distribution. | Direction of change matters more than level |
| Polymarket Probability | Market-implied odds of events. "Wisdom of the crowd" with skin in the game. | >70% = strongly priced in. <30% = surprise potential |
| Polymarket Volume | How much money is on a prediction. High volume = high conviction. | Low volume predictions are noisy |
| Sentiment-Price Divergence | Price rising but sentiment falling = smart money exiting | Bearish divergence |
| Multiple Timeframe Sentiment | Daily vs Weekly F&G. Daily extreme + weekly neutral = short-term panic | Fade the daily extreme |

## Confluence Rules

### With Layer 1 (Price Action)
```
IF Fear & Greed < 20 (Extreme Fear)
   AND price at structural support (200-day MA, VAL)
   → HIGH CONVICTION long entry
   → The crowd is panicking at a level that historically holds.

IF Fear & Greed > 80 (Extreme Greed)
   AND price at resistance (ATH, VAH)
   → HIGH CONVICTION exit / fade
   → Euphoria at resistance = distribution.
```

### With Layer 2 (Derivatives)
```
IF Fear & Greed extreme (<20 or >80)
   AND funding rate neutral (not confirming the extreme)
   → Sentiment is emotional, not leveraged. Reversal is violent.
   → Derivatives traders are NOT participating in the extreme = smart money staying out.

IF Fear & Greed neutral (40-60)
   AND funding rate extreme (>0.05% or <-0.03%)
   → Derivatives positioning contradicts sentiment.
   → Trust derivatives over sentiment. Positioning > emotion.
```

### With Layer 5 (On-Chain)
```
IF Fear & Greed < 25 (fear)
   AND exchange outflows surging
   → Fear is retail-only. Whales accumulating.
   → Highest conviction crypto entry signal.
```

### With Commodity Thesis
```
IF Polymarket "Recession 2026" probability > 60%
   AND Fear & Greed < 30
   → Risk-off macro regime. Reduce commodity long exposure.
   → Gold short signal (E4S) gets stronger.

IF Polymarket "Fed Rate Cut by July" > 70%
   AND DXY falling
   → Dovish regime. Commodities benefit. Gold short weakens.
```

## Divergence Signals (Higher Priority)

```
🔴 PRICE ↑ (ATH) BUT FEAR & GREED falling
   → Smart money selling into euphoria
   → Distribution. Fade the breakout within 2 weeks.

🔴 PRICE ↓ (crashing) BUT FEAR & GREED not in Extreme Fear
   → Real capitulation hasn't happened yet. More downside.
   → Don't buy the dip until F&G < 25.

🔴 POLYMARKET PROBABILITY > 80% ON EVENT
   → Event is fully priced in. "Buy the rumor, sell the fact."
   → If event happens = nothing. If event doesn't = violent reversal.

🔴 POLYMARKET VOLUME SPIKE ON LOW-PROBABILITY EVENT
   → Someone knows something. Check for insider information.
   → Follow the volume, not the probability.
```

## How to Query (Python)

```python
import requests

# Fear & Greed Index
fng = requests.get("https://api.alternative.me/fng/?limit=30").json()
current = fng["data"][0]
print(f"F&G: {current['value']} — {current['value_classification']}")

# 7-day trend
week_ago = fng["data"][6]
trend = int(current["value"]) - int(week_ago["value"])
print(f"7d change: {trend:+d}")

# Polymarket — macro events
pm = requests.get("https://gamma-api.polymarket.com/events",
                   params={"tag": "macro", "limit": 10, "active": "true"})
for event in pm.json():
    markets = event.get("markets", [])
    for m in markets:
        if m.get("outcomePrices"):
            prob = float(m["outcomePrices"][0]) * 100
            print(f"  {event['title'][:60]}: {prob:.0f}%")
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual check via alternative.me + Polymarket dashboards |
| v1 | Python script fetches daily F&G + top Polymarket events → vault tracker |
| v2 | Integrated into daily signal check (adds sentiment line to confluence) |
| v3 | Auto-flag when F&G extreme aligns with other layer signals |
| v4 | Polymarket macro event monitor — alerts when probability crosses 70% |

## Integration with Thesis Checklist

When a thesis uses this layer:
- [ ] Add Fear & Greed column to daily signal check
- [ ] Define thesis-specific F&G thresholds (crypto: <25 buy, >75 sell. Equity: <30 buy, >80 sell.)
- [ ] Bookmark 5-10 Polymarket events relevant to the thesis
- [ ] Add "sentiment regime" to confluence scoring (1 point if F&G supports thesis direction)

## Notes

- Fear & Greed is a CONTRARIAN indicator. Use it to fade extremes, not confirm trends.
- F&G works better in crypto than equities (crypto is more sentiment-driven).
- Polymarket probabilities are NOT predictions — they're market-implied odds. Treat like options IV.
- Weekend F&G readings can be noisy (lower volume). Trust weekday readings more.
- F&G values between 40-60 convey no signal. Don't force an interpretation.
- The best crypto entries historically: F&G 10-25 + on-chain outflows + funding neutral.
