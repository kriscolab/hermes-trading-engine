# Fundamental Analysis — Equity Earnings, Ratios & Financial Health

Module: fundamental
Signal Stack Position: Supplementary (Equity Theses)
Data Source: yfinance (free) + Alpha Vantage (free tier, 25 calls/day)
Status: v0.1 — DEFINED, Python code provided

## Why This Matters

Fundamentals tell you what the market SHOULD be pricing, not what it IS pricing. Price action and volume show you the auction. Fundamentals show you the asset. When fundamentals and price diverge, that's where alpha lives — the market is mispricing something.

For commodity thesis (Currie): Free cash flow yields of energy majors tell you if the rotation from Mag7 to Mun7 is based on real earnings or just narrative.

For AI thesis (Aschenbrenner): Capex growth rates, revenue per GPU, and semiconductor margins tell you if the AI build-out thesis is accelerating or decelerating.

For crypto: Fundamentals don't apply directly, but stablecoin market cap, exchange reserves, and protocol revenue are crypto-native fundamentals tracked in other modules.

## Data Sources

| Source | What | Rate Limit | Key Needed |
|--------|------|-----------|------------|
| yfinance | FCF, P/E, revenue, debt, market cap | No limit | None |
| Alpha Vantage | Income statement, balance sheet, ratios | 25/day | None (free apikey) |
| Financial Modeling Prep | Advanced fundamentals, DCF | 250/day free | Free apikey |
| FRED | Macro data (GDP, rates, CPI) | No limit | None |

## Key Metrics

| Metric | What It Tells You | Signal |
|--------|------------------|--------|
| Free Cash Flow Yield | FCF / Market Cap. How much cash the business generates. | >10% = undervalued. <5% = overvalued. |
| P/E Ratio | Price / Earnings. Valuation multiple. | Sector-dependent. Compare to 5-year avg. |
| Debt/Equity | Leverage. How much debt vs equity. | >2.0 = risky. <0.5 = conservative. |
| Revenue Growth YoY | Year-over-year revenue change. Growth trajectory. | >15% = high growth. <0% = declining. |
| Gross Margin | Revenue minus COGS / Revenue. Pricing power. | Expanding = bull. Contracting = bear. |
| Capex / Revenue | Capital expenditure as % of revenue. Reinvestment rate. | Rising = growth investment. Falling = harvesting. |
| FCF / Share | Free cash flow per share. True shareholder return. | Rising = value creation. Falling = value destruction. |
| Dividend Yield | Dividend / Price. Income return. | >3% = income play. Context-dependent. |
| EV/EBITDA | Enterprise Value / EBITDA. Better than P/E for capital-heavy. | <10x = cheap. >20x = expensive. |

## Confluence Rules

### With Macro Module (L6)
```
IF FCF yields rising across Mun7 AND DXY falling
   → Energy majors are undervalued + USD tailwind.
   → Commodity thesis (E1) has fundamental confirmation.

IF FCF yields flat/dropping AND DXY rising
   → Energy fundamentals not improving + FX headwind.
   → Commodity thesis may be premature. Reduce size.
```

### With Correlation Module (Gap 4)
```
IF Mun7 aggregate FCF > Mag7 aggregate FCF
   → Rotation thesis (Currie) fundamentally confirmed.
   → Favor commodity over AI allocation.

IF Mag7 FCF still growing faster than Mun7
   → Rotation thesis not yet supported by fundamentals.
   → Wait for FCF crossover.
```

### With Sentiment (Gap 3)
```
IF fundamentals improving AND Fear & Greed < 25
   → Extreme fear with improving fundamentals.
   → Strong contrarian buy. Market not pricing the improvement.

IF fundamentals deteriorating AND Fear & Greed > 75
   → Extreme greed with worsening fundamentals.
   → Strong contrarian sell. Market ignoring fundamentals.
```

## Divergence Signals

```
🔴 PRICE RISING, FCF FALLING
   → Price disconnected from cash generation. Speculation.
   → Reduce position. Bubble risk.

🟢 PRICE FALLING, FCF RISING
   → Market selling but business improving. Value opportunity.
   → Accumulate. Market will eventually price this correctly.

🔴 REVENUE GROWING, MARGINS CONTRACTING
   → Growth at expense of profitability. Unsustainable.
   → Sector-wide issue or company-specific? Investigate.

🟢 REVENUE FLAT, MARGINS EXPANDING
   → Operational efficiency improving. Earnings power increasing.
   → Bullish. Company extracting more from same revenue base.

🔴 CAPEX RISING, FCF FALLING
   → Heavy investment phase. May pay off or may destroy capital.
   → Context-dependent. For AI thesis: good (building infra). For energy: neutral.
```

## How to Query (Python)

```python
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

def fetch_fundamentals(ticker):
    """Fetch key fundamentals from yfinance (free)."""
    stock = yf.Ticker(ticker)
    info = stock.info

    # Balance Sheet
    bs = stock.balance_sheet
    income = stock.financials
    cashflow = stock.cashflow

    total_debt = bs.loc['Total Debt'].iloc[0] if 'Total Debt' in bs.index else 0
    equity = bs.loc['Stockholders Equity'].iloc[0] if 'Stockholders Equity' in bs.index else 1

    revenue = income.loc['Total Revenue'].iloc[0] if 'Total Revenue' in income.index else 0
    revenue_prev = income.loc['Total Revenue'].iloc[1] if len(income.columns) > 1 and 'Total Revenue' in income.index else revenue

    gross_profit = income.loc['Gross Profit'].iloc[0] if 'Gross Profit' in income.index else 0

    fcf = cashflow.loc['Free Cash Flow'].iloc[0] if 'Free Cash Flow' in cashflow.index else 0

    market_cap = info.get('marketCap', 0)
    pe_ratio = info.get('trailingPE', None)
    dividend_yield = info.get('dividendYield', 0)

    return {
        'ticker': ticker,
        'name': info.get('shortName', ticker),
        'sector': info.get('sector', 'Unknown'),
        'market_cap_b': round(market_cap / 1e9, 1),
        'pe_ratio': round(pe_ratio, 1) if pe_ratio else None,
        'fcf_m': round(fcf / 1e6, 1) if fcf else 0,
        'fcf_yield_pct': round((fcf / market_cap) * 100, 2) if fcf and market_cap else 0,
        'revenue_m': round(revenue / 1e6, 1),
        'revenue_growth_yoy_pct': round(((revenue - revenue_prev) / revenue_prev) * 100, 2) if revenue_prev else 0,
        'gross_margin_pct': round((gross_profit / revenue) * 100, 2) if revenue and gross_profit else 0,
        'debt_equity': round(total_debt / equity, 2) if equity else None,
        'dividend_yield_pct': round(dividend_yield * 100, 2) if dividend_yield else 0,
    }

def fetch_mun7_fundamentals():
    """Fetch aggregate fundamentals for Mun7 energy majors."""
    mun7 = ["XOM", "CVX", "COP", "SHEL", "TTE", "BP", "EQNR"]
    results = {}
    total_fcf, total_mcap = 0, 0

    for ticker in mun7:
        try:
            f = fetch_fundamentals(ticker)
            results[ticker] = f
            total_fcf += f['fcf_m']
            total_mcap += f['market_cap_b']
        except Exception:
            results[ticker] = None

    return {
        'individuals': results,
        'aggregate_fcf_m': round(total_fcf, 0),
        'aggregate_mcap_b': round(total_mcap, 0),
        'aggregate_fcf_yield_pct': round((total_fcf / (total_mcap * 1000)) * 100, 2) if total_mcap else 0,
        'tickers_succeeded': sum(1 for v in results.values() if v is not None),
    }

def fetch_alpha_vantage_fundamentals(ticker, apikey="demo"):
    """Fetch detailed fundamentals from Alpha Vantage (free tier). Use 'demo' for testing."""
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": apikey,
            },
            timeout=10
        )
        data = r.json()
        if 'Symbol' not in data:
            return None
        return {
            'ticker': data.get('Symbol'),
            'pe': float(data.get('PERatio', 0)),
            'peg': float(data.get('PEGRatio', 0)),
            'pb': float(data.get('PriceToBookRatio', 0)),
            'ev_ebitda': float(data.get('EVToEBITDA', 0)),
            'roe': float(data.get('ReturnOnEquityTTM', 0)),
            'debt_equity': float(data.get('DebtToEquityRatio', 0)),
            'profit_margin': float(data.get('ProfitMargin', 0)),
            'revenue_growth': float(data.get('QuarterlyRevenueGrowthYOY', 0)),
            'earnings_growth': float(data.get('QuarterlyEarningsGrowthYOY', 0)),
        }
    except Exception:
        return None
```

## Automation Plan

| Phase | What |
|-------|------|
| v0.1 | Python functions (above). Manual queries. |
| v1 | Auto-fetch quarterly fundamentals for Mun7/Mag7/AI conviction stocks |
| v2 | Integrate with commodity thesis: FCF yield feeds E1/E2 signals |
| v3 | Integrate with AI thesis: capex/revenue trends feed AI_E1/AI_E5 |
| v4 | DCF modeling for thesis valuation targets |

## Integration with Thesis Checklist

- [ ] Commodity thesis: Mun7 FCF yield → E1 Brent pullback confirmation
- [ ] AI thesis: Mag7 capex/revenue → AI_E1 capex acceleration, AI_X2 capex drop
- [ ] Crypto thesis: Not applicable (use crypto-native fundamentals)

## Notes

- yfinance fundamentals are quarterly delayed. Not real-time.
- Alpha Vantage free tier is 25 calls/day — use sparingly.
- Mun7 FCF yields are typically 8-15%. When >15%, thesis is strongly confirmed.
- Mag7 FCF yields are typically 2-5%. When >5%, they become value plays.
- Fundamental analysis complements technical. Never trade on fundamentals alone.
- The Currie thesis trigger (Brent + FCF) already combines technical + fundamental.
