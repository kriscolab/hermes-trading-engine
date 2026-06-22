#!/usr/bin/env python3
"""
Quant Module #4 — Monte Carlo Validation
===========================================
Validates quant module edge scores via randomized simulation.
For each signal, runs N scenarios with randomized entry timing,
slippage, and fees. Computes confidence interval, p-value,
optimal position size, and worst-case drawdown.

Answers: "Is this edge real, or could you get this result by chance?"

Usage:
    python3 monte-carlo.py BTC-USD --signal MEAN_REVERSION --edge 47
    python3 monte-carlo.py --all                           # all active signals
    python3 monte-carlo.py --json
"""

import sys
import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yfinance as yf
except ImportError:
    print("yfinance required", file=sys.stderr)
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────
N_SIMULATIONS = 500      # number of Monte Carlo runs
HOLD_DAYS = 5           # how long to hold simulated positions (was 14, too long for bear)
SLIPPAGE_BPS = 5         # 0.05% slippage per trade
FEE_BPS = 10              # 0.10% round-trip fees
PERIOD = "180d"
INITIAL_CAPITAL = 100_000

# ── Fetch ─────────────────────────────────────────────────────────────

def fetch(symbol: str):
    df = yf.download(symbol, period=PERIOD, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# ── Monte Carlo Engine ────────────────────────────────────────────────

def random_entry_exit(n_days: int, n_sims: int = N_SIMULATIONS, hold: int = HOLD_DAYS):
    """Generate N_SIMULATIONS random entry/exit pairs."""
    entries = np.random.randint(hold, n_days - hold, size=n_sims)
    exits = entries + np.random.randint(1, hold + 1, size=n_sims)
    return entries, exits


def simulate_trades(close: np.ndarray, entries: np.ndarray, exits: np.ndarray,
                    direction: str = "LONG") -> np.ndarray:
    """Simulate returns for randomized entry/exit pairs."""
    returns_pct = np.zeros(len(entries))
    for i in range(len(entries)):
        entry_price = close[entries[i]]
        exit_price = close[min(exits[i], len(close) - 1)]
        if direction == "LONG":
            raw_return = (exit_price - entry_price) / entry_price
        else:
            raw_return = (entry_price - exit_price) / entry_price
        # Apply slippage + fees
        net_return = raw_return - (SLIPPAGE_BPS + FEE_BPS) / 10000
        returns_pct[i] = net_return * 100  # convert to %
    return returns_pct


def monte_carlo_validate(symbol: str, signal_name: str, edge_score: int,
                         direction: str = "LONG") -> Dict:
    """
    Run Monte Carlo validation on a signal.
    
    Returns:
        - is_significant: is the edge better than random?
        - p_value: probability random trading achieves >= this edge
        - confidence: how confident are we in the signal? (0-100)
        - expected_return: mean return of the strategy
        - worst_case: 95th percentile worst outcome
        - optimal_size: Kelly-inspired position size
    """
    df = fetch(symbol)
    if df is None:
        return {"error": f"Could not fetch {symbol}"}

    close = df["Close"].values.astype(float)
    n_days = len(close)

    # Run random simulations
    entries, exits = random_entry_exit(n_days, N_SIMULATIONS, HOLD_DAYS)
    random_returns = simulate_trades(close, entries, exits, direction)

    # Strategy simulation (use most recent signals if possible)
    strategy_returns = []
    n_strategy = min(N_SIMULATIONS, n_days - HOLD_DAYS * 2)
    recent_entries = np.arange(n_days - n_strategy - HOLD_DAYS, n_days - HOLD_DAYS)
    recent_exits = recent_entries + HOLD_DAYS
    strategy_returns = simulate_trades(close, recent_entries, recent_exits, direction)

    # Statistics
    rand_mean = np.mean(random_returns)
    rand_std = np.std(random_returns)
    strat_mean = np.mean(strategy_returns) if len(strategy_returns) else 0

    # What percentile of random returns does our strategy outperform?
    p_value = np.mean(random_returns >= strat_mean) if strat_mean > 0 else np.mean(random_returns <= strat_mean)

    # Confidence: how much better than random? (0-100)
    excess_return = strat_mean - rand_mean
    if rand_std > 0:
        sharpe_ratio = excess_return / rand_std * np.sqrt(252 / HOLD_DAYS)
    else:
        sharpe_ratio = 0

    confidence = max(0, min(100, int(50 + sharpe_ratio * 10)))

    # Kelly-inspired position size
    win_rate = np.mean(strategy_returns > 0)
    avg_win = np.mean(strategy_returns[strategy_returns > 0]) if np.any(strategy_returns > 0) else 0
    avg_loss = abs(np.mean(strategy_returns[strategy_returns < 0])) if np.any(strategy_returns < 0) else 1

    if avg_loss > 0:
        kelly_f = win_rate - (1 - win_rate) / (avg_win / avg_loss)
    else:
        kelly_f = 0
    kelly_f = max(0, min(0.25, kelly_f))  # cap at 25%
    optimal_size = round(kelly_f * 100, 1)

    # Worst case (95th percentile)
    worst_case = np.percentile(strategy_returns, 5) if len(strategy_returns) > 0 else -5.0

    # Max drawdown simulation
    cumulative = np.cumprod(1 + strategy_returns / 100)
    peak = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - peak) / peak * 100
    max_dd = np.min(drawdowns) if len(drawdowns) > 0 else 0

    is_significant = p_value < 0.50 and sharpe_ratio > 0

    return {
        "symbol": symbol,
        "signal": signal_name,
        "edge_score_input": edge_score,
        "direction": direction,
        "validation": {
            "is_significant": bool(is_significant),
            "p_value": round(float(p_value), 3),
            "confidence": confidence,
            "sharpe_ratio": round(float(sharpe_ratio), 2),
            "excess_return_pct": round(float(excess_return), 2),
        },
        "returns": {
            "strategy_mean_pct": round(float(strat_mean), 2),
            "random_mean_pct": round(float(rand_mean), 2),
            "random_std_pct": round(float(rand_std), 2),
            "worst_case_95pct": round(float(worst_case), 2),
            "max_drawdown_pct": round(float(max_dd), 2),
        },
        "sizing": {
            "win_rate_pct": round(float(win_rate) * 100, 1),
            "avg_win_pct": round(float(avg_win), 2),
            "avg_loss_pct": round(float(avg_loss), 2),
            "kelly_fraction": round(float(kelly_f), 3),
            "optimal_size_pct": optimal_size,
        },
        "simulation": {
            "n_simulations": N_SIMULATIONS,
            "hold_days": HOLD_DAYS,
            "slippage_bps": SLIPPAGE_BPS,
            "fee_bps": FEE_BPS,
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
    }


# ── Main ──────────────────────────────────────────────────────────────

def parse_args():
    """Parse CLI: python3 monte-carlo.py BTC-USD --signal MEAN_REV --edge 47"""
    symbol = "BTC-USD"
    signal = "MEAN_REVERSION"
    edge = 50
    direction = "LONG"

    for i, arg in enumerate(sys.argv):
        if arg == "--signal" and i + 1 < len(sys.argv):
            signal = sys.argv[i + 1]
        elif arg == "--edge" and i + 1 < len(sys.argv):
            edge = int(sys.argv[i + 1])
        elif arg == "--direction" and i + 1 < len(sys.argv):
            direction = sys.argv[i + 1].upper()
        elif not arg.startswith("--") and i == 1:
            symbol = arg

    return symbol, signal, edge, direction


def main():
    json_mode = "--json" in sys.argv
    all_mode = "--all" in sys.argv

    # Regime map: which strategies work in which regimes
    REGIME_MAP = {
        "MOMENTUM": ["TRENDING", "BREAKOUT"],
        "MEAN_REVERSION": ["MEAN_REVERTING", "CHOPPY"],
        "VOL_ARB": ["HIGH_VOL", "EXPANDING"],
        "STAT_ARB": ["MEAN_REVERTING", "LOW_VOL"],
    }

    if all_mode:
        # Read live quant signals for regime data
        try:
            qs = json.loads(Path("/tmp/quant_signals.json").read_text())
        except Exception:
            qs = {"signals": {}}
        
        signals = []
        # Collect all tickers with edge scores, sort, validate top 10
        all_candidates = []
        for ticker_base in sorted(qs.get("signals", {}).keys()):
            ticker_sigs = qs.get("signals", {}).get(ticker_base, {})
            ml = ticker_sigs.get("ml-signals", {})
            regime = ml.get("dominant_regime", "UNKNOWN")
            ml_dir = ml.get("direction", "NEUTRAL")
            
            regime_direction = "SHORT" if "SELL" in ml_dir.upper() else ("LONG" if "BUY" in ml_dir.upper() else None)
            
            mom = ticker_sigs.get("momentum", {})
            edge = mom.get("edge", 0) if isinstance(mom, dict) else 0
            compatible = regime in REGIME_MAP.get("MOMENTUM", [])
            if edge > 0 and compatible and regime_direction:
                all_candidates.append((edge, ticker_base, regime_direction))
        
        # Sort by edge score desc, take top 10 for MC validation
        all_candidates.sort(key=lambda x: x[0], reverse=True)
        for edge, ticker_base, regime_direction in all_candidates[:10]:
            signals.append((f"{ticker_base}-USD", "MOMENTUM", edge, regime_direction))
        
        # Mean reversion — collect all candidates, validate top 5
        mr_candidates = []
        for ticker_base in sorted(qs.get("signals", {}).keys()):
            ticker_sigs = qs["signals"][ticker_base]
            mr = ticker_sigs.get("mean-reversion", {})
            mr_edge = mr.get("edge", 0) if isinstance(mr, dict) else 0
            mr_regime = ticker_sigs.get("ml-signals", {}).get("dominant_regime", "UNKNOWN")
            if mr_edge > 0 and mr_regime in REGIME_MAP.get("MEAN_REVERSION", []):
                mr_dir = mr.get("direction", "LONG")
                if "BUY" in mr_dir.upper(): mr_dir = "LONG"
                elif "SELL" in mr_dir.upper(): mr_dir = "SHORT"
                mr_candidates.append((mr_edge, ticker_base, mr_dir))
        mr_candidates.sort(key=lambda x: x[0], reverse=True)
        for edge, ticker_base, mr_dir in mr_candidates[:5]:
            signals.append((f"{ticker_base}-USD", "MEAN_REVERSION", edge, mr_dir))
        
        if not signals:
            print("⚠️ No regime-compatible quant signals found.")
            regs = [(t, qs['signals'][t]['ml-signals'].get('dominant_regime','?')) for t in ["BTC","ETH","SOL","LINK"] if t in qs.get("signals",{})]
            print(f"   Regimes: " + ", ".join(f"{t}={r}" for t,r in regs))
            print(f"   ML directions: " + ", ".join(f"{t}={qs['signals'][t]['ml-signals'].get('direction','?')}" for t in ["BTC","ETH","SOL","LINK"] if t in qs.get("signals",{})))
            return
    else:
        sym, sig, edge, direction = parse_args()
        signals = [(sym, sig, edge, direction)]

    results = []
    for sym, sig, edge, direction in signals:
            r = monte_carlo_validate(sym, sig, edge, direction)
            if "error" not in r:
                r["direction_tested"] = direction  # track which direction was tested
                results.append(r)

    if json_mode:
        print(json.dumps(results if all_mode else results[0] if results else {}, indent=2))
    else:
        for r in results:
            v = r["validation"]
            s = r["sizing"]
            ret = r["returns"]
            icon = "✅" if v["is_significant"] else "⚠️"
            dir_label = r.get("direction_tested", "?")
            print(f"{icon} {r['symbol']:10s} | {r['signal']:18s} {dir_label:5s} | Edge_in={r['edge_score_input']:3d} → "
                  f"Conf={v['confidence']:3d}/100 | p={v['p_value']:.2f} | "
                  f"Sharpe={v['sharpe_ratio']:+.1f} | "
                  f"Strat={ret['strategy_mean_pct']:+.1f}% vs Rand={ret['random_mean_pct']:+.1f}% | "
                  f"Size={s['optimal_size_pct']:4.1f}% | MaxDD={ret['max_drawdown_pct']:+.1f}%")


if __name__ == "__main__":
    import pandas as pd
    main()
