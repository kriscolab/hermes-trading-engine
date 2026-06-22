#!/usr/bin/env python3
"""
Hermes Strategy Synthesizer v2.0 — Programmatic, no LLM dependency
==================================================================
Reads all data sources → computes market regime, confluence scores,
risk factors, and per-thesis recommendations → writes daily_state.json

Inputs:
  /tmp/live_market_data.json    — commodity: brent, gold, dxy, vix
  /tmp/crypto_module_data.json  — crypto: confluence, prices, funding
  /tmp/quant_signals.json       — quant: edge scores, regimes
  journal.db                    — positions, signal log
  /tmp/portfolio_prices.json    — mark-to-market prices

Output:
  synthesis/daily_state.json    — structured market state with recommendations
"""

import json, sqlite3, sys, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))
TRADING_DIR = Path(__file__).resolve().parent.parent
DB_PATH = TRADING_DIR / "paper-trader" / "journal.db"
STATE_PATH = TRADING_DIR / "synthesis" / "daily_state.json"
ARCHIVE_DIR = TRADING_DIR / "synthesis" / "archive"

MARKET_PATH = Path("/tmp/live_market_data.json")
CRYPTO_PATH = Path("/tmp/crypto_module_data.json")
QUANT_PATH = Path("/tmp/quant_signals.json")
PRICES_PATH = Path("/tmp/portfolio_prices.json")
AI_TRACKER_PATH = Path("/tmp/ai_tracker_prices.json")
INTRADAY_PATH = Path("/tmp/intraday_signals.json")

# ── Shared config ──
try:
    from delivery.trading_config import REGIME_THRESHOLDS, CRYPTO_TICKERS
except ImportError:
    REGIME_THRESHOLDS = {"NEUTRAL": {"t1": 0.08, "t2": 0.15, "sl": -0.12}}
    CRYPTO_TICKERS = ["BTC", "ETH", "SOL", "LINK", "AVAX", "ADA", "XRP", "DOGE"]

# ══════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════

def load_json(path: Path) -> dict:
    if path.exists():
        try: return json.loads(path.read_text())
        except Exception: pass
    return {}

def load_journal():
    """Return positions, latest signals, and thesis states."""
    conn = sqlite3.connect(str(DB_PATH)); conn.row_factory = sqlite3.Row
    
    positions = [dict(r) for r in conn.execute(
        "SELECT symbol, direction, entry_price, shares, trade_date, entry_signal FROM trades WHERE status='open'").fetchall()]
    
    # Latest signal per thesis
    thesis_state = {}
    for thesis, probe in [("commodity","E1"),("crypto","CRYPTO_E1"),("ai","AI_E1")]:
        row = conn.execute(f"SELECT check_date FROM signal_log WHERE signal_id='{probe}' ORDER BY check_date DESC LIMIT 1").fetchone()
        if row:
            sig_ids = {"commodity": ["E1","E2","E3","E4S","E4L"],
                       "crypto": ["CRYPTO_E1","CRYPTO_E2","CRYPTO_E3","CRYPTO_E4"],
                       "ai": ["AI_E1","AI_E2","AI_E3","AI_E4","AI_E5"]}[thesis]
            placeholders = ",".join(f"'{s}'" for s in sig_ids)
            firing = conn.execute(
                f"SELECT signal_id FROM signal_log WHERE check_date='{row['check_date']}' AND triggered=1 AND signal_id IN ({placeholders})").fetchall()
            thesis_state[thesis] = {"last_check": row["check_date"], "firing": [r["signal_id"] for r in firing]}
    
    conn.close()
    
    # Compute deployed per thesis
    deployed = {"commodity": 0, "crypto": 0, "ai": 0}
    for p in positions:
        sig = p["entry_signal"]
        val = p["entry_price"] * p["shares"]
        if sig.startswith("CRYPTO"): deployed["crypto"] += val
        elif sig.startswith("AI"): deployed["ai"] += val
        else: deployed["commodity"] += val
    
    total = sum(deployed.values())
    
    return positions, thesis_state, deployed, total


# ══════════════════════════════════════════════════════════════════════
# MARKET REGIME DETECTION
# ══════════════════════════════════════════════════════════════════════

def detect_regime(market: dict, quant: dict) -> str:
    """Determine overall market regime from available data."""
    vix = market.get("vix", 20)
    dxy_rising = market.get("dxy_rising", False)
    dxy_falling = market.get("dxy_falling", False)
    
    # Get ML regime consensus from quant signals — full 8-ticker universe
    regimes = []
    for ticker in CRYPTO_TICKERS:
        ts = quant.get("signals",{}).get(ticker,{})
        ml = ts.get("ml-signals",{})
        r = ml.get("dominant_regime","")
        if r: regimes.append(r)
    
    # Map ML regime consensus to schema-compliant enums
    ML_TO_SCHEMA = {
        "TRENDING": "RISK_ON",
        "BREAKOUT": "RISK_ON",
        "MEAN_REVERTING": "CAUTIOUS",
        "CHOPPY": "CAUTIOUS",
        "HIGH_VOL": "RISK_OFF",
        "LOW_VOL": "NEUTRAL",
    }
    regime_consensus = max(set(regimes), key=regimes.count) if regimes else "UNKNOWN"
    
    # Use shared config thresholds where possible, fall back to hardcoded
    if vix > 25:
        return "RISK_OFF"
    elif vix < 15 and dxy_falling:
        return "RISK_ON"
    elif dxy_rising:
        return "CAUTIOUS"
    elif regime_consensus in ("CHOPPY","LOW_VOL"):
        return "NEUTRAL"
    else:
        result = ML_TO_SCHEMA.get(regime_consensus, "NEUTRAL") if regime_consensus != "UNKNOWN" else "NEUTRAL"
        return result


# ══════════════════════════════════════════════════════════════════════
# COMPOSITE CONFLUENCE SCORE
# ══════════════════════════════════════════════════════════════════════

def compute_confluence(market: dict, crypto: dict, thesis_state: dict) -> dict:
    """Compute composite confluence score (-5 to +5) across all theses."""
    
    thesis_scores = {}
    
    # Commodity thesis
    brent = market.get("brent_close") or 0
    brent_sma = market.get("brent_50sma")
    if brent_sma is None:
        brent_sma = brent * 0.92 if brent > 0 else 100  # fallback: estimate SMA
    gold = market.get("gold") or 0
    fcf = market.get("mun7_fcf_yield", 0)
    dxy_rising = market.get("dxy_rising", False)
    dxy_falling = market.get("dxy_falling", False)
    
    commodity_score = 0
    if brent > brent_sma: commodity_score += 1  # Brent above SMA = bullish
    if fcf > 0.12: commodity_score += 1          # Strong FCF supports thesis
    if dxy_falling: commodity_score += 1          # Weakening USD = commodity tailwind
    if dxy_rising: commodity_score -= 1           # Strengthening USD = headwind
    if gold < 3000: commodity_score += 1          # Gold below structural value zone
    if brent > 110: commodity_score += 1          # Breakout territory
    commodity_score = max(-2, min(2, commodity_score))
    thesis_scores["commodity"] = commodity_score
    
    # Crypto thesis
    conc = crypto.get("confluence", {})
    crypto_conc = conc.get("score", 0)
    crypto_score = 0
    if crypto_conc >= 4: crypto_score = 2
    elif crypto_conc >= 3: crypto_score = 1
    elif crypto_conc <= 1: crypto_score = -1
    thesis_scores["crypto"] = crypto_score
    
    # AI thesis — check if any signals are firing
    ai_firing = thesis_state.get("ai", {}).get("firing", [])
    ai_score = 0
    if len(ai_firing) >= 2: ai_score = 2
    elif len(ai_firing) >= 1: ai_score = 1
    thesis_scores["ai"] = ai_score
    
    composite = sum(thesis_scores.values())
    composite = max(-5, min(5, composite))
    
    interpretation = "NEUTRAL"
    if composite >= 3: interpretation = "Bullish confluence — multiple theses aligned"
    elif composite >= 1: interpretation = "Slight bullish bias"
    elif composite <= -3: interpretation = "Bearish confluence — headwinds across theses"
    elif composite <= -1: interpretation = "Slight bearish bias"
    
    return {
        "value": composite,
        "range": [-5, 5],
        "interpretation": interpretation,
        "thesis_scores": thesis_scores,
    }


# ══════════════════════════════════════════════════════════════════════
# RISK FACTORS
# ══════════════════════════════════════════════════════════════════════

def compute_risks(market: dict) -> dict:
    """Identify primary risk factors."""
    vix = market.get("vix", 20)
    dxy_rising = market.get("dxy_rising", False)
    dxy = market.get("dxy", 100)
    
    if dxy_rising and dxy > 100:
        return {
            "factor": "DXY strengthening above 100",
            "severity": "HIGH",
            "description": f"DXY at {dxy} and rising — USD strength pressures all commodity and crypto positions. Commodity thesis depends on weakening dollar.",
            "affected_theses": ["commodity", "crypto"],
        }
    elif vix > 25:
        return {
            "factor": "Elevated volatility (VIX > 25)",
            "severity": "MEDIUM",
            "description": f"VIX at {vix} — risk-off environment. Reduce position sizes, widen stops.",
            "affected_theses": ["commodity", "crypto", "ai"],
        }
    elif not dxy_rising and not market.get("dxy_falling", False):
        return {
            "factor": "DXY direction uncertainty",
            "severity": "MEDIUM",
            "description": f"DXY flat at {dxy} — no macro direction. Wait for breakout above 100 or breakdown below 98 before sizing up.",
            "affected_theses": ["commodity"],
        }
    else:
        return {
            "factor": "No acute risk factor identified",
            "severity": "LOW",
            "description": "VIX moderate, DXY not threatening. Standard risk management applies.",
            "affected_theses": [],
        }


# ══════════════════════════════════════════════════════════════════════
# THESIS RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════

def thesis_recommendation(thesis: str, market: dict, crypto: dict, 
                          quant: dict, thesis_state: dict,
                          positions: list, deployed: dict) -> dict:
    """Generate a recommendation for a single thesis."""
    
    if thesis == "commodity":
        brent = market.get("brent_close", 0)
        brent_sma = market.get("brent_50sma", 100)
        gold = market.get("gold", 0)
        dxy_rising = market.get("dxy_rising", False)
        dxy_falling = market.get("dxy_falling", False)
        vix = market.get("vix", 20)
        
        firing = thesis_state.get("commodity", {}).get("firing", [])
        
        if "E2" in firing:
            bias = "BULLISH"
            action = f"Brent ${brent:.0f} above 50-SMA ${brent_sma:.0f}. E2 breakout active. Hold XLE long. Monitor DXY."
        elif dxy_falling and brent > brent_sma:
            bias = "SLIGHTLY_BULLISH"
            action = "DXY falling supports commodity thesis. Brent above SMA. Watch for E2 trigger (brent > $110)."
        elif dxy_rising:
            bias = "CAUTIOUS"
            action = "DXY rising — headwind for commodities. Tighten stops. No new entries until DXY reverses."
        else:
            bias = "NEUTRAL"
            action = "DXY flat, Brent range-bound. Hold existing positions. Wait for directional signal."
        
        # Active positions
        active = []
        for p in positions:
            if p["entry_signal"] in ("E1","E2","E3","E4S","E4L"):
                active.append({
                    "signal": p["entry_signal"], "symbol": p["symbol"],
                    "direction": p["direction"].upper(),
                    "entry_price": p["entry_price"], "shares": p["shares"],
                    "entered": str(p.get("trade_date","?"))[:10],
                    "status": "ACTIVE",
                })
        
        return {
            "bias": bias, "action": action,
            "next_signal_watch": "E2 (Brent > $110) or E4S (Gold > $3,800 + DXY rising)",
            "size_adjustment": 1.0 if bias == "BULLISH" else 0.5,
            "active_positions": active,
            "notes": f"Brent ${brent:.0f} vs SMA ${brent_sma:.0f}. Gold ${gold:,.0f}. VIX {vix}. DXY {'↑' if dxy_rising else '↓' if dxy_falling else '→'}.",
        }
    
    elif thesis == "crypto":
        conc = crypto.get("confluence", {})
        crypto_conc = conc.get("score", 0)
        btc = crypto.get("prices", {}).get("btc", 0)
        fg = crypto.get("sentiment", {}).get("fear_greed", {}).get("value", 50)
        funding = crypto.get("derivatives", {}).get("btc_funding", {}).get("funding_rate_pct", 0)
        
        firing = thesis_state.get("crypto", {}).get("firing", [])
        
        if "CRYPTO_E1" in firing:
            bias = "SLIGHTLY_BULLISH"
            action = f"3/6 confluence active. BTC ${btc:,.0f}. F&G {fg}. Funding {funding:+.3f}%. Hold IBIT+ETHA."
        elif crypto_conc >= 4:
            bias = "BULLISH"
            action = f"Strong confluence ({crypto_conc}/6). Consider adding on CRYPTO_E2 trigger."
        elif crypto_conc <= 1:
            bias = "CAUTIOUS"
            action = "Confluence below threshold. Wait for 2+ layers to align before entering."
        else:
            bias = "NEUTRAL"
            action = f"Confluence {crypto_conc}/6 — below entry threshold (3). Monitoring."
        
        active = []
        for p in positions:
            if "CRYPTO" in p["entry_signal"]:
                active.append({
                    "signal": p["entry_signal"], "symbol": p["symbol"],
                    "direction": p["direction"].upper(),
                    "entry_price": p["entry_price"], "shares": p["shares"],
                    "entered": str(p.get("trade_date","?"))[:10],
                    "status": "ACTIVE",
                })
        
        return {
            "bias": bias, "action": action,
            "next_signal_watch": f"CRYPTO_E1 (3/6 confluence) — currently {crypto_conc}/6",
            "size_adjustment": 0.5 if crypto_conc >= 3 else 0.0,
            "active_positions": active,
            "notes": f"BTC ${btc:,.0f}. F&G {fg}. Funding {funding:+.4f}%. Confluence {crypto_conc}/6.",
        }
    
    elif thesis == "ai":
        soxx = market.get("SOXX", 0)
        igv = market.get("IGV", 0)
        dtcr = market.get("DTCR", 0)
        tan = market.get("TAN", 0)
        intc = market.get("INTC", 0)
        corz = market.get("CORZ", 0)
        
        firing = thesis_state.get("ai", {}).get("firing", [])
        
        if firing:
            bias = "SLIGHTLY_BULLISH"
            action = f"AI signals firing: {', '.join(firing)}. SOXX ${soxx:.0f}. Hold positions."
        elif soxx > 550:
            bias = "BULLISH"
            action = "SOXX above 550 — AI infra spending cycle confirmed. Watch AI_E5 trigger."
        else:
            bias = "NEUTRAL"
            action = f"SOXX ${soxx:.0f} (need >540 for E1). DTCR ${dtcr:.0f} (need >32) TAN ${tan:.0f} (need >67 for E2). Monitoring."
        
        active = []
        for p in positions:
            if "AI" in p["entry_signal"]:
                active.append({
                    "signal": p["entry_signal"], "symbol": p["symbol"],
                    "direction": p["direction"].upper(),
                    "entry_price": p["entry_price"], "shares": p["shares"],
                    "entered": str(p.get("trade_date","?"))[:10],
                    "status": "ACTIVE",
                })
        
        return {
            "bias": bias, "action": action,
            "next_signal_watch": f"AI_E1 (SOXX > 520) — currently ${soxx:.0f}",
            "size_adjustment": 0.5 if firing else 0.0,
            "active_positions": active,
            "notes": f"SOXX ${soxx:.0f}. IGV ${igv:.0f}. INTC ${intc:.0f}. CORZ ${corz:.0f}.",
        }
    
    return {"bias": "NEUTRAL", "action": "No data available."}


# ══════════════════════════════════════════════════════════════════════
# DATA GAPS
# ══════════════════════════════════════════════════════════════════════

def detect_gaps(market: dict, crypto: dict) -> list:
    gaps = []
    if market.get("real_rates", "unknown") == "unknown":
        gaps.append({"module":"macro","gap":"Real rates unknown","impact":"MEDIUM",
                     "fix":"Add FRED DGS10/TIPS yield spread to fetch-prices.py"})
    if not crypto.get("options",{}).get("btc_skew",{}).get("skew"):
        gaps.append({"module":"options","gap":"Deribit IV skew returning zero","impact":"LOW",
                     "fix":"Verify Deribit API endpoint — may need session refresh"})
    return gaps


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

def generate() -> dict:
    market = load_json(MARKET_PATH)
    # Normalize market data — replace None with sensible defaults
    # (fetch-prices.py now propagates None on yfinance failure)
    _market_defaults = {
        "brent_close": 0, "brent_50sma": 100, "gold": 0, "gold_spot": 0,
        "mun7_fcf_yield": 0, "dxy": 100, "vix": 20, "xle_price": 0,
        "xlk_price": 0, "dxy_rising": False, "dxy_falling": False,
        "real_rates": "unknown",
    }
    for k, v in _market_defaults.items():
        if market.get(k) is None:
            market[k] = v

    crypto = load_json(CRYPTO_PATH)
    quant = load_json(QUANT_PATH)
    ai_tracker = load_json(AI_TRACKER_PATH)
    
    # Merge AI ETF prices into market data
    for sym in ["SOXX","IGV","DTCR","TAN","XLC","INTC","BE","CORZ"]:
        if sym in ai_tracker and sym not in market:
            market[sym] = ai_tracker[sym]
    positions, thesis_state, deployed, total_deployed = load_journal()
    
    regime = detect_regime(market, quant)
    confluence = compute_confluence(market, crypto, thesis_state)
    risk = compute_risks(market)
    gaps = detect_gaps(market, crypto)
    
    recs = {}
    for th in ["commodity","crypto","ai"]:
        recs[th] = thesis_recommendation(th, market, crypto, quant, thesis_state, positions, deployed)
    
    # ── DIVERGENCES ──
    divergences = []
    ens = quant.get("ensemble", {}).get("signals", {})
    # ML vs Ensemble divergence
    for ticker in CRYPTO_TICKERS:
        ml = quant.get("signals",{}).get(ticker,{}).get("ml-signals",{})
        ed = ens.get(ticker, {})
        ml_dir = ml.get("direction","")
        ens_dir = ed.get("direction","")
        if ml_dir == "SELL" and ens_dir == "BULLISH":
            divergences.append(f"{ticker}: ML says SELL but ensemble says BULLISH ({ed.get('ensemble_score',0):+.2f})")
        elif ml_dir == "BUY" and ens_dir == "BEARISH":
            divergences.append(f"{ticker}: ML says BUY but ensemble says BEARISH ({ed.get('ensemble_score',0):+.2f})")
    # Thesis vs Quant divergence
    commodity_bias = recs.get("commodity", {}).get("bias", "NEUTRAL")
    crypto_bias = recs.get("crypto", {}).get("bias", "NEUTRAL")
    if "BULLISH" in commodity_bias and "BULLISH" not in crypto_bias:
        divergences.append("Commodity BULLISH but crypto not confirming — macro thesis may be decoupling from risk assets")
    if "BULLISH" in crypto_bias and "BULLISH" not in commodity_bias:
        divergences.append("Crypto BULLISH but commodity not confirming — speculative flow without macro backing")
    
    # ── QUANT + INTRADAY AWARENESS ──
    quant_summary = {}
    if ens:
        bullish_count = sum(1 for e in ens.values() if e.get("direction") == "BULLISH")
        bearish_count = sum(1 for e in ens.values() if e.get("direction") == "BEARISH")
        max_score = max(abs(e.get("ensemble_score",0)) for e in ens.values()) if ens else 0
        best_ticker = max(ens.items(), key=lambda x: abs(x[1].get("ensemble_score",0)))[0] if ens else "?"
        quant_summary = {
            "tickers_analyzed": len(ens),
            "bullish": bullish_count, "bearish": bearish_count,
            "max_abs_score": round(max_score, 3),
            "best_ticker": best_ticker,
            "execution_threshold_met": max_score > 0.7,
        }
    
    intraday_state = {}
    intraday = load_json(INTRADAY_PATH)
    if intraday:
        intraday_state = {
            "candidates_screened": intraday.get("candidates_screened", 0),
            "signals_generated": intraday.get("signals_generated", 0),
            "active": len([s for s in intraday.get("signals", [])]),
            "top_ticker": intraday.get("signals", [{}])[0].get("ticker", "?") if intraday.get("signals") else "?",
        }
    
    return {
        "meta": {
            "generated_at": datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            "synthesizer_version": "v2.1-programmatic",
            "theses_active": 3,
            "modules_loaded": len(quant.get("modules_ran", [])),
            "data_freshness": "live",
        },
        "market_regime": {
            "primary": regime,
            "confidence": 0.7,
            "components": {
                "trend": f"VIX {market.get('vix','?')}, DXY {market.get('dxy','?')}",
                "volatility": f"VIX {market.get('vix','?')}",
                "macro": f"DXY {'rising' if market.get('dxy_rising') else 'falling' if market.get('dxy_falling') else 'flat'} at {market.get('dxy','?')}",
                "sentiment": f"VIX {market.get('vix','?')} {'elevated' if market.get('vix',20)>25 else 'moderate'}",
                "session": f"IST {datetime.now(IST).strftime('%H:%M')}",
            },
        },
        "composite_confluence_score": confluence,
        "primary_risk_factor": risk,
        "divergences": divergences,
        "quant_overview": quant_summary,
        "intraday_overview": intraday_state,
        "thesis_recommendations": recs,
        "data_gaps": gaps,
    }


def main():
    import hashlib
    output = generate()
    
    # Archive previous state — skip if content unchanged (dedup)
    new_hash = hashlib.md5(json.dumps(output, sort_keys=True, default=str).encode()).hexdigest()
    if STATE_PATH.exists():
        try:
            old_data = json.loads(STATE_PATH.read_text())
            old_hash = hashlib.md5(json.dumps(old_data, sort_keys=True, default=str).encode()).hexdigest()
        except Exception:
            old_hash = None
        
        if new_hash != old_hash:
            ts = datetime.now(IST).strftime("%Y%m%d_%H%M")
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            STATE_PATH.rename(ARCHIVE_DIR / f"state_{ts}.json")
    
    # Write new state
    STATE_PATH.write_text(json.dumps(output, indent=2))
    print(f"✅ Synthesizer v2.1 → {STATE_PATH}")
    
    # ── Write to journal.db (learning feedback loop) ──
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS synthesizer_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                regime TEXT,
                confluence_score INTEGER,
                risk_factor TEXT,
                risk_severity TEXT,
                commodity_bias TEXT,
                crypto_bias TEXT,
                ai_bias TEXT,
                state_json TEXT
            )
        """)
        conn.execute(
            "INSERT INTO synthesizer_snapshots (created_at, regime, confluence_score, risk_factor, risk_severity, commodity_bias, crypto_bias, ai_bias, state_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now(IST).strftime("%Y-%m-%d %H:%M"), 
             output["market_regime"]["primary"],
             output["composite_confluence_score"]["value"],
             output["primary_risk_factor"]["factor"],
             output["primary_risk_factor"]["severity"],
             output["thesis_recommendations"]["commodity"]["bias"],
             output["thesis_recommendations"]["crypto"]["bias"],
             output["thesis_recommendations"]["ai"]["bias"],
             json.dumps(output))
        )
        # ── Cleanup: retain 30-day rolling window ──
        cutoff = (datetime.now(IST) - timedelta(days=30)).strftime("%Y-%m-%d")
        old_rows = conn.execute(
            "SELECT id, created_at, regime, state_json FROM synthesizer_snapshots WHERE created_at < ? ORDER BY created_at",
            (cutoff,)
        ).fetchall()
        
        if old_rows:
            # Archive to compressed monthly dump
            archive_base = ARCHIVE_DIR / "snapshots"
            archive_base.mkdir(parents=True, exist_ok=True)
            month_key = old_rows[0][1][:7]  # YYYY-MM
            archive_path = archive_base / f"snapshots_{month_key}.json.gz"
            
            import gzip
            existing = []
            if archive_path.exists():
                try:
                    existing = json.loads(gzip.decompress(archive_path.read_bytes()))
                except Exception:
                    pass
            existing.extend([{
                "created_at": r[1], "regime": r[2] if len(r) > 2 else None, "state": json.loads(r[-1]) if r[-1] else {}
            } for r in old_rows])
            archive_path.write_bytes(gzip.compress(json.dumps(existing, indent=2).encode()))
            
            deleted = conn.execute(
                "DELETE FROM synthesizer_snapshots WHERE created_at < ?", (cutoff,)
            ).rowcount
            print(f"🧹 Retention: archived {len(old_rows)} rows → {archive_path.name}, deleted {deleted}")
        
        conn.commit()
        conn.close()
        print(f"📊 Synthesizer snapshot → journal.db")
    except Exception as e:
        print(f"⚠️ journal.db write failed: {e}")
    
    if "--json" in sys.argv:
        print(json.dumps(output, indent=2))
    elif "--summary" in sys.argv:
        print(f"Regime: {output['market_regime']['primary']}")
        print(f"Confluence: {output['composite_confluence_score']['value']}/5")
        print(f"Risk: {output['primary_risk_factor']['factor']} ({output['primary_risk_factor']['severity']})")
        for th, rec in output["thesis_recommendations"].items():
            print(f"  {th}: {rec['bias']} — {rec['action'][:80]}")


if __name__ == "__main__":
    main()
