#!/usr/bin/env python3
"""Commodity Meta-Optimizer — v12.0 (~20 params).

Weekly optimization of commodity engine parameters:
- 4 entry signal thresholds (E1-E4S)
- 5 exit signal thresholds (X1-X5)
- Position sizing multipliers
- Regime-specific size overrides

Usage:
    python3 meta_commodity.py --dry-run
    python3 meta_commodity.py --summary
"""

import sys, os, json, math
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from learning.meta_base import MetaBase, Param, ParamSpace

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent
PAPER_DIR = TRADING_DIR / "paper-trader"

def now_ist(): return datetime.now(IST)


def load_trades():
    sys.path.insert(0, str(PAPER_DIR))
    from db_helper import union_query
    return union_query("trades", "WHERE engine='commodity' AND status='closed'")


def compute_metrics(trades):
    if not trades: return 0.0, 0.0, 0.0
    pnls = [t.get("pnl_realized", 0) or 0 for t in trades]
    total = sum(pnls)
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(pnls) if pnls else 0.0
    rets = [(pnls[i]-pnls[i-1])/max(abs(pnls[i-1]),1) for i in range(1,len(pnls))]
    mu = sum(rets)/max(len(rets),1)
    var = sum((r-mu)**2 for r in rets)/max(len(rets)-1,1)
    std = math.sqrt(var) if var > 0 else 0.001
    sharpe = round((mu/std)*math.sqrt(252),3) if std > 0 else 0.0
    return total, wr, sharpe


def build_space():
    p = []
    # Entry signal size allocations (% of $100K)
    p.append(Param("size_e1", 25.0, 10.0, 40.0, "E1 Brent Pullback size %"))
    p.append(Param("size_e2", 25.0, 10.0, 40.0, "E2 Brent Breakout size %"))
    p.append(Param("size_e3", 25.0, 10.0, 40.0, "E3 Energy Rotation size %"))
    p.append(Param("size_e4s", 25.0, 10.0, 40.0, "E4S Gold Tactical Short size %"))

    # Exit thresholds (how much evidence to exit?)
    p.append(Param("exit_threshold", 0.5, 0.2, 0.9, "Base exit evidence threshold"))
    p.append(Param("exit_structural_mult", 2.0, 1.0, 3.0, "Structural exit size multiplier (X2)"))

    # Regime overrides
    p.append(Param("regime_cautious_size", 0.5, 0.2, 0.8, "Size mult in CAUTIOUS regime"))
    p.append(Param("regime_riskoff_new", 0.0, 0.0, 0.3, "Allow new entries in RISK_OFF? (0=no)"))

    # Position management
    p.append(Param("pos_max_xle", 3, 1, 6, "Max XLE positions"))
    p.append(Param("pos_max_gld", 2, 1, 4, "Max GLD positions"))
    p.append(Param("pos_aging_days", 90, 30, 180, "Days before flagging stale position"))

    # Signal conviction (E4S short has different behavior than E1-E3 longs)
    p.append(Param("short_conviction_bonus", 0.0, -0.2, 0.3, "Extra conviction for short entries"))

    # XLE/Gold ratio thresholds
    p.append(Param("xle_xlk_ratio_min", 1.5, 1.0, 3.0, "Min XLE/XLK ratio for energy rotation (E3)"))

    # Brent price thresholds
    p.append(Param("brent_pullback_pct", -10.0, -30.0, -5.0, "Brent pullback % for E1"))
    p.append(Param("brent_breakout_pct", 10.0, 5.0, 25.0, "Brent breakout % for E2"))
    p.append(Param("brent_contango_days", 28, 14, 56, "Days of contango for X4 exit"))

    # VIX/risk thresholds
    p.append(Param("vix_entry_max", 35, 20, 50, "Max VIX to allow new entries"))
    p.append(Param("vix_riskoff_trigger", 40, 30, 60, "VIX level triggering RISK_OFF"))

    # Signal uniqueness (avoid duplicate XLE entries)
    p.append(Param("unique_signal_dedup_days", 30, 7, 90, "Days before same signal can re-enter"))

    return ParamSpace(p, min_trades=10)


def main():
    dry_run = "--dry-run" in sys.argv
    summary = "--summary" in sys.argv

    print(f"Commodity Meta-Optimizer — {now_ist().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"  Params: ~{len(build_space().params)}")

    trades = load_trades()
    total_pnl, win_rate, sharpe = compute_metrics(trades)
    print(f"  Trades: {len(trades)} closed | Win: {win_rate:.1%} | P&L: ${total_pnl:,.0f} | Sharpe: {sharpe}")

    space = build_space()
    opt = MetaBase("commodity", space)

    can_opt, reason = opt.should_optimize(len(trades))
    print(f"  Optimize: {can_opt} — {reason}")

    if not can_opt:
        if summary:
            print(f"Commodity meta: {len(trades)} trades, Sharpe={sharpe}, {reason}")
        return

    if dry_run:
        # Show current defaults
        for p in space.params:
            print(f"  {p.name}={p.current:.3f} [{p.min_val}-{p.max_val}] {p.description}")
        return

    def evaluator(vec):
        return max(0.0, sharpe * 0.7 + win_rate * 0.3)

    result = opt.optimize(evaluator, iters=10)
    rollback_target = opt.check_rollback(sharpe)

    if rollback_target:
        print(f"  ⚠️ ROLLBACK to {rollback_target}")
        opt.rollback(rollback_target)
    else:
        ver = opt.deploy(result, sharpe, win_rate, total_pnl, len(trades))
        print(f"  ✅ Deployed {ver}")

    if summary:
        v = opt.versions[-1] if opt.versions else None
        print(f"\nCommodity meta: {'v'+v.version if v else 'none'}, Sharpe={sharpe}")


if __name__ == "__main__":
    main()
