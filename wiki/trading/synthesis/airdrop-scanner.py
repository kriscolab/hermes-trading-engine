#!/usr/bin/env python3
"""
Airdrop Scanner — v8g
=======================
Scores and ranks airdrop opportunities. Scrapes aggregator sites,
applies 5-dimension scoring, outputs daily ranking.

Usage:
    python3 airdrop-scanner.py              # Full report
    python3 airdrop-scanner.py --summary    # Telegram-ready digest
    python3 airdrop-scanner.py --top 5      # Top 5 only

Data sources: DefiLlama, Airdrops.io (free, no key)
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent
STATE_PATH = BASE_DIR / "airdrop_state.json"
RANKINGS_DIR = BASE_DIR / "airdrop_rankings"
RANKINGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Scoring Weights ──
WEIGHTS = {
    "likelihood": 30,
    "est_value": 25,
    "time_to_claim": 15,
    "team_backers": 15,
    "rug_risk_inverse": 15,
}


# ── Scoring Engine ──

class AirdropScorer:
    """Score a single airdrop opportunity."""

    @staticmethod
    def score_likelihood(status: str) -> int:
        """Score based on confirmation status."""
        return {"confirmed": 30, "likely": 20, "rumored": 10, "speculative": 5}.get(
            status.lower(), 5
        )

    @staticmethod
    def score_value(tvl_m: float = 0, funding_m: float = 0) -> int:
        """Score based on protocol size."""
        score = 0
        if tvl_m > 500 or funding_m > 50:
            score = 25
        elif tvl_m > 100 or funding_m > 20:
            score = 18
        elif tvl_m > 50 or funding_m > 10:
            score = 12
        elif tvl_m > 10 or funding_m > 2:
            score = 8
        else:
            score = 4
        return min(score, 25)

    @staticmethod
    def score_time(days_until: Optional[int] = None) -> int:
        """Score based on time until airdrop. Shorter = better."""
        if days_until is None:
            return 7  # unknown
        if days_until <= 30:
            return 15
        elif days_until <= 90:
            return 10
        elif days_until <= 180:
            return 5
        else:
            return 2

    @staticmethod
    def score_team(team_public: bool = False, vc_tier: str = "none") -> int:
        """Score based on team quality."""
        score = 0
        if team_public:
            score += 7
        if vc_tier == "tier1":
            score += 8
        elif vc_tier == "tier2":
            score += 4
        elif vc_tier == "tier3":
            score += 2
        return min(score, 15)

    @staticmethod
    def score_rug_risk(audits: int = 0, age_months: int = 0) -> int:
        """Score based on safety. Higher audits + older = safer."""
        score = 0
        if audits >= 3:
            score += 8
        elif audits >= 1:
            score += 4
        if age_months >= 12:
            score += 7
        elif age_months >= 6:
            score += 4
        elif age_months >= 3:
            score += 2
        return min(score, 15)

    @classmethod
    def score_full(cls, opp: Dict) -> Dict:
        """Score a full opportunity dict and return with scores."""
        scores = {
            "likelihood": cls.score_likelihood(opp.get("status", "speculative")),
            "est_value": cls.score_value(
                opp.get("tvl_m", 0), opp.get("funding_m", 0)
            ),
            "time_to_claim": cls.score_time(opp.get("days_until")),
            "team_backers": cls.score_team(
                opp.get("team_public", False), opp.get("vc_tier", "none")
            ),
            "rug_risk_inverse": cls.score_rug_risk(
                opp.get("audits", 0), opp.get("age_months", 0)
            ),
        }
        total = sum(scores.values())
        tier = (
            "S" if total >= 80 else
            "A" if total >= 60 else
            "B" if total >= 40 else
            "C" if total >= 20 else
            "D"
        )
        return {**opp, "scores": scores, "total_score": total, "tier": tier}


# ── Data Source (Placeholder — uses static data until web scraping is wired) ──

# These are example entries. In production, this would be scraped from
# DefiLlama / Airdrops.io APIs or web pages.

SAMPLE_OPPORTUNITIES = [
    {
        "name": "LayerZero",
        "protocol": "LayerZero",
        "status": "confirmed",
        "tvl_m": 0,
        "funding_m": 293,
        "days_until": 30,
        "team_public": True,
        "vc_tier": "tier1",
        "audits": 3,
        "age_months": 30,
        "chain": "Multi-chain",
        "notes": "Cross-chain interoperability protocol. $293M raised. Confirmed airdrop snapshot taken.",
    },
    {
        "name": "zkSync",
        "protocol": "zkSync",
        "status": "confirmed",
        "tvl_m": 800,
        "funding_m": 458,
        "days_until": 45,
        "team_public": True,
        "vc_tier": "tier1",
        "audits": 4,
        "age_months": 24,
        "chain": "Ethereum L2",
        "notes": "ZK-rollup L2. $458M raised. Token generation event announced.",
    },
    {
        "name": "StarkNet",
        "protocol": "StarkNet",
        "status": "likely",
        "tvl_m": 600,
        "funding_m": 282,
        "days_until": 60,
        "team_public": True,
        "vc_tier": "tier1",
        "audits": 3,
        "age_months": 36,
        "chain": "Ethereum L2",
        "notes": "ZK-STARK L2. STRK token launched, airdrop rounds continue.",
    },
    {
        "name": "EigenLayer",
        "protocol": "EigenLayer",
        "status": "likely",
        "tvl_m": 12000,
        "funding_m": 164,
        "days_until": 90,
        "team_public": True,
        "vc_tier": "tier1",
        "audits": 5,
        "age_months": 18,
        "chain": "Ethereum",
        "notes": "Restaking protocol. $12B TVL. Multiple airdrop seasons expected.",
    },
    {
        "name": "Scroll",
        "protocol": "Scroll",
        "status": "rumored",
        "tvl_m": 400,
        "funding_m": 80,
        "days_until": 120,
        "team_public": True,
        "vc_tier": "tier2",
        "audits": 2,
        "age_months": 18,
        "chain": "Ethereum L2",
        "notes": "ZK-EVM L2. Airdrop rumored but not confirmed. Farming campaigns active.",
    },
    {
        "name": "Metamask",
        "protocol": "Metamask",
        "status": "speculative",
        "tvl_m": 0,
        "funding_m": 0,
        "days_until": None,
        "team_public": True,
        "vc_tier": "tier1",
        "audits": 0,
        "age_months": 84,
        "chain": "Multi-chain",
        "notes": "Speculative. No confirmation from Consensys. Largest wallet — if it happens, it's huge.",
    },
    {
        "name": "Hyperliquid",
        "protocol": "Hyperliquid",
        "status": "likely",
        "tvl_m": 2000,
        "funding_m": 0,
        "days_until": 30,
        "team_public": False,
        "vc_tier": "none",
        "audits": 1,
        "age_months": 18,
        "chain": "Arbitrum",
        "notes": "Perp DEX. $2B TVL. Points program active. No VC backing — fully community-owned.",
    },
    {
        "name": "Berachain",
        "protocol": "Berachain",
        "status": "confirmed",
        "tvl_m": 0,
        "funding_m": 142,
        "days_until": 60,
        "team_public": True,
        "vc_tier": "tier1",
        "audits": 2,
        "age_months": 24,
        "chain": "Cosmos",
        "notes": "L1 with Proof-of-Liquidity. $142M raised. Testnet active.",
    },
]


# ── Data Source ──

class LiveAirdropFetcher:
    """Fetch real airdrop data from web sources."""

    @staticmethod
    def fetch_defillama() -> List[Dict]:
        """Scrape DefiLlama airdrops page. Returns list of opportunities."""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        opportunities = []
        try:
            # DefiLlama doesn't have a public API for airdrops — scrape the page
            resp = requests.get(
                "https://defillama.com/airdrops",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            # Look for airdrop cards/rows — structure varies, try common patterns
            cards = soup.select("[class*='airdrop'], [class*='card'], [class*='row']")

            for card in cards[:10]:
                name_el = card.select_one("h2, h3, [class*='name'], [class*='title']")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                notes = card.get_text(strip=True)[:200]
                opportunities.append({
                    "name": name,
                    "protocol": name,
                    "status": "rumored",
                    "tvl_m": 0,
                    "funding_m": 0,
                    "days_until": None,
                    "team_public": False,
                    "vc_tier": "none",
                    "audits": 0,
                    "age_months": 0,
                    "chain": "Unknown",
                    "notes": notes,
                })
        except Exception as e:
            print(f"  ⚠ DefiLlama scrape failed: {e}", file=sys.stderr)

        return opportunities

    @staticmethod
    def fetch_all() -> List[Dict]:
        """Fetch from all available sources."""
        opportunities = LiveAirdropFetcher.fetch_defillama()
        return opportunities if opportunities else []


# ── Scanner ──

class AirdropScanner:
    """Main scanner that aggregates, scores, and ranks opportunities."""

    def __init__(self, use_live: bool = False):
        self.use_live = use_live
        self.opportunities = []

    def fetch(self) -> List[Dict]:
        """Fetch opportunities from data sources."""
        if self.use_live:
            live = LiveAirdropFetcher.fetch_all()
            if live:
                self.opportunities = live
                return self.opportunities

        # Fallback: curated sample data
        self.opportunities = SAMPLE_OPPORTUNITIES[:]
        return self.opportunities

    def score_all(self) -> List[Dict]:
        """Score all opportunities and sort by total score descending."""
        scored = [AirdropScorer.score_full(opp) for opp in self.opportunities]
        scored.sort(key=lambda x: x["total_score"], reverse=True)
        return scored

    def top_n(self, n: int = 5) -> List[Dict]:
        """Return top N opportunities."""
        return self.score_all()[:n]

    def summary(self, limit: int = 5) -> str:
        """Telegram-ready summary."""
        ranked = self.top_n(limit)
        if not ranked:
            return "[AIRDROP] #scanner\n\nNo opportunities found."

        lines = ["[AIRDROP] #daily-ranking", ""]
        tier_icons = {"S": "🏆", "A": "⭐", "B": "👍", "C": "👀", "D": "🗑"}

        for i, opp in enumerate(ranked, 1):
            icon = tier_icons.get(opp["tier"], "•")
            lines.append(
                f"{i}. {icon} **{opp['name']}** [{opp['tier']}-Tier] "
                f"— Score: {opp['total_score']}/100"
            )
            lines.append(f"   {opp['status'].upper()} | {opp['chain']} | ~{opp.get('days_until', '?')}d")
            lines.append(f"   Value: {opp['scores']['est_value']}/25 | "
                        f"Safety: {opp['scores']['rug_risk_inverse']}/15 | "
                        f"Team: {opp['scores']['team_backers']}/15")
            lines.append(f"   {opp['notes'][:100]}")
            lines.append("")

        lines.append("💡 **Today's pick:** "
                    f"{ranked[0]['name']} ({ranked[0]['tier']}-Tier, {ranked[0]['total_score']}/100)")
        lines.append(f"   {ranked[0]['notes'][:120]}")

        return "\n".join(lines)


# ── Main ──

def main():
    summary_only = "--summary" in sys.argv
    use_live = "--live" in sys.argv
    top_n = 5
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            top_n = int(sys.argv[i + 1])

    scanner = AirdropScanner(use_live=use_live)
    scanner.fetch()

    if summary_only:
        output = scanner.summary(limit=top_n)
        print(output)
    else:
        ranked = scanner.top_n(top_n)
        lines = []
        for i, opp in enumerate(ranked, 1):
            lines.append(f"{i}. {opp['name']} [{opp['tier']}] — {opp['total_score']}/100")
            lines.append(f"   Likelihood: {opp['scores']['likelihood']}/30 | "
                         f"Value: {opp['scores']['est_value']}/25 | "
                         f"Time: {opp['scores']['time_to_claim']}/15")
            lines.append(f"   Team: {opp['scores']['team_backers']}/15 | "
                         f"Safety: {opp['scores']['rug_risk_inverse']}/15")
            lines.append(f"   {opp['notes']}")
            lines.append("")
        output = "\n".join(lines)
        print(output)
    
    # Write to rankings directory
    today = datetime.now().strftime("%Y-%m-%d")
    RANKINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RANKINGS_DIR / f"{today}.json"
    json.dump({
        "date": today,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "live_data": use_live,
        "top_n": top_n,
        "rankings": [{"rank": i+1, **opp} for i, opp in enumerate(scanner.top_n(top_n))],
    }, out_path.open("w"), indent=2)
    print(f"\n📁 Rankings saved → {out_path}")


if __name__ == "__main__":
    main()
