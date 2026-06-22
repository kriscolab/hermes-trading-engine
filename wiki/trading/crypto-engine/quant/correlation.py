#!/usr/bin/env python3
"""
Quant Module #2 — Correlation Matrix
=======================================
Cross-asset (BTC/SPY, ETH/NASDAQ) + cross-crypto (ETH/BTC, SOL/BTC).
Computed from OHLCV (yfinance — free). Detects decoupling events.

Edge: Low correlation between assets that normally move together = opportunity.
      Example: BTC/SPY correlation at 0.15 (decoupling) → crypto-native move.
      Example: BTC.D dropping, ETH outperforming → rotation signal.

Usage:
    python3 correlation.py               # Full matrix
    python3 correlation.py --json        # JSON for engine
"""

import sys
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

try:
    import yfinance as yf
except ImportError:
    print("yfinance required", file=sys.stderr)
    sys.exit(1)

# ── Pairs ──
PAIRS = [
    ("BTC-USD", "SPY", "BTC/SPY", "Crypto vs equities — decoupling = crypto-native"),
    ("ETH-USD", "QQQ", "ETH/NASDAQ", "Crypto vs tech — decoupling = sector divergence"),
    ("ETH-USD", "BTC-USD", "ETH/BTC", "Alt rotation — ETH/BTC rising = alt season"),
    ("SOL-USD", "BTC-USD", "SOL/BTC", "Solana dominance vs Bitcoin"),
    ("BTC-USD", "GLD", "BTC/GLD", "Digital gold vs physical gold"),
]

PERIOD = "90d"
WINDOWS = [30, 14, 7]  # lookback windows for correlation

# ── Compute ───────────────────────────────────────────────────────────

def fetch(symbol: str):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].values.astype(float)


def rolling_correlation(a: np.ndarray, b: np.ndarray, window: int) -> np.ndarray:
    """Rolling Pearson correlation."""
    min_len = min(len(a), len(b))
    a, b = a[-min_len:], b[-min_len:]
    n = len(a)
    corr = np.zeros(n) * np.nan
    for i in range(window, n):
        corr[i] = np.corrcoef(a[i-window:i], b[i-window:i])[0, 1]
    return corr


def analyze_all() -> List[Dict]:
    results = []
    for sym1, sym2, label, desc in PAIRS:
        a = fetch(sym1)
        b = fetch(sym2)
        if a is None or b is None:
            continue

        correlations = {}
        for w in WINDOWS:
            corr = rolling_correlation(a, b, w)
            val = corr[-1] if not np.isnan(corr[-1]) else 0
            change = val - (corr[-w-1] if len(corr) > w and not np.isnan(corr[-w-1]) else val)
            correlations[f"{w}d"] = {
                "value": round(float(val), 3),
                "change": round(float(change), 3),
                "trending": "up" if change > 0.05 else ("down" if change < -0.05 else "flat"),
            }

        latest = correlations["30d"]["value"]
        trend = correlations["14d"]["trending"]

        # Edge: decoupling = opportunity
        if abs(latest) < 0.3:
            signal = "DECOUPLING"
            interpretation = "Assets moving independently. Crypto-native factors dominate. Signal: trade crypto on own fundamentals."
        elif latest > 0.7:
            signal = "HIGH_CORR"
            interpretation = "Assets highly correlated. No diversification benefit. Use one as hedge for the other."
        else:
            signal = "MODERATE"
            interpretation = "Normal correlation. No edge from relationship alone."

        results.append({
            "pair": label,
            "symbols": [sym1, sym2],
            "description": desc,
            "correlations": correlations,
            "signal": signal,
            "interpretation": interpretation,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        })

    return results


# ── Main ──────────────────────────────────────────────────────────────

def main():
    json_mode = "--json" in sys.argv
    results = analyze_all()

    if json_mode:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            c30 = r["correlations"]["30d"]
            c14 = r["correlations"]["14d"]
            icon = {"DECOUPLING": "🟢", "HIGH_CORR": "⚫", "MODERATE": "🟡"}.get(r["signal"], "⚫")
            print(f"{icon} {r['pair']:12s} | 30d={c30['value']:+.2f} ({c30['trending']}) | "
                  f"14d={c14['value']:+.2f} ({c14['trending']}) | {r['signal']}")
        print(f"\n{results[0]['interpretation'] if results else 'No data'}")


if __name__ == "__main__":
    import pandas as pd
    main()
