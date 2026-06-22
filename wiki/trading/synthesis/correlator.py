#!/usr/bin/env python3
"""
Cross-Thesis Correlator — v8f
===============================
Finds relationships between signals across all three theses.
Identifies triad alignments, conflicts, and non-obvious linkages.

Usage:
    python3 correlator.py              # Full report → stdout
    python3 correlator.py --summary    # Compact for Telegram

Run: Sunday 9:15 PM IST (after weekly review at 9 PM, before missed audit at 9:30)
"""

import json
import sqlite3
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "paper-trader" / "journal.db"
STATE_PATH = BASE_DIR / "synthesis" / "daily_state.json"
CORRELATION_DIR = BASE_DIR / "synthesis"

# ── Cross-link patterns ──

# Pattern: (thesis_A, thesis_B, condition, interpretation)
CROSS_LINKS = [
    # ── Oil ↔ AI (both confirm AI build-out) ──
    {
        "name": "AI Build-Out Double Confirmation",
        "theses": ["commodity", "ai"],
        "condition": "commodity_bullish AND ai_bullish",
        "interpretation": "Both commodity and AI theses are aligned. The AI build-out bottleneck is confirmed from both the molecules side (energy/metals) and the electrons side (semis/GPUs). Maximum conviction for the AI infrastructure supercycle.",
        "action": "Consider increasing allocation to BOTH theses. They validate each other.",
        "severity": "BULLISH",
    },
    {
        "name": "Oil Breakout without AI Capex",
        "theses": ["commodity", "ai"],
        "condition": "commodity_bullish AND ai_neutral",
        "interpretation": "Commodity thesis is bullish (energy demand) but AI thesis shows no capex acceleration. The physical bottleneck may be supply-driven (Hormuz, underinvestment) rather than AI demand-driven. Adjust thesis weights.",
        "action": "Favor commodity thesis over AI thesis. AI capex not confirming.",
        "severity": "INFO",
    },
    {
        "name": "AI Capex without Energy Confirmation",
        "theses": ["ai", "commodity"],
        "condition": "ai_bullish AND commodity_neutral",
        "interpretation": "AI infrastructure build-out accelerating but energy prices not responding. Either AI efficiency is reducing energy demand (Jevons paradox risk) or energy markets haven't priced it yet. Watch Brent for catch-up trade.",
        "action": "Favor AI thesis. Watch Brent for lagging confirmation. Potential commodity entry on Brent breakout.",
        "severity": "INFO",
    },

    # ── Gold ↔ AI ──
    {
        "name": "Risk-On/Risk-Off Conflict",
        "theses": ["commodity", "ai"],
        "condition": "gold_short_active AND ai_bullish",
        "interpretation": "Gold short (E4S) is active (DXY rising, real rates rising) while AI thesis is bullish. Rising rates hurt growth stocks — this is a macro conflict. One thesis is likely wrong about the rate direction.",
        "action": "Review DXY and real rates. If rates are indeed rising, reduce AI thesis exposure. If rates outlook is dovish, cover E4S gold short.",
        "severity": "WARNING",
    },

    # ── Crypto ↔ Commodity ──
    {
        "name": "Inflation Hedge Alignment",
        "theses": ["crypto", "commodity"],
        "condition": "crypto_bullish AND commodity_bullish",
        "interpretation": "Both crypto and commodity theses are bullish — classic inflation-hedge alignment. BTC and energy both benefit from USD debasement and real asset preference. Strongest macro convergence signal.",
        "action": "Maximum conviction for real assets. Size up on both theses. Correlation benefit — diversified inflation exposure.",
        "severity": "BULLISH",
    },
    {
        "name": "Crypto Decoupling from Commodities",
        "theses": ["crypto", "commodity"],
        "condition": "crypto_bullish AND commodity_bearish",
        "interpretation": "Crypto bullish while commodities bearish — suggests crypto is trading on its own fundamentals (on-chain, ETF flows) rather than as an inflation hedge. BTC/SPY correlation likely low. Crypto-native edge is active.",
        "action": "Trust crypto-native signals over macro. Commodity thesis may be early/late. Monitor for convergence.",
        "severity": "INFO",
    },

    # ── Three-Thesis Triad ──
    {
        "name": "Triple Bullish Convergence",
        "theses": ["commodity", "ai", "crypto"],
        "condition": "commodity_bullish AND ai_bullish AND crypto_bullish",
        "interpretation": "ALL THREE theses are simultaneously bullish. This is rare — maximum risk-on alignment. AI build-out demand confirmed from both molecule and electron sides, plus crypto accumulation. This is the strongest possible signal from the platform.",
        "action": "Maximum deployment. All three theses in alignment. Consider increasing total allocation if under-deployed.",
        "severity": "STRONG_BULLISH",
    },
    {
        "name": "Triple Bearish Divergence",
        "theses": ["commodity", "ai", "crypto"],
        "condition": "commodity_bearish AND ai_bearish AND crypto_bearish",
        "interpretation": "ALL THREE theses are bearish simultaneously. Systemic risk-off. DXY likely surging, VIX elevated, real rates rising. This is the strongest risk-off signal from the platform.",
        "action": "Reduce all positions. Cash is the position. Wait for thesis alignment to shift.",
        "severity": "STRONG_BEARISH",
    },

    # ── DXY Impact Chain ──
    {
        "name": "DXY Headwind Across Theses",
        "theses": ["commodity", "ai", "crypto"],
        "condition": "dxy_rising",
        "interpretation": "DXY rising — headwind for commodities (USD-denominated), AI (growth stocks hurt by strong USD), and crypto (inverse correlation). If DXY breaks above 100, all three theses face significant headwinds.",
        "action": "Reduce size across all theses. Monitor DXY 100 level as key threshold.",
        "severity": "WARNING",
    },
]


# ── Database ──

class CorrelatorDB:
    def __init__(self, db_path=str(DB_PATH)):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_active_signals(self) -> Dict[str, List[str]]:
        """Get active signals grouped by thesis."""
        # Check recent signal_log for triggered signals
        cutoff = (datetime.now().strftime("%Y-%m-%d"))
        rows = self.conn.execute(
            "SELECT signal_id, thesis_id FROM signal_log "
            "WHERE triggered = 1 AND check_date >= ? "
            "ORDER BY check_date DESC",
            (cutoff,)
        ).fetchall()

        active = {"commodity": [], "ai": [], "crypto": []}
        for r in rows:
            thesis = r["thesis_id"] or _infer_thesis(r["signal_id"])
            if thesis in active and r["signal_id"] not in active[thesis]:
                active[thesis].append(r["signal_id"])
        return active

    def get_open_positions(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE status = 'open'"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()


def _infer_thesis(signal_id: str) -> str:
    if signal_id.startswith("AI_"): return "ai"
    if signal_id.startswith("CRYPTO_"): return "crypto"
    return "commodity"


# ── Analyzer ──

class CrossThesisCorrelator:
    def __init__(self, db: CorrelatorDB):
        self.db = db

    @staticmethod
    def _thesis_bias(active_signals: List[str], thesis: str) -> str:
        """Determine thesis bias from active signals."""
        if not active_signals:
            return "NEUTRAL"
        # Entry signals active = bullish. Exit signals active = bearish.
        has_entry = any(not s.startswith(("X", "AI_X", "CRYPTO_X")) for s in active_signals)
        has_exit = any(s.startswith(("X", "AI_X", "CRYPTO_X")) for s in active_signals)
        if has_entry and not has_exit:
            return "BULLISH"
        elif has_exit and not has_entry:
            return "BEARISH"
        elif has_entry and has_exit:
            return "MIXED"
        return "NEUTRAL"

    def analyze(self) -> dict:
        """Run cross-thesis correlation analysis."""
        active = self.db.get_active_signals()
        positions = self.db.get_open_positions()

        # Determine biases
        biases = {
            t: self._thesis_bias(active.get(t, []), t)
            for t in ["commodity", "ai", "crypto"]
        }

        # Load synthesizer state
        syn_state = {}
        if STATE_PATH.exists():
            syn_state = json.loads(STATE_PATH.read_text())

        regime = syn_state.get("market_regime", {}).get("primary", "UNKNOWN")
        composite = syn_state.get("composite_confluence_score", {}).get("value", 0)
        dxy = 100
        dxy_direction = "flat"
        if STATE_PATH.exists():
            # Try reading market data
            market_path = Path("/tmp/live_market_data.json")
            if market_path.exists():
                mdata = json.loads(market_path.read_text())
                dxy = mdata.get("dxy", 100)
                if mdata.get("dxy_rising"):
                    dxy_direction = "rising"
                elif mdata.get("dxy_falling"):
                    dxy_direction = "falling"

        # Evaluate cross-links
        links_fired = []
        for link in CROSS_LINKS:
            condition = link["condition"]
            fired = False

            # Parse conditions
            if "commodity_bullish" in condition:
                if biases["commodity"] != "BULLISH":
                    continue
            if "commodity_bearish" in condition:
                if biases["commodity"] != "BEARISH":
                    continue
            if "commodity_neutral" in condition:
                if biases["commodity"] not in ("NEUTRAL",):
                    continue
            if "ai_bullish" in condition:
                if biases["ai"] != "BULLISH":
                    continue
            if "ai_bearish" in condition:
                if biases["ai"] != "BEARISH":
                    continue
            if "ai_neutral" in condition:
                if biases["ai"] not in ("NEUTRAL",):
                    continue
            if "crypto_bullish" in condition:
                if biases["crypto"] != "BULLISH":
                    continue
            if "crypto_bearish" in condition:
                if biases["crypto"] != "BEARISH":
                    continue
            if "gold_short_active" in condition:
                if "E4S" not in active.get("commodity", []):
                    continue
            if "dxy_rising" in condition:
                if dxy_direction != "rising":
                    continue

            links_fired.append(link)

        return {
            "biases": biases,
            "active_signals": active,
            "open_positions": positions,
            "regime": regime,
            "composite_score": composite,
            "dxy": dxy,
            "dxy_direction": dxy_direction,
            "links_fired": links_fired,
            "triad": self._triad_analysis(biases),
        }

    def _triad_analysis(self, biases: Dict[str, str]) -> str:
        """Summarize the three-thesis alignment."""
        bullish = sum(1 for b in biases.values() if b == "BULLISH")
        bearish = sum(1 for b in biases.values() if b == "BEARISH")
        neutral = sum(1 for b in biases.values() if b == "NEUTRAL")

        if bullish == 3:
            return "🟢🟢🟢 TRIPLE BULLISH — Maximum risk-on alignment"
        elif bearish == 3:
            return "🔴🔴🔴 TRIPLE BEARISH — Systemic risk-off"
        elif bullish == 2:
            return "🟢🟢⚫ 2 bullish, 1 neutral — Favorable, monitor the neutral"
        elif bearish == 2:
            return "🔴🔴⚫ 2 bearish, 1 neutral — Defensive, reduce risk"
        elif bullish == 1 and bearish == 1:
            return "🟢🔴⚫ Mixed — Conflicting signals, reduce size"
        else:
            return "⚫⚫⚫ All neutral — No strong directional bias"

    def summary(self, report: dict) -> str:
        """Telegram-ready summary."""
        lines = ["[CORRELATION] #cross-thesis", ""]

        # Triad
        lines.append(f"**Triad:** {report['triad']}")
        lines.append("")

        # Biases
        bias_icons = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚫", "MIXED": "🟡"}
        lines.append("**Thesis Biases:**")
        for t, b in report["biases"].items():
            active_sigs = report["active_signals"].get(t, [])
            sig_str = f" ({', '.join(active_sigs)})" if active_sigs else ""
            lines.append(f"  {bias_icons.get(b, '⚫')} {t}: {b}{sig_str}")

        # Regime
        lines.append("")
        lines.append(f"🌍 Regime: **{report['regime']}** | DXY: {report['dxy']} ({report['dxy_direction']})")

        # Cross-links fired
        links = report["links_fired"]
        if links:
            lines.append("")
            lines.append("**Cross-Links Fired:**")
            for link in links:
                sev_icon = {"BULLISH": "🟢", "STRONG_BULLISH": "🟢🟢", "WARNING": "⚠️",
                           "INFO": "💡", "BEARISH": "🔴", "STRONG_BEARISH": "🔴🔴"}.get(link["severity"], "💡")
                lines.append(f"  {sev_icon} **{link['name']}**")
                lines.append(f"     {link['action']}")
        else:
            lines.append("")
            lines.append("💡 No cross-thesis links firing. Theses are independent this week.")

        return "\n".join(lines)

    def full_report(self, report: dict) -> str:
        """Full report for vault."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M IST")
        lines = [
            "# Cross-Thesis Correlation Report",
            f"> {now}",
            "",
            f"## Triad: {report['triad']}",
            "",
            "## Thesis Biases",
        ]
        for t, b in report["biases"].items():
            lines.append(f"- **{t}**: {b}")

        lines.extend([
            "",
            f"## Regime: {report['regime']} | Composite: {report['composite_score']:+d}",
            f"DXY: {report['dxy']} ({report['dxy_direction']})",
            "",
            "## Active Signals",
        ])
        for t, sigs in report["active_signals"].items():
            if sigs:
                lines.append(f"- {t}: {', '.join(sigs)}")
            else:
                lines.append(f"- {t}: none")

        lines.extend(["", "## Cross-Links Fired"])
        for link in report["links_fired"]:
            lines.append(f"### {link['name']} ({link['severity']})")
            lines.append(link["interpretation"])
            lines.append(f"**Action:** {link['action']}")
            lines.append("")

        lines.append("---")
        lines.append("*Generated by synthesis/correlator.py (v8f)*")
        return "\n".join(lines)


# ── Main ──

def main():
    summary_only = "--summary" in sys.argv

    db = CorrelatorDB()
    correlator = CrossThesisCorrelator(db)

    report = correlator.analyze()

    if summary_only:
        print(correlator.summary(report))
    else:
        print(correlator.full_report(report))

    db.close()


if __name__ == "__main__":
    main()
