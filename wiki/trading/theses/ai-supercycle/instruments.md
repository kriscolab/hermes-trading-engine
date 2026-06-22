# Instruments — AI Supercycle Thesis

Version: v0
Status: DEFINED
Last updated: May 17, 2026

---

## Layer ETFs (Stable, Weekly Track)

These proxies represent Aschenbrenner's 5 layers without tracking his 29 individual positions.

| Ticker | Name | Layer | Weight in Basket |
|--------|------|-------|-----------------|
| SOXX | iShares Semiconductor ETF | Silicon | 25% |
| IGV | iShares Expanded Tech-Software | Compute | 25% |
| DTCR | Global X Data Center & Digital REITs | Electrons | 20% |
| TAN | Invesco Solar ETF | Electrons (alt) | 15% |
| XLC | Communication Services Select SPDR | Optics/Connectivity | 15% |

**Basket calculation:** Equal-weight contribution. Weekly tracker computes AI-BASKET = 0.25×SOXX + 0.25×IGV + 0.20×DTCR + 0.15×TAN + 0.15×XLC.

---

## Conviction Stocks (Aschenbrenner's Long-Term Core)

Stocks held 3+ consecutive quarters by Situational Awareness LP.

| Ticker | Company | Layer | Avg Entry (est.) | Held Since | Status |
|--------|---------|-------|-----------------|------------|--------|
| INTC | Intel Corp | Silicon | ~$22.72 | Q1 2025 | Held unchanged — 0 shares traded in 4 quarters |
| CRWV | CoreWeave Inc | Compute | ~$12 (IPO) | Rebuilt Q3 2025 | #1 position at 14.04% of portfolio |
| BE | Bloom Energy Corp | Electrons | ~$25 | Q3 2025 | Largest single-stock bet at 16% |
| CORZ | Core Scientific Inc | Compute | ~$5 | Q1 2025 | 4-quarter consecutive build — activist 13D |

---

## Benchmark Instruments

| Ticker | Name | Role |
|--------|------|------|
| SPY | SPDR S&P 500 ETF Trust | Broad market |
| XLK | Technology Select Sector SPDR | Tech sector |
| QQQ | Invesco QQQ Trust | Growth/tech benchmark |

---

## Price Sources

| Ticker | Source | Method |
|--------|--------|--------|
| SOXX, IGV, DTCR, TAN, XLC, SPY, XLK, QQQ | yfinance | `yf.download(ticker, period="5d")` |
| INTC, BE, CORZ | yfinance | Same as above |
| CRWV | yfinance | May require web scrape if OTC |

---

## Rebalancing Rules

- Basket weights fixed at definition. Rebalanced only when fundamentals change (e.g., Aschenbrenner exits a conviction stock).
- If a conviction stock is fully exited from the 13F, remove from tracker within 2 weeks.
- New conviction stocks added only after 3+ consecutive quarters of holding.

---

## Notes

- CRWV is a relatively new IPO (March 2025). May have limited price history in yfinance.
- TAN (solar) is an imperfect proxy for "power infrastructure." Consider adding URA (uranium) or NLR (nuclear) if Aschenbrenner expands into nuclear.
- XLC includes social media companies — not a pure optics play. If a pure fiber/optics ETF emerges, replace.
