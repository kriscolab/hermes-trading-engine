#!/usr/bin/env python3
"""Crypto Engine — v12.0. $100K isolated. Multi-thesis + quant + intraday. Every 5 min.
Thesis 1: Fink "Institutional Inevitability" (active, 50% alloc).

WIRED: Gate (5-point check) + RiskManager (circuit breakers) + persistence tracking.
"""

import sys, os, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crypto-engine"))
from engines.base import EngineBase, now_ist, get_live_price, load_json
from regime_detector import detect_crypto_regime
from quant.execution_gate import Gate, update_persistence
from quant.risk_manager import RiskManager
from pathlib import Path

QUANT_PATH = Path("/tmp/quant_signals.json")
INTRADAY_PATH = Path("/tmp/intraday_signals.json")
EDGE_PATH = Path("/tmp/edge_generator.json")
ETF_FLOWS_PATH = Path("/tmp/etf_flows.json")
INVALIDATION_PATH = Path("/tmp/crypto_invalidation.json")

INTRADAY_TICKERS = ["BTC", "ETH", "SOL", "AVAX", "LINK", "DOGE"]
IST = timezone(timedelta(hours=5, minutes=30))

# TICKER MAPPING — thesis uses ETFs, tactical uses Hyperliquid spot
THESIS_TICKER_MAP = {"BTC": "IBIT", "ETH": "ETHA"}  # ETFs for thesis

def _load_tactical_map():
    """Load tactical ticker map from Hyperliquid universe (fallback: hardcoded)."""
    uni_path = Path("/tmp/hl_universe.json")
    if uni_path.exists():
        data = json.loads(uni_path.read_text())
        native = data.get("native", [])
        # All native tickers → themselves (Hyperliquid uses direct names)
        return {a["name"]: a["name"] for a in native}
    # Fallback: top 70 instruments
    return {n: n for n in [
        "BTC","ETH","SOL","HYPE","XRP","DOGE","AVAX","LINK","ADA",
        "NEAR","TON","SUI","APT","ARB","OP","MATIC","DOT","ATOM",
        "WIF","BONK","PEPE","SHIB","SEI","INJ","TIA","RUNE","FET",
        "RNDR","TAO","WLD","STRK","JUP","PYTH","JTO","ENA","PENDLE",
        "LDO","AAVE","UNI","CRV","SNX","GMX","DYDX","MKR","COMP",
        "LTC","BCH","ETC","FIL","ICP","QNT","ZEC","LIT","ZRO",
        "EIGEN","OM","ONDO","BEAM","AKT","GALA","SAND","MANA",
        "AXS","IMX","APE","BLUR","ORDI","SATS","RATS",
    ]}

TACTICAL_TICKER_MAP = _load_tactical_map()


class CryptoEngine(EngineBase):
    ENGINE_NAME = "crypto"
    JOURNAL_DB = "journal_crypto.db"
    TOTAL_CAPITAL = 100_000.0
    CHECK_WINDOW = None

    THESIS_ENTRY = {
        "CRYPTO_ENTRY_ETF_FLOW":    {"thesis": "crypto", "name": "ETF Flows >0.03%",   "ticker": "IBIT", "direction": "long", "allocation_pct": 12.5},
        "CRYPTO_ENTRY_CUSTODY":     {"thesis": "crypto", "name": "Custody Infra Build","ticker": "ETHA", "direction": "long", "allocation_pct": 12.5},
        "CRYPTO_ENTRY_REGULATION":  {"thesis": "crypto", "name": "Regulatory Tailwind","ticker": "IBIT", "direction": "long", "allocation_pct": 6.25},
        "CRYPTO_ENTRY_SOVEREIGN":   {"thesis": "crypto", "name": "Sovereign Adoption", "ticker": "IBIT", "direction": "long", "allocation_pct": 12.5},
        "CRYPTO_ENTRY_LIQUIDITY":   {"thesis": "crypto", "name": "Global Liquidity",   "ticker": "IBIT", "direction": "long", "allocation_pct": 6.25},
    }

    THESIS_EXIT = {
        "CRYPTO_EXIT_RETREAT":      {"thesis": "crypto", "name": "ETF Outflows",       "ticker": "IBIT"},
        "CRYPTO_EXIT_STRUCTURAL":    {"thesis": "crypto", "name": "Structural Break",   "ticker": "IBIT"},
        "CRYPTO_EXIT_REGIME":        {"thesis": "crypto", "name": "Regime Shift",       "ticker": "IBIT"},
        "CRYPTO_EXIT_OVERHEAT":      {"thesis": "crypto", "name": "Overheating",        "ticker": "IBIT"},
        "CRYPTO_EXIT_CORRELATION":   {"thesis": "crypto", "name": "Correlation Break",  "ticker": "IBIT"},
    }

    def __init__(self, execute_mode=False, summary_mode=False):
        # ── Wire gate + risk manager BEFORE super().__init__ (regime needs gate) ──
        self.gate = None  # placeholder — set after conn is available
        self.risk = None
        super().__init__(execute_mode, summary_mode)
        self.gate = Gate(self.conn)
        self.risk = RiskManager(self.conn, cap_alloc=self.TOTAL_CAPITAL * 0.50)

    def _load_regime(self):
        regime = detect_crypto_regime()
        if self.gate:
            self.gate.set_regime(regime["regime"] if regime.get("regime") != "NEUTRAL" else "NEUTRAL")
        if regime.get("regime") != "NEUTRAL":
            return regime
        base = super()._load_regime()
        base["source"] = "synthesizer-fallback"
        if self.gate:
            self.gate.set_regime(base.get("regime", "NEUTRAL"))
        return base

    # ── Signal detection ──
    def detect_signals(self):
        self._detect_etf_signals()

    def _detect_etf_signals(self):
        flows = load_json(ETF_FLOWS_PATH)
        if not flows: return
        sigs = flows.get("signals", {})
        tid = self.ENGINE_NAME
        if sigs.get("E1_firing"): self.log_signal("CRYPTO_ENTRY_ETF_FLOW", True, tid)
        if sigs.get("X1_firing"): self.log_signal("CRYPTO_EXIT_RETREAT", True, tid)

    # ── Invalidation watchdog (Fix #1) ──
    def _check_invalidation(self):
        inv = load_json(INVALIDATION_PATH)
        if inv and inv.get("exit_firing"):
            self.alerts.append("🚨 THESIS EXIT — killing tactical positions")
            for pos in self.open_positions():
                if pos.get("entry_signal", "").startswith("TACTICAL_"):
                    price = get_live_price(pos["symbol"])
                    if price > 0:
                        pnl, sym, direction = self.close_position(pos["id"], price, "CRYPTO_EXIT_STRUCTURAL", "Thesis exit — tactical closed")
                        self.risk.record_result(pnl, pos["id"])
            return True
        return False

    # ── Cross-check: quant + intraday + edge-gen ──
    def _crypto_cross_check(self, ticker):
        qd, idata, edata = load_json(QUANT_PATH), load_json(INTRADAY_PATH), load_json(EDGE_PATH)
        ens = qd.get("ensemble", {}).get("signals", {})
        q_meta = ens.get(ticker, {})
        q_score = abs(q_meta.get("ensemble_score", 0))
        q_dir = q_meta.get("direction", "NEUTRAL")
        q_firing = q_score > 0.06 and q_dir != "NEUTRAL"  # Lowered from 0.25 — expanded universe has lower scores
        if q_firing:
            mc = (qd.get("signals", {}).get(ticker, {})).get("monte-carlo", {})
            # MC gate: required only when ticker HAS MC data AND score >= 0.20
            # New tickers without MC data pass through (don't block on missing data)
            if mc and q_score >= 0.20 and not mc.get("passed", False):
                q_firing = False
        id_dir = next((s.get("direction", "") for s in idata.get("signals", []) if s.get("ticker", "").upper() == ticker.upper()), None)

        edge_bonus = 0.0
        if edata:
            edges = edata.get("recommendations", None)
            if edges is None: edges = edata.get("edges", edata)
            if isinstance(edges, list):
                for item in edges:
                    if isinstance(item, dict) and item.get("ticker", "").upper() == ticker.upper():
                        if item.get("unified_score", item.get("score", 0)) > 35: edge_bonus = 0.5
                        break
            elif isinstance(edges, dict):
                ticker_edge = edges.get(ticker, {})
                if ticker_edge.get("unified_score", ticker_edge.get("score", 0)) > 35: edge_bonus = 0.5

        q_bull, q_bear = q_dir == "BULLISH", q_dir == "BEARISH"
        if q_firing and id_dir:
            return ("CONFIRMED", 1.5 + edge_bonus) if (q_bull and id_dir == "long") or (q_bear and id_dir == "short") else ("CONFLICT", 0.0)
        if q_firing:   return ("QUANT_ONLY", 1.0 + edge_bonus)
        if id_dir:      return ("INTRADAY_ONLY", 0.5 + edge_bonus)
        if edge_bonus > 0: return ("EDGE_ONLY", edge_bonus)
        return ("NONE", 0.0)

    # ── Tactical execution (quant + intraday) ──
    def manage_tactical_positions(self) -> list:
        """Close tactical positions based on time, TP, or SL.
        
        Intraday: max hold 60min, TP +2%, SL -1%
        Quant: max hold 24h, TP +5%, SL -3%
        """
        outputs = []
        now = now_ist()
        
        for pos in self.open_positions():
            sig = pos.get("entry_signal", "")
            if not sig.startswith("TACTICAL_"): continue
            
            entry_time = None
            if pos.get("entry_timestamp"):
                try:
                    entry_time = datetime.fromisoformat(pos["entry_timestamp"].replace("+05:30", "") + "+05:30")
                except: pass
            if not entry_time and pos.get("trade_date"):
                try:
                    entry_time = datetime.strptime(pos["trade_date"], "%Y-%m-%d").replace(tzinfo=IST)
                except: pass
            if not entry_time: continue
            
            age_min = (now - entry_time).total_seconds() / 60
            live_price = get_live_price(pos["symbol"])
            if live_price <= 0: continue
            
            pnl_pct = (live_price - pos["entry_price"]) / pos["entry_price"] * 100
            if pos["direction"] == "short": pnl_pct = -pnl_pct
            
            close_reason = None
            
            # Intraday exits (60 min max, tight TP/SL)
            if "_INTRADAY" in sig or any(t in pos.get("entry_signal","") for t in ["SOL","AVAX","LINK","DOGE","WIF","BONK","PEPE"]):
                if age_min > 60:
                    close_reason = f"intraday max hold ({age_min:.0f}min)"
                elif pnl_pct > 2.0:
                    close_reason = f"intraday TP +{pnl_pct:.1f}%"
                elif pnl_pct < -1.0:
                    close_reason = f"intraday SL {pnl_pct:.1f}%"
            # Quant exits (24h max, wider TP/SL)  
            else:
                if age_min > 1440:  # 24h
                    close_reason = f"quant max hold ({age_min/60:.1f}h)"
                elif pnl_pct > 5.0:
                    close_reason = f"quant TP +{pnl_pct:.1f}%"
                elif pnl_pct < -3.0:
                    close_reason = f"quant SL {pnl_pct:.1f}%"
            
            if close_reason:
                result = self.close_position(pos["id"], live_price, f"TACTICAL_AUTO", close_reason)
                if result:
                    pnl, sym, direction = result
                    self.risk.record_result(pnl, pos["id"])
                    msg = f"🔒 {close_reason}: {direction} {sym} @ ${live_price:.2f} | P&L=${pnl:,.2f}"
                    outputs.append(msg)
                    self.trades_today.append(msg)
        
        return outputs

    def execute_tactical(self):
        outputs = []
        if not self.regime.get("allow_entries", True): return outputs

        # ── RISK GATE: can we trade at all? ──
        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            self.alerts.append(f"⛔ RISK BLOCK: {reason}")
            return outputs

        size_mult = self.regime.get("size_multiplier", 1.0)
        tactical_cap = self.TOTAL_CAPITAL * 0.50

        qd, idata = load_json(QUANT_PATH), load_json(INTRADAY_PATH)
        ens = qd.get("ensemble", {}).get("signals", {})
        all_tickers = set(ens.keys()) | {s.get("ticker", "").upper() for s in idata.get("signals", []) if s.get("ticker")}

        for ticker in all_tickers:
            verdict, x_mult = self._crypto_cross_check(ticker)
            if verdict in ("NONE", "CONFLICT"):
                if verdict == "CONFLICT": self.alerts.append(f"⚠️ CONFLICT {ticker}")
                update_persistence(ticker, "neutral", False)
                continue

            instrument = TACTICAL_TICKER_MAP.get(ticker.upper(), ticker.upper())
            q_meta = ens.get(ticker, {})
            if verdict in ("QUANT_ONLY", "CONFIRMED"):
                direction = "long" if q_meta.get("direction") == "BULLISH" else "short"
            else:
                s = next((s for s in idata.get("signals", []) if s.get("ticker", "").upper() == ticker.upper()), None)
                if not s: continue
                direction = s.get("direction", "long")

            # ── EXECUTION GATE: 5-point check ──
            gate_ok, gate_reason = self.gate.check(ticker, direction)
            if not gate_ok:
                self.alerts.append(f"🚫 GATE {ticker}: {gate_reason}")
                update_persistence(ticker, direction, False)
                continue

            update_persistence(ticker, direction, True)

            if self.has_open_signal(f"TACTICAL_{ticker}", instrument): continue

            pos_size = tactical_cap * 0.10 * x_mult * size_mult
            dep = float(self.conn.execute(
                "SELECT COALESCE(SUM(shares*entry_price),0) FROM trades WHERE status='open' AND entry_signal LIKE 'TACTICAL_%'"
            ).fetchone()[0])
            if dep + pos_size > tactical_cap: continue
            if self.total_deployed() + pos_size > self.TOTAL_CAPITAL * self.HARD_CAP_PCT: continue

            price = get_live_price(instrument)
            if price <= 0: continue

            sig_id = f"TACTICAL_{ticker}"
            trade_id = self.open_position(instrument, direction, price, pos_size / price, sig_id, "crypto")
            self.log_signal(sig_id, True, "crypto")
            self.mark_executed(sig_id)

            msg = f"⚡ {verdict} {ticker}: {direction} {instrument} @ ${price:.2f} = ${pos_size:,.0f}"
            outputs.append(msg)
            self.trades_today.append(msg)
            self.risk.record_result(0.0, trade_id)  # Track entry (PnL = 0 until closed)

        return outputs

    def run(self):
        if self.summary_mode: return []
        outputs = []
        self.detect_signals()
        outputs.extend(self.manage_tactical_positions())  # TP/SL/time exits FIRST
        outputs.extend(self.execute_exits())               # Thesis exits
        outputs.extend(self.execute_entries())             # Thesis entries
        if not self._check_invalidation():
            outputs.extend(self.execute_tactical())        # New tactical entries
        self.take_snapshot()
        outputs.extend(self.alerts)
        return outputs


def main():
    execute, summary = "--execute" in sys.argv, "--summary" in sys.argv
    engine = CryptoEngine(execute_mode=execute, summary_mode=summary)
    outputs = engine.run()
    if summary: print(engine.summary())
    elif outputs:
        print(f"[CRYPTO] {now_ist().strftime('%H:%M IST')}")
        for l in outputs: print(f"  {l}")
        print(f"  ── {engine.summary()}")
    engine.close()

if __name__ == "__main__": main()
