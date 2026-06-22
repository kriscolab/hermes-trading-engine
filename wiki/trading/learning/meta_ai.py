#!/usr/bin/env python3
"""AI Meta-Optimizer — v12.0 (~25 params).

Weekly optimization of AI engine parameters:
- 5 entry signal thresholds / sizes
- Signal uniqueness enforcement params
- Position sizing per sub-sector

Usage:
    python3 meta_ai.py --dry-run
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
    return union_query("trades", "WHERE engine='ai' AND status='closed'")

def compute_metrics(trades):
    if not trades: return 0.0, 0.0, 0.0
    pnls = [t.get("pnl_realized",0) or 0 for t in trades]
    total = sum(pnls)
    wr = sum(1 for p in pnls if p>0)/max(len(pnls),1)
    rets = [(pnls[i]-pnls[i-1])/max(abs(pnls[i-1]),1) for i in range(1,len(pnls))]
    mu = sum(rets)/max(len(rets),1)
    var = sum((r-mu)**2 for r in rets)/max(len(rets)-1,1)
    std = math.sqrt(var) if var>0 else 0.001
    return total, wr, round((mu/std)*math.sqrt(252),3)

def build_space():
    p = []
    # Signal sizes per AI sub-sector
    p.append(Param("size_ai_e1_soxx", 20.0, 10.0, 30.0, "AI_E1 Capex: SOXX size %"))
    p.append(Param("size_ai_e2_dtcr", 15.0, 5.0, 25.0, "AI_E2 GPU: DTCR size %"))
    p.append(Param("size_ai_e3_igv", 15.0, 5.0, 25.0, "AI_E3 Software: IGV size %"))
    p.append(Param("size_ai_e4_soxx", 10.0, 5.0, 20.0, "AI_E4 DC Build: SOXX size %"))
    p.append(Param("size_ai_e5_tan", 10.0, 5.0, 20.0, "AI_E5 Renewables: TAN size %"))

    # Signal uniqueness
    p.append(Param("unique_family_dedup", 1, 1, 5, "Max positions per signal family"))
    p.append(Param("unique_same_ticker_cap", 2, 1, 4, "Max positions on same ticker"))
    p.append(Param("unique_family_cooldown", 30, 7, 90, "Days before family can re-enter"))

    # Sub-sector allocation caps
    p.append(Param("cap_semiconductors", 50.0, 30.0, 70.0, "Max % in semi (SOXX, INTC)"))
    p.append(Param("cap_software", 30.0, 15.0, 50.0, "Max % in software (IGV)"))
    p.append(Param("cap_infrastructure", 40.0, 20.0, 60.0, "Max % in infra (DTCR, TAN)"))
    p.append(Param("cap_media", 20.0, 5.0, 35.0, "Max % in media/comm (XLC)"))

    # Exit thresholds
    p.append(Param("exit_capex_cut_pct", -30.0, -50.0, -10.0, "Capex cut % for AI_X1"))
    p.append(Param("exit_gpu_oversupply_months", 3, 1, 6, "Months oversupply for AI_X2"))
    p.append(Param("exit_power_gw_shortfall", 15.0, 5.0, 30.0, "GW shortfall for AI_X4"))

    # Regime sizing
    p.append(Param("regime_cautious_size", 0.5, 0.2, 0.8, "Size mult in CAUTIOUS"))
    p.append(Param("regime_riskoff_new", 0.0, 0.0, 0.3, "Allow entries in RISK_OFF?"))

    # Conviction thresholds (SOXX price levels)
    p.append(Param("soxx_entry_min", 520, 400, 650, "Min SOXX for entry signal"))
    p.append(Param("igv_entry_min", 200, 150, 280, "Min IGV for entry signal"))
    p.append(Param("dtcr_entry_min", 40, 25, 60, "Min DTCR for entry signal"))
    p.append(Param("tan_entry_min", 45, 30, 70, "Min TAN for entry signal"))
    p.append(Param("xlc_entry_min", 120, 80, 160, "Min XLC for entry signal"))

    # Meta: size dampening based on consecutive signals
    p.append(Param("consecutive_dampen_pct", 25.0, 10.0, 50.0,
                   "Reduce size by % per consecutive entry in same family"))

    return ParamSpace(p, min_trades=10)


def main():
    dry_run = "--dry-run" in sys.argv
    summary = "--summary" in sys.argv

    print(f"AI Meta-Optimizer — {now_ist().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"  Params: ~{len(build_space().params)}")

    trades = load_trades()
    total_pnl, win_rate, sharpe = compute_metrics(trades)
    print(f"  Trades: {len(trades)} closed | Win: {win_rate:.1%} | P&L: ${total_pnl:,.0f} | Sharpe: {sharpe}")

    space = build_space()
    opt = MetaBase("ai", space)

    can_opt, reason = opt.should_optimize(len(trades))
    print(f"  Optimize: {can_opt} — {reason}")

    if not can_opt:
        if summary: print(f"AI meta: {len(trades)} trades, {reason}")
        return

    if dry_run:
        for p in space.params[:5]:
            print(f"  {p.name}={p.current:.1f} [{p.min_val}-{p.max_val}] {p.description}")
        print(f"  ... {len(space.params)-5} more params")
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


if __name__ == "__main__":
    main()
