# Integration Guide — Adding to the Platform

## How to Add a New Thesis

### Step 1: Create thesis directory
```
mkdir -p vault/wiki/trading/theses/new-thesis/
```

### Step 2: Write three files
```
theses/new-thesis/
├── thesis.md          ← codified claims, risk register
├── instruments.md     ← tickers, ETFs, data sources
└── signals.md         ← entry/exit triggers with falsifiable conditions
```

### Step 3: Add signal definitions to engine.py
```python
# In engine.py, add after existing signal blocks:

NEW_ENTRY_SIGNALS: Dict[str, Signal] = {
    "NEW_E1": Signal(
        signal_id="NEW_E1",
        name="Your Entry Signal",
        signal_type=SignalType.ENTRY,
        description="Trigger condition description",
        trigger_condition="your_condition",
        action="Enter X% into Y",
        allocation_pct=25.0,
        priority=1,
    ),
}

NEW_EXIT_SIGNALS: Dict[str, Signal] = {
    "NEW_X1": Signal(...),
}

# Add to ALL_SIGNALS registry:
ALL_SIGNALS = {
    "commodity": (ENTRY_SIGNALS, EXIT_SIGNALS),
    "ai": (AI_ENTRY_SIGNALS, AI_EXIT_SIGNALS),
    "crypto": (CRYPTO_ENTRY_SIGNALS, CRYPTO_EXIT_SIGNALS),
    "new": (NEW_ENTRY_SIGNALS, NEW_EXIT_SIGNALS),  # ← ADD THIS
}
```

### Step 4: Update CLI choices
```python
parser.add_argument("--thesis", choices=["commodity", "ai", "crypto", "new"])
```

### Step 5: Register in theses/index.md
```markdown
| [[new-thesis/thesis]] — Your thesis description | Defined | v0 | Date | Not yet live |
```

### Step 6: Create cron jobs
```bash
# Daily signal check (9:25 AM IST = 3:55 UTC)
cronjob action=create deliver=telegram:-1003894402844 \
  name="New Thesis Daily Check" \
  schedule="55 3 * * *" \
  prompt="Run: cd ~/vault/wiki/trading/paper-trader && python3 engine.py --thesis new --data /tmp/live_market_data.json"

# Weekly tracker (Sun 9:00 PM IST = 15:30 UTC)
cronjob action=create deliver=telegram:-1003894402844 \
  name="New Thesis Weekly Tracker" \
  schedule="30 15 * * 0" \
  prompt="..."
```

---

## How to Add a New Module

### Step 1: Create the module file
```
modules/your-module.md
```

### Step 2: Follow the standard template
```markdown
# Layer X — Module Name

Module: your-module
Signal Stack Position: Layer X / Gap X
Data Source: API name (free/paid)
Status: v0.1 — DEFINED, not yet automated

## Why This Matters
(2-3 sentences on what edge this module provides)

## Data Sources
(API endpoints, keys needed, rate limits)

## Key Metrics
| Metric | What It Tells You | Signal |

## Confluence Rules
### With Other Layers
IF X AND Y → Z

## Divergence Signals
🔴 Pattern → Interpretation → Action

## How to Query (Python)
(Working code example with real API endpoints)

## Automation Plan
| Phase | What |

## Integration with Thesis Checklist
- [ ] Add to daily signal check
```

### Step 3: Reference from relevant thesis
Add module name to thesis signals.md Notes section so sanity audit doesn't flag it as unreferenced.

---

## How to Add a New Cron Job

```bash
cronjob action=create \
  deliver=telegram:-1003894402844 \
  name="Job Name [TRADING DESK]" \
  schedule="0 9 * * *" \
  prompt="Step-by-step instructions for the cron agent."
```

### IST to UTC conversion
```
IST = UTC + 5:30
8:30 AM IST  = 3:00 UTC
9:00 AM IST  = 3:30 UTC
8:00 PM IST  = 14:30 UTC
9:30 PM IST  = 16:00 UTC
```

---

## How to Add a New Data Source

### Step 1: Add to fetch-prices.py
```python
NEW_SYMBOLS = {
    "TICKER1": "key_name1",
    "TICKER2": "key_name2",
}
```

### Step 2: Add usage mapping in sanity audit
```python
usage_map = {
    ...
    "key_name1": ["engine.py signal_X", "weekly tracker"],
}
```

### Step 3: Update market_data JSON template in QUICK_REFERENCE.md

---

## How to Run the Sanity Audit After Changes

```bash
cd ~/vault/wiki/trading
python3 synthesis/sanity-audit.py --summary
```

Fix any issues before deploying cron jobs. Expected: "✅ All checks passed."
