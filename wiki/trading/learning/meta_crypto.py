#!/usr/bin/env python3
"""Crypto Meta-Optimizer — v12.0 (~100 params).

Weekly Bayesian sweep of crypto engine parameters:
- 13 quant modules × 4 regimes = 52 weight params
- Arbiter thresholds (thesis_override_threshold, quant_vote_threshold)
- Execution gate params (volume_min, spread_max, persistence_checks)
- Thesis signal entry thresholds (4 entry × threshold + size_mult)
- Module auto-promote/suspend Sharpe thresholds

Input: journal_crypto.db via db_helper
Output: /tmp/crypto_params.json

Usage:
    python3 meta_crypto.py              # Full optimization
    python3 meta_crypto.py --dry-run    # Analyze only, no deploy
    python3 meta_crypto.py --summary    # Compact output
"""

import sys, os, json, math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from learning.meta_base import MetaBase, Param, ParamSpace

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent
PAPER_DIR = TRADING_DIR / "paper-trader"

# Regime names
REGIMES = ["TRENDING", "CHOPPY", "RISK_OFF", "VOLATILE", "NEUTRAL"]

# Module names (10 original + 3 v12)
MODULES = [
    "mean_reversion", "momentum", "correlation", "stat_arbitrage",
    "monte_carlo", "volatility_arbitrage", "ml_signals",
    "event_driven", "market_making", "microstructure",
    "orderflow", "tape_reading", "volume_profile",
]

def now_ist(): return datetime.now(IST)


def load_trades():
    """Load crypto trades from db_helper."""
    sys.path.insert(0, str(PAPER_DIR))
    from db_helper import union_query
    trades = union_query("trades", "WHERE engine='crypto' AND status='closed'")
    return trades


def compute_metrics(trades):
    """Compute Sharpe, win rate, total P&L from closed trades."""
    if not trades:
        return 0.0, 0.0, 0.0

    pnls = [t.get("pnl_realized", 0) or 0 for t in trades]
    total_pnl = sum(pnls)
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(pnls) if pnls else 0.0

    # Sharpe: compute from P&L series
    if len(pnls) < 10:
        return total_pnl, win_rate, 0.0

    rets = [(pnls[i] - pnls[i-1]) / max(abs(pnls[i-1]), 1) for i in range(1, len(pnls))]
    mu = sum(rets) / len(rets)
    var = sum((r - mu)**2 for r in rets) / max(len(rets) - 1, 1)
    std = math.sqrt(var) if var > 0 else 0.001
    sharpe = (mu / std) * math.sqrt(252) if std > 0 else 0.0

    return total_pnl, win_rate, round(sharpe, 3)


def build_space() -> ParamSpace:
    """Build crypto parameter space: ~100 params."""
    params = []

    # Module weights per regime (13 modules × 4 specific regimes = 52 params)
    # NEUTRAL uses average across regimes
    for regime in ["TRENDING", "CHOPPY", "RISK_OFF", "VOLATILE"]:
        for mod in MODULES:
            # Default: higher weight for established modules, lower for v12 modules
            default = 0.08 if mod in ("ml_signals", "momentum", "mean_reversion") else \
                      0.05 if mod in ("orderflow", "tape_reading", "volume_profile") else 0.06
            params.append(Param(
                f"weight_{regime}_{mod}", default, 0.0, 0.30,
                f"{regime} weight for {mod}"
            ))

    # Arbiter thresholds
    params.append(Param("arbiter_thesis_override", 0.75, 0.50, 0.95,
                        "Thesis must have this % conviction to override quant"))
    params.append(Param("arbiter_quant_vote", 0.25, 0.10, 0.50,
                        "Min ensemble score for quant to vote in arbiter"))
    params.append(Param("arbiter_conflict_tiebreaker", 0.50, 0.30, 0.70,
                        "Weight given to thesis vs quant in conflicts (0.5=equal)"))

    # Execution gate params
    params.append(Param("gate_volume_min_m", 10.0, 5.0, 50.0, "Min 24h volume in $M"))
    params.append(Param("gate_spread_max_pct", 0.5, 0.1, 2.0, "Max bid-ask spread %"))
    params.append(Param("gate_persistence_checks", 2.0, 1.0, 5.0, "Consecutive signal checks"))

    # Risk management params
    params.append(Param("risk_max_positions", 3.0, 1.0, 8.0, "Max concurrent positions"))
    params.append(Param("risk_max_trades_day", 10.0, 3.0, 30.0, "Max trades per day"))
    params.append(Param("risk_daily_loss_pct", 2.0, 0.5, 5.0, "Daily loss limit %"))
    params.append(Param("risk_consecutive_pause", 3.0, 2.0, 6.0, "Consecutive losses before pause"))

    # Thesis signal thresholds (E1-E4) — how much evidence needed?
    params.append(Param("thesis_e1_threshold", 0.03, 0.01, 0.10, "E1 ETF flow % of BTC mcap"))
    params.append(Param("thesis_e1_size_pct", 25.0, 10.0, 40.0, "E1 allocation %"))
    params.append(Param("thesis_e2_size_pct", 25.0, 10.0, 40.0, "E2 allocation %"))
    params.append(Param("thesis_e3_size_pct", 12.5, 5.0, 25.0, "E3 allocation %"))
    params.append(Param("thesis_e3bis_overrides", 1.0, 0.0, 1.0, "E3bis overrides E3 (binary)"))
    params.append(Param("thesis_e4_tactical_pct", 6.25, 2.0, 20.0, "E4 tactical allocation %"))

    # Position management
    params.append(Param("quant_tp_atr_mult", 1.5, 0.5, 3.0, "Quant TP as ATR multiple"))
    params.append(Param("quant_sl_atr_mult", 1.0, 0.3, 2.0, "Quant SL as ATR multiple"))
    params.append(Param("intraday_tp_atr_mult", 0.5, 0.2, 1.5, "Intraday TP as ATR multiple"))
    params.append(Param("intraday_sl_atr_mult", 0.3, 0.1, 1.0, "Intraday SL as ATR multiple"))
    params.append(Param("quant_max_hold_hours", 24.0, 4.0, 72.0, "Max quant position hold"))
    params.append(Param("intraday_max_hold_min", 60.0, 15.0, 240.0, "Max intraday hold"))

    # Module quality thresholds
    params.append(Param("mod_promote_sharpe", 0.5, 0.0, 2.0, "Sharpe to promote module"))
    params.append(Param("mod_suspend_sharpe", 0.0, -1.0, 0.5, "Sharpe to suspend module"))
    params.append(Param("mod_suspend_weeks", 2.0, 1.0, 4.0, "Weeks below threshold to suspend"))

    # Tactical layer allocation split
    params.append(Param("tactical_quant_pct", 50.0, 30.0, 70.0, "% of tactical to quant"))
    params.append(Param("tactical_intraday_pct", 30.0, 10.0, 50.0, "% of tactical to intraday"))
    params.append(Param("tactical_edge_pct", 20.0, 5.0, 40.0, "% of tactical to edge-gen"))

    return ParamSpace(params, min_trades=20)


def main():
    dry_run = "--dry-run" in sys.argv
    summary = "--summary" in sys.argv

    print(f"Crypto Meta-Optimizer — {now_ist().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"  Params: ~{len(build_space().params)}")

    # Load trade data
    trades = load_trades()
    total_pnl, win_rate, sharpe = compute_metrics(trades)
    print(f"  Trades: {len(trades)} closed | Win: {win_rate:.1%} | P&L: ${total_pnl:,.0f} | Sharpe: {sharpe}")

    space = build_space()
    opt = MetaBase("crypto", space)

    can_opt, reason = opt.should_optimize(len(trades))
    print(f"  Optimize: {can_opt} — {reason}")

    if not can_opt:
        if summary:
            print(f"Crypto meta: {len(trades)} trades, Sharpe={sharpe}, {reason}")
        return

    if dry_run:
        print("  DRY RUN — analyzing without deploying")
        # Show which modules have highest weights
        for regime in REGIMES:
            weights = {p.name: p.current for p in space.params
                      if p.name.startswith(f"weight_{regime}_")}
            top3 = sorted(weights.items(), key=lambda x: -x[1])[:3]
            print(f"  {regime}: " + ", ".join(f"{k.split('_')[-1]}={v:.3f}" for k, v in top3))
        return

    # Dummy evaluator: uses actual trade metrics
    def evaluator(vec):
        """Score based on current trade metrics (no forward sim yet)."""
        # Higher Sharpe + higher win_rate + positive P&L = better
        score = sharpe * 0.6 + win_rate * 0.3 + (1.0 if total_pnl > 0 else 0.0) * 0.1
        return max(0.0, score)

    result = opt.optimize(evaluator, iters=15)
    rollback_target = opt.check_rollback(sharpe)

    if rollback_target:
        print(f"  ⚠️ ROLLBACK NEEDED: current Sharpe {sharpe} < best * 0.8 → reverting to {rollback_target}")
        opt.rollback(rollback_target)
    else:
        ver = opt.deploy(result, sharpe, win_rate, total_pnl, len(trades))
        print(f"  ✅ Deployed {ver}")
        print(f"  Output: {opt.out_path}")

    if summary:
        print(f"\nCrypto meta {opt.versions[-1].version}: Sharpe={sharpe}, {len(trades)} trades")


if __name__ == "__main__":
    main()
