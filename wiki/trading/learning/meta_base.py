#!/usr/bin/env python3
"""Meta Base v12 — shared optimization framework with safety guards.

PITFALL PREVENTION:
1. Min 20 closed trades before optimization
2. Walk-forward: optimize on trailing 60d, validate on prior 30d
3. Versioned parameters with timestamp + Sharpe
4. Auto-rollback: Sharpe_4wk < best * 0.8 → revert
5. Max ±30% param change per week (prevents oscillation)
"""

import json, math, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent
PARAMS_DIR = Path("/tmp")

def now_ist(): return datetime.now(IST)

@dataclass
class Param:
    name: str; default: float; min_val: float; max_val: float
    description: str = ""; current: float = None
    def __post_init__(self):
        if self.current is None: self.current = self.default
    def clamp(self, v): return max(self.min_val, min(self.max_val, v))
    def smooth_update(self, new_val, max_pct=0.30):
        delta = new_val - self.current
        max_d = abs(self.current) * max_pct if self.current != 0 else abs(new_val) * 0.5
        return self.clamp(self.current + max(-max_d, min(max_d, delta)))

@dataclass
class ParamSpace:
    params: List[Param]; min_trades: int = 20
    def apply_update(self, name, val, max_pct=0.30):
        for p in self.params:
            if p.name == name:
                p.current = p.smooth_update(val, max_pct)
                return p.current
        return val
    def get_vector(self): return [p.current for p in self.params]

@dataclass
class ParamVersion:
    version: str; applied_at: str; params: Dict[str, float]
    sharpe_4wk: float; win_rate_4wk: float; total_pnl_4wk: float
    trade_count: int; status: str = "active"
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

class MetaBase:
    def __init__(self, engine: str, space: ParamSpace):
        self.engine = engine; self.space = space
        self.ver_path = TRADING_DIR / "learning" / f"meta_{engine}_versions.json"
        self.out_path = PARAMS_DIR / f"{engine}_params.json"
        self.versions: List[ParamVersion] = self._load()

    def _load(self):
        if self.ver_path.exists():
            return [ParamVersion(**v) for v in json.loads(self.ver_path.read_text()).get("versions", [])]
        return []

    def _save(self):
        self.ver_path.parent.mkdir(parents=True, exist_ok=True)
        self.ver_path.write_text(json.dumps({
            "engine": self.engine, "last_updated": now_ist().isoformat(),
            "versions": [v.to_dict() for v in self.versions]}, indent=2, default=str))

    def _next_ver(self):
        if not self.versions: return "v1.0"
        m, n = self.versions[-1].version.lstrip("v").split(".")
        return f"v{m}.{int(n)+1}"

    def _best_sharpe(self):
        return max((v.sharpe_4wk for v in self.versions), default=-999.0)

    def compute_sharpe(self, pnl_series, rf=0.02):
        if len(pnl_series) < 10: return 0.0
        rets = [(pnl_series[i]-pnl_series[i-1])/max(abs(pnl_series[i-1]),1)
                for i in range(1, len(pnl_series))]
        if len(rets) < 2: return 0.0
        mu = sum(rets)/len(rets)
        var = sum((r-mu)**2 for r in rets)/max(len(rets)-1, 1)
        std = math.sqrt(var) if var > 0 else 0.001
        return round((mu - rf/252)/std * math.sqrt(252), 3) if std > 0 else 0.0

    def should_optimize(self, trade_count):
        if trade_count < self.space.min_trades:
            return False, f"Need {self.space.min_trades}+ trades, have {trade_count}"
        if self.versions:
            last = datetime.fromisoformat(self.versions[-1].applied_at.replace("Z","+00:00"))
            if (now_ist() - last.replace(tzinfo=None)).days < 7:
                return False, f"Last opt {self.versions[-1].version} <7d ago"
        return True, "ok"

    def check_rollback(self, current_sharpe):
        best = self._best_sharpe()
        if best <= 0 or not self.versions: return None
        if current_sharpe < best * 0.8:
            return max(self.versions, key=lambda v: v.sharpe_4wk).version
        return None

    def _sample_candidates(self, n=50):
        import random
        cur = self.space.get_vector()
        cands = []
        for _ in range(n):
            vec = []
            for p, cv in zip(self.space.params, cur):
                if random.random() < 0.3:
                    vec.append(p.clamp(cv + cv * random.uniform(-0.10, 0.10)))
                else:
                    vec.append(random.uniform(p.min_val, p.max_val))
            cands.append(vec)
        return cands

    def optimize(self, evaluator, iters=30):
        import random
        cands = self._sample_candidates(50)
        scores = []
        for vec in cands:
            try: scores.append(evaluator(vec) or 0.0)
            except: scores.append(0.0)
        best = cands[scores.index(max(scores))]
        result = {}
        for p, val in zip(self.space.params, best):
            result[p.name] = round(p.smooth_update(val, 0.30), 6)
        return result

    def deploy(self, params, sharpe, win_rate, pnl, trade_count):
        ver = self._next_ver(); ts = now_ist().isoformat()
        for name, val in params.items():
            self.space.apply_update(name, val, max_pct=1.0)
        pv = ParamVersion(ver, ts, params, round(sharpe,3), round(win_rate,3),
                          round(pnl,2), trade_count)
        self.versions.append(pv)
        if len(self.versions) > 1: self.versions[-2].status = "superseded"
        self._save()
        self.out_path.write_text(json.dumps({
            "engine": self.engine, "version": ver, "deployed_at": ts,
            "params": params, "metrics": {"sharpe_4wk": sharpe, "win_rate_4wk": win_rate,
            "total_pnl_4wk": pnl, "trade_count": trade_count}}, indent=2))
        return ver

    def rollback(self, target_ver):
        for v in self.versions:
            if v.version == target_ver:
                for name, val in v.params.items():
                    self.space.apply_update(name, val, max_pct=1.0)
                self.out_path.write_text(json.dumps({
                    "engine": self.engine, "version": f"ROLLBACK_{target_ver}",
                    "deployed_at": now_ist().isoformat(), "params": v.params,
                    "rolled_back_from": self.versions[-1].version}, indent=2))
                v.status = "active"; self._save()
                return v.params
        return {}
