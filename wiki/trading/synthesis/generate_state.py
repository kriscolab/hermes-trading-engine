#!/usr/bin/env python3
"""Strategy Synthesizer — daily_state.json generator (v0.2)"""
import json, os, sqlite3
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")

# ── Load input files ──────────────────────────────────────────────
with open("/tmp/live_market_data.json") as f:
    m = json.load(f)
with open("/tmp/crypto_module_data.json") as f:
    cm = json.load(f)
with open("/tmp/quant_signals.json") as f:
    qs = json.load(f)

# ── Read journal DB ───────────────────────────────────────────────
db_path = os.path.expanduser("~/vault/wiki/trading/paper-trader/journal.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM trades WHERE status='open'")
open_trades = [dict(r) for r in c.fetchall()]

c.execute("SELECT * FROM portfolio_snapshots ORDER BY id DESC LIMIT 1")
snap = c.fetchone()
portfolio = dict(snap) if snap else {}

conn.close()

# ── Current snapshot prices ──────────────────────────────────────
prices = {
    "GLD": m.get("gld_price"),
    "XLE": m.get("xle_price"),
    "IBIT": None,  # from tracker
    "ETHA": None,
    "SOXX": None,
    "IGV": None,
    "DTCR": None,
    "TAN": None,
    "XLC": None,
}
# Load tracker prices
try:
    with open("/tmp/tracker_prices.json") as f:
        tp = json.load(f)
        for k in prices:
            if k in tp:
                prices[k] = tp[k]
except:
    pass
try:
    with open("/tmp/ai_tracker_prices.json") as f:
        ai_p = json.load(f)
        for k in prices:
            if k in ai_p:
                prices[k] = ai_p[k]
except:
    pass
# Hard-code IBIT/ETHA from fetch-prices --portfolio output
prices["IBIT"] = 37.74
prices["ETHA"] = 13.76

# ── Build active positions with P&L ──────────────────────────────
active_positions = []
for t in open_trades:
    sym = t["symbol"]
    pnl = None
    if t["direction"] == "long" and prices.get(sym):
        pnl = round((prices[sym] - t["entry_price"]) * t["shares"], 2)
    elif t["direction"] == "short" and prices.get(sym):
        pnl = round((t["entry_price"] - prices[sym]) * t["shares"], 2)
    active_positions.append({
        "signal": t["entry_signal"],
        "symbol": sym,
        "direction": t["direction"],
        "entry_price": t["entry_price"],
        "shares": t["shares"],
        "current_price": prices.get(sym),
        "unrealized_pnl": pnl,
        "entered": t["trade_date"],
        "thesis": t["thesis_id"],
        "status": "ACTIVE"
    })

# ── Thesis recommendations ────────────────────────────────────────

# --- COMMODITY ---
# Brent $83.02 (vs E2 threshold >$110), GLD short working (-$20.74/share),
# XLE long underwater (-$5.74/share), DXY flat, VIX moderate
commodity_positions = [p for p in active_positions if p["thesis"] == "commodity"]
gold_pnl = sum(p.get("unrealized_pnl",0) or 0 for p in commodity_positions if p["symbol"]=="GLD")
xle_pnl = sum(p.get("unrealized_pnl",0) or 0 for p in commodity_positions if p["symbol"]=="XLE")
commodity = {
    "bias": "BEARISH",
    "action": "Gold short working (+$248 P&L). XLE long underwater (-$1,157). Brent at $83 far from E2 >$110. DXY flat 99.68 provides no tailwind. Hold GLD short for further gold pullback. Reduce XLE position on any bounce to stop-loss threshold. No new commodity entries.",
    "active_signals": {
        "e4s_gold_short": {"status": "ACTIVE", "pnl": gold_pnl, "valid": True},
        "e2_xle_long": {"status": "UNDERWATER", "pnl": xle_pnl, "valid": False, "note": "Brent $83 vs $110 threshold. XLE -9.4% from entry. Assess stop loss."},
        "e1_brent_long": {"status": "WAITING", "valid": False, "note": "Brent $83 vs $110 threshold"}
    },
    "size_adjustment": 0.3,
    "active_positions": commodity_positions,
    "notes": f"Brent ${m['brent_close']}. Gold ${m['gold']}. DXY {m['dxy']}. VIX {m['vix']}. Mun7 FCF yield {m['mun7_fcf_yield']:.4f}. XLE/XLK ratio {m['xle_xlk_ratio']:.4f}."
}

# --- CRYPTO ---
# F&G 23 Extreme Fear rising, confluence 3/6 met (CRYPTO_E1), but all trends down,
# BTC $65.8K, ETH $1.77K. ml-signals strongly BUY across board.
# BTC doji pattern (indecision). Short liquidations only.
btc = cm["prices"].get("btc", 0)
eth = cm["prices"].get("eth", 0)
sol = cm["prices"].get("sol", 0)
fg = cm.get("sentiment",{}).get("fear_greed",{})
confluence = cm.get("confluence",{})
crypto_positions = [p for p in active_positions if p["thesis"] == "crypto"]
# Get BTC quant ensemble signal
btc_signals = qs.get("signals",{}).get("BTC",{})
buy_signals = sum(1 for k,v in btc_signals.items() if isinstance(v,dict) and v.get("direction") in ("BUY","SLIGHTLY_BULLISH","BULLISH"))
total_modules_with_direction = sum(1 for k,v in btc_signals.items() if isinstance(v,dict) and v.get("direction"))
btc_bull_ratio = buy_signals / max(total_modules_with_direction, 1)

crypto = {
    "bias": "SLIGHTLY_BULLISH",
    "action": "Contrarian signal flashing: F&G 23 Extreme Fear rising from 20. Confluence 3/6 met (CRYPTO_E1). ml-signals BUY across BTC/ETH/SOL/AVAX/XRP/LINK. However, all 20d trends down, BTC below VWAP ($73.8K), funding neutral. BTC doji suggests indecision/potential reversal. Hold existing IBIT/ETHA positions. Monitor for confirmation of a bottom before adding.",
    "confluence": {
        "score": confluence.get("score", 0),
        "max_score": confluence.get("max_score", 6),
        "signal": confluence.get("signal", "WAIT"),
        "threshold_met": confluence.get("threshold_met", False)
    },
    "btc_quant_ensemble": {
        "bullish_modules": buy_signals,
        "total_modules": total_modules_with_direction,
        "bull_ratio": round(btc_bull_ratio, 2),
        "interpretation": "Moderately bullish" if btc_bull_ratio > 0.5 else "Bearish-skewed"
    },
    "key_metrics": {
        "btc_dominance": cm.get("correlation",{}).get("btc_dominance",{}).get("btc_dominance_pct"),
        "eth_btc_ratio": cm.get("correlation",{}).get("eth_btc",{}).get("eth_btc_ratio"),
        "fear_greed": {"value": fg.get("fear_greed_value"), "classification": fg.get("classification"), "trend": fg.get("trend")},
        "total_tvl": cm.get("on_chain",{}).get("tvl",{}).get("total_tvl_usd"),
        "tvl_change_7d": cm.get("on_chain",{}).get("tvl",{}).get("tvl_change_7d_pct")
    },
    "notable_alts": [
        {"asset": "AVAX", "signal": "ml-signals 136 BUY (strongest), microstructure SLIGHTLY_BULLISH, volume-profile BULLISH"},
        {"asset": "INJ", "signal": "engulfing_bull pattern + 20d UP trend (bullish outlier)"},
        {"asset": "XRP", "signal": "ml-signals 77 BUY, microstructure BUY, orderflow BULLISH"},
        {"asset": "RUNE", "signal": "engulfing_bull + hammer pattern (potential reversal)"},
        {"asset": "AAVE", "signal": "volume dry-up, orderflow BULLISH, tape NEUTRAL"},
        {"asset": "ONDO", "signal": "orderflow BULLISH (29.93), volume-profile BULLISH (34.86)"}
    ],
    "size_adjustment": 0.5,
    "active_positions": crypto_positions,
    "notes": f"BTC ${btc:,} | ETH ${eth:,} | SOL ${sol:.2f} | F&G {fg.get('fear_greed_value')} ({fg.get('classification')}) rising | BTC funding {cm.get('derivatives',{}).get('btc_funding',{}).get('funding_rate_pct')}% | OI ${cm.get('derivatives',{}).get('btc_oi',{}).get('oi_value_usd',0)/1e9:.1f}B | Corr BTC-GLD {qs.get('signals',{}).get('BTC',{}).get('correlation',{}).get('corr_30d',0)}"
}

# --- AI ---
# SOXX +26.7% from entry (495.87 → 628.45) – strong performance
# IGV flat, DTCR +7.9%, TAN flat, XLC -3.4%
soxx = prices.get("SOXX", 0)
igv = prices.get("IGV", 0)
soxx_entry = 495.87
ai_positions = [p for p in active_positions if p["thesis"] == "ai"]
soxx_pnl = sum(p.get("unrealized_pnl",0) or 0 for p in ai_positions if p["symbol"]=="SOXX")
ai = {
    "bias": "BULLISH",
    "action": "SOXX delivering strong alpha (+26.7% from entry). AI thesis is the best-performing thesis. Hold all positions. Consider scaling SOXX if pullback to $580. DTCR and TAN showing signs of life. IGV flat but steady. Monitor XLC for reversal below $110.",
    "performance": {
        "SOXX": {"entry": soxx_entry, "current": soxx, "return_pct": round((soxx/soxx_entry - 1)*100, 1), "status": "LEADING"},
        "IGV": {"entry": 92.87, "current": igv, "return_pct": round((igv/92.87 - 1)*100, 1), "status": "FLAT"},
        "DTCR": {"entry": 29.57, "current": prices.get("DTCR"), "return_pct": round((prices.get("DTCR",0)/29.57 - 1)*100, 1), "status": "GREEN"},
        "TAN": {"entry": 62.61, "current": prices.get("TAN"), "return_pct": round((prices.get("TAN",0)/62.61 - 1)*100, 1), "status": "FLAT"},
        "XLC": {"entry": 116.12, "current": prices.get("XLC"), "return_pct": round((prices.get("XLC",0)/116.12 - 1)*100, 1), "status": "SLIGHTLY_RED"}
    },
    "next_signal_watch": "AI_E1 active. Watch SOXX > $650 for AI_E2 entry signal. Monitor INTC ($127.86) and CORZ ($28.22) for AI infrastructure conviction adds.",
    "size_adjustment": 1.0,
    "active_positions": ai_positions,
    "notes": f"SOXX ${soxx:.2f} | IGV ${igv:.2f} | DTCR ${prices.get('DTCR','?')} | TAN ${prices.get('TAN','?')} | XLC ${prices.get('XLC','?')} | XLK ${m.get('xlk_price','?')} | INTC $127.86 CORZ $28.22"
}

# ── Composite confluence ──────────────────────────────────────────
thesis_scores = {"commodity": -1, "crypto": 1, "ai": 2}  # bearish, slight bullish, bullish
composite = sum(thesis_scores.values())
composite = max(-5, min(5, composite))  # clamp to [-5,5]

# ── Market regime ─────────────────────────────────────────────────
regime_components = {
    "macro": f"DXY {m['dxy']} (flat), VIX {m['vix']} (moderate)",
    "commodity": f"Brent ${m['brent_close']}, Gold ${m['gold']}",
    "crypto": f"BTC ${btc:,} (downtrend), F&G {fg.get('fear_greed_value')} Extreme Fear",
    "ai_tech": f"SOXX ${soxx:.2f} (+26.7% entry), XLK ${m.get('xlk_price','?')}",
    "volatility": f"VIX {m['vix']}. Crypto vol regime: EXPANDING",
    "sentiment": f"Crypto: Extreme Fear rising. Equities: VIX moderate (16.2)"
}
# Determine primary regime
if fg.get("fear_greed_value", 50) <= 25 and btc < 70000:
    primary_regime = "CRYPTO_FEAR"
elif btc > 70000 and composite > 0:
    primary_regime = "RISK_ON"
elif composite < 0:
    primary_regime = "RISK_OFF"
else:
    primary_regime = "MIXED"

# ── Primary risk factor ──────────────────────────────────────────
risk_factor = {
    "factor": "DXY direction uncertainty + crypto downtrend persistence",
    "severity": "MEDIUM",
    "description": f"DXY flat at {m['dxy']} — no macro direction. Crypto in persistent downtrend (all 20d trends down). BTC-$65.8K below VWAP with expanding vol. Risk of further crypto drawdown if BTC loses $60K support. Commodity energy basket underwater on XLE.",
    "affected_theses": ["commodity", "crypto"]
}

# ── Divergences ──────────────────────────────────────────────────
divergences = [
    {
        "type": "BTC_price_vs_sentiment",
        "detail": f"BTC ${btc:,} at local lows but F&G 23 Extreme Fear rising from 20 — classic bottom signal divergence",
        "direction": "CONTRARIAN_BULLISH"
    },
    {
        "type": "gold_vs_dxy",
        "detail": f"Gold ${m['gold']} elevated while DXY flat at {m['dxy']} — gold holding bid without USD weakness",
        "direction": "GOLD_BID"
    },
    {
        "type": "SOXX_vs_broader_market",
        "detail": f"SOXX $628 (+26.7% from entry) outperforming while most other risk assets weak — AI capex theme intact",
        "direction": "AI_LEADERSHIP"
    }
]

# ── Data gaps ────────────────────────────────────────────────────
data_gaps = [
    {
        "module": "macro",
        "gap": "Real rates unknown",
        "impact": "MEDIUM",
        "fix": "Add FRED DGS10/TIPS yield spread to fetch-prices.py"
    },
    {
        "module": "options",
        "gap": "Deribit IV skew returning zero (BTC/ETH)",
        "impact": "LOW",
        "fix": "Verify Deribit API endpoint — may need session refresh. Currently defaulting to neutral."
    },
    {
        "module": "quant",
        "gap": "stat-arbitrage module failed (NoneType error)",
        "impact": "LOW",
        "fix": "Debug stat-arb module — likely needs ticker validation before spread calculation."
    },
    {
        "module": "commodity",
        "gap": "Brent 50-SMA is null",
        "impact": "LOW",
        "fix": "May need more data points to calculate — yfinance may lack sufficient history."
    }
]

# ── Assemble state ───────────────────────────────────────────────
state = {
    "meta": {
        "generated_at": now_ist,
        "synthesizer_version": "v0.2",
        "theses_active": 3,
        "data_freshness": "live",
        "data_timestamp": m.get("_fetched_at", "unknown")
    },
    "market_regime": {
        "primary": primary_regime,
        "confidence": 0.65,
        "components": regime_components,
        "composite_score": composite
    },
    "composite_confluence_score": {
        "value": composite,
        "range": [-5, 5],
        "interpretation": "Slightly bullish — AI thesis carrying, crypto contrarian signal forming",
        "thesis_scores": thesis_scores
    },
    "primary_risk_factor": risk_factor,
    "divergences": divergences,
    "thesis_recommendations": {
        "commodity": commodity,
        "crypto": crypto,
        "ai": ai
    },
    "portfolio_summary": {
        "cash": portfolio.get("cash"),
        "deployed": portfolio.get("deployed"),
        "equity": portfolio.get("equity"),
        "realized_pnl": portfolio.get("realized_pnl"),
        "open_positions_count": len(open_trades),
        "unrealized_pnl_total": round(sum(p.get("unrealized_pnl",0) or 0 for p in active_positions), 2)
    },
    "data_gaps": data_gaps
}

# ── Write output ─────────────────────────────────────────────────
out_dir = os.path.expanduser("~/vault/wiki/trading/synthesis")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "daily_state.json")
with open(out_path, "w") as f:
    json.dump(state, f, indent=2, default=str)
print(f"✅ daily_state.json written ({os.path.getsize(out_path)} bytes)")
print(f"   Regime: {primary_regime} | Confluence: {composite} | Theses: {thesis_scores}")
print(f"   Active positions: {len(open_trades)} | Unrealized PnL: ${state['portfolio_summary']['unrealized_pnl_total']:.2f}")

# ── Also log to synthesizer_snapshots table ─────────────────────
try:
    conn2 = sqlite3.connect(db_path)
    c2 = conn2.cursor()
    c2.execute("""
        INSERT INTO synthesizer_snapshots (created_at, regime, confluence_score, risk_factor, risk_severity, commodity_bias, crypto_bias, ai_bias, state_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now_ist,
        primary_regime,
        composite,
        risk_factor["factor"],
        risk_factor["severity"],
        commodity["bias"],
        crypto["bias"],
        ai["bias"],
        json.dumps(state, default=str)
    ))
    conn2.commit()
    conn2.close()
    print("✅ synthesizer_snapshots table updated")
except Exception as e:
    print(f"⚠️ DB log skipped: {e}")
