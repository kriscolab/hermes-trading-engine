# Gap 2 — Session Clock: Asia / London / New York Windows

Module: session-clock
Signal Stack Position: Gap 2 (Session Context)
Data Source: Static timezone mapping (no API needed)
Status: v0.1 — DEFINED, static data (no API needed)

## Why This Matters

Crypto trades 24/7, but liquidity and volatility are NOT evenly distributed. Each session has a personality:
- **Asia** (Tokyo/Shanghai): Retail-driven, trend-confirming. If a move starts in NY and holds through Asia, it's real.
- **London**: Institutional flow. Largest FX and crypto OTC desks. Reversals often start here.
- **New York**: Highest volume. US macro data hits here. Trend acceleration or sharp reversals on news.

Session overlaps are where the most liquid, most violent moves happen. Knowing which session you're trading in prevents you from mistaking Asia chop for NY conviction.

For crypto theses: session context determines whether a breakout is institutional (London/NY) or retail (Asia). Institutional moves persist. Retail moves fade.

## Session Map (All Times UTC — Convert to Local)

```
SESSION      UTC HOURS    IST HOURS      PERSONALITY
─────────────────────────────────────────────────────
Asia         00:00-09:00  05:30-14:30    Retail flow. Range-bound.
                                         Breakouts here are suspicious
                                         unless they hold through London.

London       08:00-17:00  13:30-22:30    Institutional flow. Trend setting.
                                         Reversals here are high conviction.
                                         Largest crypto OTC desks active.

New York     13:00-22:00  18:30-03:30    Highest volume. News-driven.
                                         US macro releases at 8:30 AM ET
                                         (13:30 UTC / 19:00 IST).

OVERLAPS (highest volume, highest volatility):
  Asia/London    08:00-09:00 UTC  13:30-14:30 IST   Liquidity bridge
  London/NY      13:00-17:00 UTC  18:30-22:30 IST   MAX VOLUME WINDOW
```

## Session Characteristics

### Asia Session (00:00-09:00 UTC)
- **Volume:** Lowest of three sessions. Thin books.
- **Volatility:** Moderate. Gap fills from weekend. BTC often ranges.
- **Key markets:** Japan (Tokyo), Korea (Upbit premium), China/HK sentiment.
- **Indicators to watch:** Kimchi premium (Korea), CNY/USD, Nikkei futures.
- **Trading rule:** Don't chase Asia breakouts unless they survive into London overlap.
- **Best for:** Accumulating positions slowly. Not for entries on breakouts.
- **Worst for:** Breakout entries. Thin liquidity = fakeouts common.

### London Session (08:00-17:00 UTC)
- **Volume:** Medium-high. Largest crypto OTC desks.
- **Volatility:** High during NY overlap. Moderate otherwise.
- **Key markets:** UK/European institutional flow. LMAX, Eurex.
- **Indicators to watch:** EUR/USD, FTSE, DAX, Bund yields.
- **Trading rule:** London reversal after Asia trend = fade the Asia move. London continuation of Asia = trend is real.
- **Best for:** Trend confirmation. If NY trend holds through Asia and London continues it → strong trend.
- **Worst for:** Counter-trend trades. London institutional flow respects trends.

### New York Session (13:00-22:00 UTC)
- **Volume:** Highest. US spot ETFs, CME futures, options expiry.
- **Volatility:** Highest. Especially 8:30-10:30 AM ET on macro data days.
- **Key markets:** US equities (SPY, QQQ), bonds, DXY, VIX.
- **Indicators to watch:** SPY, QQQ, DXY, VIX, US 10Y yield.
- **Trading rule:** NY open direction is the day's direction 65% of the time. Fade at your peril.
- **Best for:** Breakout entries. Highest volume validates breakouts.
- **Worst for:** Weekend. Saturday/Sunday = no NY session. Low conviction moves.

### Weekend (Friday 22:00 UTC — Sunday 22:00 UTC)
- **Volume:** Thinnest. Retail-only. No institutional flow.
- **Volatility:** Unpredictable. Can be dead or explosive on news.
- **Trading rule:** No entries on weekends. Wait for Monday Asia/London.
- **Exception:** CME gap fills on Sunday evening (NY open). BTC futures gap almost always fills within 24h.

## Key Time Windows for Crypto Events

| Event | UTC | IST | Impact |
|-------|-----|-----|--------|
| CME BTC Futures Close | Fri 21:00 | Sat 02:30 | Weekly close. CME gap opens. |
| CME BTC Futures Open | Sun 23:00 | Mon 04:30 | Gap fill watch. 90% fill rate within 24h. |
| Deribit Options Expiry | Fri 08:00 | Fri 13:30 | Monthly: last Friday. Max pain magnet. |
| OKX Funding Reset | Every 8h: 00:00, 08:00, 16:00 UTC | 05:30, 13:30, 21:30 IST | Highest funding rate changes near resets. |
| US CPI / FOMC | Usually 13:30 UTC | 19:00 IST | Maximum volatility. No entries 1h before/after. |
| US Non-Farm Payrolls | Fri 13:30 UTC | Fri 19:00 IST | High vol. Same rule as CPI. |

## Confluence Rules

### With Layer 2 (Derivatives)
```
IF funding rate resets at 08:00 UTC (London open)
   AND funding flips from negative to positive
   → Shorts capitulating as institutions arrive. Bullish.
   → Enter long on the London open if other layers confirm.

IF funding rate resets at 00:00 UTC (Asia open)
   AND funding spikes positive (>0.05%)
   → Asia retail chasing. Likely fade by London.
   → Don't enter on Asia funding spike. Wait for London.
```

### With Layer 3 (Options)
```
IF Deribit expiry approaching (Friday 08:00 UTC)
   AND BTC price far from max pain
   → Price gravitates toward max pain in final 48h.
   → Fade the direction away from max pain.
```

### With Layer 5 (On-Chain)
```
IF large exchange inflow detected during Asia session
   → Asian whales moving coins to exchanges before NY open.
   → Bearish. They expect to sell into NY liquidity.
  
IF large exchange inflow detected during NY session
   → Distribution into strength. More bearish than Asia inflows.
   → Exit or reduce.
```

### With Layer 6 (Macro)
```
IF US macro data release during NY session (CPI, FOMC, NFP)
   → NO ENTRIES 1 hour before or after release.
   → This is a HARD RULE. Override all other signals.
   → Re-evaluate 1 hour after release.
```

### With Regime
```
IF regime = LOW-VOL RANGE
   AND current session = Asia
   → Expect range to hold. Play range boundaries.
   → Breakout unlikely until London/NY volume arrives.

IF regime = HIGH-VOL RANGE
   AND current session = London/NY overlap
   → Maximum chaos. Stay flat or reduce size 50%.
```

## Session-Based Entry Rules

```
ENTRY TIMING (applies to ALL theses):

  BEST:    London open (08:00 UTC) — institutional validation
           NY open (13:30 UTC) — highest volume confirmation
           London/NY overlap (13:00-17:00 UTC) — max liquidity

  OK:      Asia if confirming existing trend (NOT initiating)

  AVOID:   Last 2 hours of NY (20:00-22:00 UTC) — late entries
           Weekends — no institutional flow
           1h before/after macro data — binary event risk
           First 30 min of any session — noise/gap fills
```

## How to Use (Python)

```python
from datetime import datetime
import pytz

def get_current_session() -> str:
    """Return current trading session."""
    now = datetime.now(pytz.UTC)
    hour = now.hour

    if 0 <= hour < 8:
        return "Asia"
    elif 8 <= hour < 9:
        return "Asia/London Overlap"
    elif 9 <= hour < 13:
        return "London"
    elif 13 <= hour < 17:
        return "London/NY Overlap ⚡"
    elif 17 <= hour < 22:
        return "New York"
    else:
        return "Weekend / After Hours"

def is_macro_news_window() -> bool:
    """Check if we're in a macro news blackout window."""
    now = datetime.now(pytz.UTC)
    weekday = now.weekday()
    hour = now.hour

    # CPI/FOMC typically Wed 13:30 UTC
    # NFP typically Fri 13:30 UTC
    if weekday in (2, 4) and 12 <= hour <= 15:
        return True  # Conservative: block Wed+Fri afternoons
    return False

def is_deribit_expiry_48h() -> bool:
    """Check if within 48h of monthly Deribit expiry."""
    now = datetime.now(pytz.UTC)
    # Last Friday of month at 08:00 UTC
    # Simplified: check if today is last Friday
    import calendar
    last_day = calendar.monthrange(now.year, now.month)[1]
    last_friday = last_day - ((last_day - 4 - now.weekday()) % 7)
    return now.day >= last_friday - 2 and now.day <= last_friday
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Manual timezone awareness during signal review |
| v1 | Python function returns current session. Integrated into daily check header. |
| v2 | Session-aware signal override: block entries in Asia alone unless trend-confirming |
| v3 | Macro news calendar integration — auto-block entries on FOMC/CPI/NFP days |
| v4 | Session volume profile tracker — which sessions produce winning trades vs losing |

## Integration with Thesis Checklist

- [ ] Add session indicator to daily signal check header: `Session: London/NY Overlap ⚡`
- [ ] Implement session-based entry filter in engine.py:
  - No entries on weekends
  - No entries 1h before/after macro news
  - Asia-only entries require existing trend confirmation
- [ ] Track trade performance by session — which sessions win most?

## Notes

- This module is crypto-specific. Equity markets have clean session boundaries (9:30-4:00). Crypto bleeds across sessions.
- IST is +5:30 from UTC. Asia = early morning IST, London = afternoon/evening IST, NY = night IST.
- The London/NY overlap (13:00-17:00 UTC / 18:30-22:30 IST) is where 40%+ of daily crypto volume happens.
- CME gap fills are one of crypto's most reliable patterns (90% fill rate). Always check Monday open.
- Deribit monthly expiry (last Friday 08:00 UTC) = max pain magnet. Track max pain price.
