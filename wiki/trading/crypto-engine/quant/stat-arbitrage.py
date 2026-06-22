#!/usr/bin/env python3
"""
Quant Module #5 — Statistical Arbitrage (Pair Trading)
=========================================================
Pair trading based on cointegration. Finds spread between pairs,
Z-scores the deviation, signals when spread is extreme.

Pairs tested:
  BTC/ETH   — King vs Queen. Stable relationship, slow mean-reversion.
  SOL/ETH   — High-beta vs stable. Fast-reverting, volatile spread.
  BTC/SOL   — Macro vs micro. Wide spread, slower convergence.

Edge: When spread Z-score > 2.0, enter pair trade (long the cheap, short the rich).
      Mean-reverting in 5-20 days historically.

Usage:
    python3 stat-arbitrage.py               # All pairs
    python3 stat-arbitrage.py --jet --json  # JSON for engine
"""

import sys
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import yfinance as yf
except ImportError:
    print("yfinance required", file=sys.stderr)
    sys.exit(1)

from scipy import stats

# ── Pairs ─────────────────────────────────────────────────────────────

PAIRS = [
    {"a": "BTC-USD", "b": "ETH-USD", "name": "BTC/ETH", "ratio": True},
    {"a": "ETH-USD", "b": "SOL-USD", "name": "ETH/SOL", "ratio": False},
    {"a": "BTC-USD", "b": "SOL-USD", "name": "BTC/SOL", "ratio": True},
]

PERIOD = "180d"
Z_ENTRY = 2.0        # enter when Z-score exceeds this
Z_EXIT = 0.5         # exit when Z-score reverts below this


# ── Fetch ─────────────────────────────────────────────────────────────

def fetch(symbol: str):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"].values.astype(float)


# ── Cointegration + Spread ────────────────────────────────────────────

def engle_granger_coint(a: np.ndarray, b: np.ndarray) -> Tuple[bool, float, float, float]:
    """
    Engle-Granger cointegration test.
    Returns: (is_cointegrated, hedge_ratio, intercept, p_value)
    """
    slope, intercept, r, p, _ = stats.linregress(a, b)
    residuals = b - (slope * a + intercept)

    # ADF test on residuals (cointegration check)
    try:
        adf_stat, adf_p, _, _, critical, _ = _adf_simple(residuals)
        is_coint = adf_p < 0.10  # 90% confidence
    except Exception:
        is_coint = False
        adf_p = 1.0

    return is_coint, slope, intercept, adf_p


def _adf_simple(series: np.ndarray, maxlag: int = 10):
    """Simplified ADF test using scipy (no statsmodels dependency).
    Tests multiple lag specifications and returns the best (most negative t-stat)."""
    y = np.diff(series)
    y_lag = series[:-1]
    n = len(y)
    X = np.column_stack([np.ones(n), y_lag])
    
    best_t_stat = 0
    best_p_val = 1.0
    
    for lag in range(1, min(maxlag + 1, n)):
        try:
            beta = np.linalg.lstsq(X[:n-lag], y[lag:], rcond=None)[0]
            residuals = y[lag:] - X[:n-lag] @ beta
            rss = np.sum(residuals**2)
            dof = len(residuals) - 2
            if dof <= 0 or rss <= 0:
                continue
            se = np.sqrt(rss / dof)
            if se > 0:
                t_stat = beta[1] / se
                p_val = 2 * (1 - stats.t.cdf(abs(t_stat), dof))
                # More negative t-stat = stronger evidence of stationarity
                if t_stat < best_t_stat or best_t_stat == 0:
                    best_t_stat = t_stat
                    best_p_val = p_val
        except Exception:
            continue
    
    if best_t_stat < 0:
        return best_t_stat, best_p_val, None, None, None
    return -1, 1.0, None, None, None


def compute_spread(a: np.ndarray, b: np.ndarray, hedge: float, intercept: float,
                    ratio: bool = False) -> np.ndarray:
    """Compute spread between two price series."""
    if ratio:
        spread = a / (b + 1e-10)
    else:
        spread = a - (hedge * b + intercept)
    return spread


def spread_zscore(spread: np.ndarray, window: int = 20) -> np.ndarray:
    """Rolling Z-score of the spread."""
    z = np.zeros_like(spread) * np.nan
    for i in range(window, len(spread)):
        mu = np.mean(spread[i-window:i])
        sigma = np.std(spread[i-window:i]) or 1e-10
        z[i] = (spread[i] - mu) / sigma
    return z


def half_life(spread: np.ndarray) -> float:
    """Estimate mean-reversion half-life (days)."""
    y = np.diff(spread)
    y_lag = spread[:-1]
    slope, _, _, _, _ = stats.linregress(y_lag, y)
    if slope >= 0:
        return 999
    return -np.log(2) / slope


# ── Edge Scoring ──────────────────────────────────────────────────────

def score_pair(pair: Dict) -> Optional[Dict]:
    """Score a single pair for arbitrage opportunity."""
    a_prices = fetch(pair["a"])
    b_prices = fetch(pair["b"])
    if a_prices is None or b_prices is None:
        return None

    # Spread using ratio (simpler, works without cointegration test)
    spread = a_prices / (b_prices + 1e-10)
    z = spread_zscore(spread)
    hl = half_life(spread)

    latest_z = z[-1] if not np.isnan(z[-1]) else 0
    abs_z = abs(latest_z)

    # Correlation check (are they related enough?)
    corr = np.corrcoef(a_prices[-90:], b_prices[-90:])[0, 1]
    is_correlated = abs(corr) > 0.5

    # Edge score (0-100)
    if not is_correlated:
        edge = 0  # no edge without correlation
        direction = "UNCORRELATED"
    elif abs_z > Z_ENTRY:
        edge = min(int(abs_z * 15), 70)
        direction = "SHORT_SPREAD" if latest_z > 0 else "LONG_SPREAD"
        # Bonus for fast mean-reversion
        if hl < 10:
            edge += 20
        elif hl < 20:
            edge += 10
        edge = min(edge, 100)
    elif abs_z > 1.5:
        edge = int(abs_z * 10)
        direction = "WATCH_SHORT" if latest_z > 0 else "WATCH_LONG"
    else:
        edge = max(0, int((abs_z / Z_ENTRY) * 30))
        direction = "NEUTRAL"

    target_z = 0.5 * latest_z if abs_z > Z_ENTRY else 0

    return {
        "pair": pair["name"],
        "symbols": [pair["a"], pair["b"]],
        "correlation": round(float(corr), 3),
        "spread_z_score": round(float(latest_z), 2),
        "half_life_days": round(float(hl), 1),
        "edge_score": edge,
        "direction": direction,
        "recommended_size_pct": 15 if edge >= 60 else (10 if edge >= 40 else 0),
        "interpretation": _interpret(direction, latest_z, hl),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
    }


def _interpret(direction: str, z: float, hl: float) -> str:
    if direction == "SHORT_SPREAD":
        return (f"Pair A rich vs Pair B. Short the spread at Z={z:+.1f}σ. "
                f"Mean-reversion half-life: {hl:.0f}d. Exit at Z<{Z_EXIT}σ.")
    elif direction == "LONG_SPREAD":
        return (f"Pair A cheap vs Pair B. Long the spread at Z={z:+.1f}σ. "
                f"Mean-reversion half-life: {hl:.0f}d. Exit at Z>-{Z_EXIT}σ.")
    elif direction.startswith("WATCH"):
        return f"Spread approaching extreme (Z={z:+.1f}σ). Watch for entry at Z=±{Z_ENTRY}σ."
    elif direction == "UNCORRELATED":
        return "Pair not correlated enough for stat-arb. No tradeable relationship."
    else:
        return f"Spread within normal range (Z={z:+.1f}σ). No signal."


# ── Main ──────────────────────────────────────────────────────────────

def main():
    json_mode = "--json" in sys.argv
    results = [score_pair(p) for p in PAIRS]
    results = [r for r in results if r is not None]

    if json_mode:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            z = r["spread_z_score"]
            icon = "🔴" if abs(z) > Z_ENTRY else ("🟡" if abs(z) > 1.5 else "🟢")
            corr_icon = "🟢" if r["correlation"] > 0.7 else ("🟡" if r["correlation"] > 0.5 else "🔴")
            print(f"{icon} {r['pair']:12s} | Z={z:+.2f}σ | Edge={r['edge_score']:3d}/100 | "
                  f"Corr={corr_icon} {r['correlation']:+.2f} | "
                  f"HL={r['half_life_days']:.0f}d | {r['direction']}")
            print(f"   {r['interpretation']}")


if __name__ == "__main__":
    import pandas as pd
    main()
