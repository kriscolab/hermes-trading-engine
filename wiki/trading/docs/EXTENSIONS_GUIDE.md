# Extensions Guide — Advanced Features & Configuration

## 1. Browser Use Web Scraping

### Setup
```bash
pip install browser-use playwright --break-system-packages
python3 -m playwright install chromium
```

### API Key
```
Key: bu_5mMPHFNkEXs4TS1DWfeVDIMkMnxoT-7JZz6WyUIafxg
Set as: export BROWSER_USE_API_KEY=bu_5mMPHFNkEXs4TS1DWfeVDIMkMnxoT-7JZz6WyUIafxg
```

### Usage (from Python)
```python
from browser_use import Agent

agent = Agent(
    task="Go to defillama.com/airdrops and list the top 5 upcoming airdrops",
    use_vision=False,
)
result = await agent.run()
```

### Known Issue: VPS Network Timeout
Browser Use may time out on VPS due to network restrictions. Fallback: `requests` + `BeautifulSoup` lightweight scraper available via `airdrop-scanner.py --live`.

### High-Value Use Cases
- **DefiLlama Airdrops:** Real-time opportunity scraping
- **SEC EDGAR:** 13F filings for Aschenbrenner quarterly holdings
- **Slickcharts:** Energy sector weight in S&P 500
- **Polymarket:** Event probabilities with skin-in-the-game
- **News monitoring:** Hormuz status, Mag7 capex, regulatory actions

---

## 2. API Key Configuration

### Required for Full Crypto Module Activation

```bash
# Add to ~/.hermes/.env or ~/.bashrc
export COINGLASS_API_KEY="your_key_here"
export GLASSNODE_API_KEY="your_key_here"
export WHALE_ALERT_API_KEY="your_key_here"
export CRYPTOQUANT_API_KEY="your_key_here"
```

### Free API Endpoints (No Key Needed)
```
Deribit:     https://www.deribit.com/api/v2/public/
Binance:     https://api.binance.com/api/v3/
DeFiLlama:   https://api.llama.fi/
alt.me:      https://api.alternative.me/fng/
Polymarket:  https://gamma-api.polymarket.com/events
Dune:        https://dune.com/browse/dashboards
yfinance:    import yfinance as yf
```

---

## 3. Building a New Module

### Template Structure
Every module follows this exact format:
```markdown
# Layer X — Module Name
Module: module-name
Signal Stack Position: Layer X
Data Source: API (free/paid)
Status: v0.1

## Why This Matters
## Data Sources
## Key Metrics
## Confluence Rules
## Divergence Signals
## How to Query (Python)
## Automation Plan
## Integration with Thesis Checklist
## Notes
```

### Module Checklist
- [ ] Free data source identified (API with no key, or free tier)
- [ ] Python query code tested and working
- [ ] At least 3 confluence rules (cross-layer interactions)
- [ ] At least 3 divergence signals
- [ ] Automation plan (v0.1 → v4 phases)
- [ ] Referenced by at least one thesis signals.md
- [ ] Added to sanity-audit.py layer mapping

---

## 4. Adding a New Cron Job Pattern

### Signal Check Cron Template
```
STEP 1: Fetch data → cd ~/vault/wiki/trading && python3 scripts/fetch-prices.py --portfolio
STEP 2: Run engine → cd paper-trader && python3 engine.py --thesis X --data /tmp/live_market_data.json
STEP 3: Run confluence → python3 engine.py --data /tmp/live_market_data.json --recommend
STEP 4: Portfolio → python3 engine.py --summary --prices "$(cat /tmp/portfolio_prices.json)"
STEP 5: Format + send → use delivery/formatter.py for consistent output
```

### Weekly Tracker Cron Template
```
STEP 1: Fetch all → python3 scripts/fetch-prices.py --all
STEP 2: Read tracker prices → parse /tmp/tracker_prices.json
STEP 3: Compute changes → basket % change, top/bottom performers
STEP 4: Run engine → python3 engine.py --thesis X
STEP 5: Format + send → delivery/formatter.py weekly_tracker()
```

---

## 5. Delivery Module Extension

### Adding a New Formatter

```python
# In delivery/formatter.py
def my_new_format(self, param1, param2) -> str:
    lines = [
        self._tag("category"),
        "",
        f"**{param1}**",
        param2,
        f"_{self._ist_now()}_",
    ]
    return self._truncate("\n".join(lines))
```

### Adding a New Category Tag
```python
CATEGORY_TAGS = {
    ...
    "my_category": "[MY_CAT] #my-tag",
}
```

---

## 6. Synthesis Layer Extension

### Adding a New Field to daily_state.json

1. Update `synthesis/schema.json` — add field to required properties
2. Update `synthesizer.py` ContextBuilder — include data in prompt
3. Update `synthesizer.py` Validator — validate new field
4. Update `correlator.py` — consume new field if relevant

### Adding a New Cross-Link Pattern

In `synthesis/correlator.py` CROSS_LINKS:
```python
{
    "name": "Pattern Name",
    "theses": ["commodity", "crypto"],
    "condition": "commodity_bullish AND crypto_bullish",
    "interpretation": "What this means...",
    "action": "What to do...",
    "severity": "BULLISH",  # or WARNING, INFO, BEARISH
}
```

---

## 7. Playwright + Chromium (Installed)

```
Location: ~/.cache/ms-playwright/chromium_headless_shell-1217
Version:  Chrome Headless Shell 147.0.7727.15
Status:   Installed and ready for Browser Use
```

### Alternative: Lightweight Scraping
When browser automation fails (VPS network issues):
```python
import requests
from bs4 import BeautifulSoup

resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(resp.text, "html.parser")
```
