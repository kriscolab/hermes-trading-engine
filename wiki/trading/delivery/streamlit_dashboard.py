#!/usr/bin/env python3
"""Hermes Trading Dashboard v5.1 — V12 3-Engine Architecture
=============================================================
Tabs: Portfolio · Signals · Thesis · Architecture · Pulse
Real marked-to-market P&L · Conviction monitoring · hl.eco-inspired widgets

Usage: streamlit run delivery/streamlit_dashboard.py --server.port 8501 --server.headless true
"""

import streamlit as st
import sqlite3, json, os, sys, pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
TRADING = Path(__file__).resolve().parent.parent
PAPER = TRADING / "paper-trader"

sys.path.insert(0, str(PAPER))
from db_helper import all_trades, all_signals, get_engine_db, get_shared_db

st.set_page_config(page_title="Trading v12", page_icon="📊", layout="wide")

# ── Helpers ──────────────────────────────────────────────────────────
def now_ist(): return datetime.now(IST)
def parse_date(d): return datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=IST)  # Make aware for subtraction
def fmt_pnl(v): return f"+${v:,.0f}" if v > 0 else f"-${abs(v):,.0f}" if v < 0 else "$0"
def pnl_color(v): return "#10b981" if v > 0 else "#ef4444" if v < 0 else "#94a3b8"
def e_color(n): return {"commodity": "#f59e0b", "ai": "#10b981", "crypto": "#6366f1"}.get(n, "#94a3b8")
def load_json(p): 
    if Path(p).exists():
        try: return json.loads(Path(p).read_text())
        except: pass
    return {}

def dframe(rows, cols):
    """Safe dataframe renderer for streamlit."""
    if not rows:
        st.caption("No data")
        return
    return st.dataframe(pd.DataFrame(rows, columns=cols), hide_index=True, use_container_width=True)

@st.cache_data(ttl=15)
def get_prices():
    p = load_json("/tmp/portfolio_prices.json")
    c = load_json("/tmp/crypto_module_data.json")
    if c:
        pr = c.get("prices", {})
        p.update({k.upper(): v for k, v in pr.items() if isinstance(v, (int, float))})
    return p

@st.cache_data(ttl=30)
def engine_snapshot():
    engines = {}
    prices = get_prices()
    for name in ["commodity", "ai", "crypto"]:
        conn = get_engine_db(name)
        open_pos = [dict(r) for r in conn.execute("SELECT * FROM trades WHERE status='open'").fetchall()]
        deployed_cost = sum(p["entry_price"] * p["shares"] for p in open_pos)
        deployed_mtm = 0
        unrealized = 0
        for pos in open_pos:
            live = prices.get(pos["symbol"].upper(), pos["entry_price"])
            val = live * pos["shares"]
            deployed_mtm += val
            u = (live - pos["entry_price"]) * pos["shares"]
            if pos["direction"] == "short": u = -u
            unrealized += u
        closed_pnl = conn.execute("SELECT COALESCE(SUM(pnl_realized),0) FROM trades WHERE status='closed'").fetchone()[0] or 0
        equity = 100_000 - deployed_cost + closed_pnl + unrealized
        engines[name] = {
            "open": open_pos, "deployed_cost": deployed_cost, "deployed_mtm": deployed_mtm,
            "unrealized": unrealized, "closed_pnl": closed_pnl, "equity": equity,
            "count": len(open_pos),
        }
        conn.close()
    return engines

@st.cache_data(ttl=30)
def load_synth(): return load_json(TRADING / "synthesis" / "daily_state.json")
@st.cache_data(ttl=30)
def load_etf(): return load_json("/tmp/etf_flows.json")
@st.cache_data(ttl=10)
def load_quant(): return load_json("/tmp/quant_signals.json")
@st.cache_data(ttl=10)
def load_intraday(): return load_json("/tmp/intraday_signals.json")

# ═════════════════════════════════════════════════════════════════════

st.title("📊 Trading Platform v12")
st.caption(f"3 isolated $100K engines · {now_ist().strftime('%H:%M:%S IST')} · Auto-refresh 30s")

tabs = st.tabs(["📋 Portfolio", "📡 Signals", "📖 Thesis", "🏗 Architecture", "🔍 Pulse"])

engines = engine_snapshot()
synth = load_synth()
etf = load_etf()

# ═════════════════════════════════════════════════════════════════════
# TAB 1: PORTFOLIO
# ═════════════════════════════════════════════════════════════════════
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    for col, name, data in [(c1, "commodity", engines["commodity"]), 
                              (c2, "ai", engines["ai"]),
                              (c3, "crypto", engines["crypto"]),
                              (c4, "total", None)]:
        with col:
            if name == "total":
                eq = sum(e["equity"] for e in engines.values())
                dep = sum(e["deployed_mtm"] for e in engines.values())
                ur = sum(e["unrealized"] for e in engines.values())
                cl = sum(e["closed_pnl"] for e in engines.values())
            else:
                eq, dep, ur, cl = data["equity"], data["deployed_mtm"], data["unrealized"], data["closed_pnl"]
            cap_pct = dep / 100_000 * 100 if name != "total" else dep / 300_000 * 100
            label = name.upper() if name != "total" else "TOTAL"
            color = e_color(name) if name != "total" else "#22d3ee"
            st.markdown(f"""
            <div style="background:#0f172a;border:1px solid {color}40;border-radius:8px;padding:10px;margin:3px 0">
              <div style="color:#94a3b8;font-size:10px;text-transform:uppercase">{label}</div>
              <div style="color:{color};font-size:20px;font-weight:bold;font-family:monospace">${eq:,.0f}</div>
              <div style="font-size:10px;font-family:monospace">
                <span style="color:#94a3b8">Dep:</span> ${dep:,.0f} ({cap_pct:.0f}%)
                <span style="color:{pnl_color(ur)}"> U: {fmt_pnl(ur)}</span>
                <span style="color:{pnl_color(cl)}"> R: {fmt_pnl(cl)}</span>
              </div>
            </div>""", unsafe_allow_html=True)

    st.divider()
    
    prices = get_prices()
    for name, data in engines.items():
        if not data["open"]: continue
        st.subheader(f"{name.upper()} — {data['count']} Open Positions")
        rows = []
        for p in data["open"]:
            live = prices.get(p["symbol"].upper(), p["entry_price"])
            u_pnl = (live - p["entry_price"]) * p["shares"]
            if p["direction"] == "short": u_pnl = -u_pnl
            u_pnl_pct = (live / p["entry_price"] - 1) * 100
            if p["direction"] == "short": u_pnl_pct = -u_pnl_pct
            sig = p.get("entry_signal", "?").replace("COMM_ENTRY_","").replace("AI_ENTRY_","").replace("CRYPTO_ENTRY_","").replace("TACTICAL_","⚡")
            cost = p["entry_price"] * p["shares"]
            mtm = live * p["shares"]
            rows.append([sig, p["direction"], p["symbol"], f"${p['entry_price']:,.2f}", f"${live:,.2f}",
                        f"{p['shares']:,.1f}", f"${cost:,.0f}", f"${mtm:,.0f}", 
                        f"{fmt_pnl(u_pnl)} ({fmt_pnl(u_pnl_pct)}%)"])
        dframe(rows, ["Signal", "Dir", "Ticker", "Entry", "Live", "Shares", "Cost", "MTM", "U-P&L"])

    st.divider()
    st.subheader("📜 Recent Closed Trades")
    trades = all_trades()
    closed = [t for t in trades if t.get("status") == "closed"]
    closed.sort(key=lambda x: x.get("exit_date", ""), reverse=True)
    rows = []
    for t in closed[:20]:
        sig = t.get("entry_signal", "?").replace("COMM_ENTRY_","").replace("AI_ENTRY_","").replace("CRYPTO_ENTRY_","").replace("TACTICAL_","⚡")
        pnl = t.get("pnl_realized", 0) or 0
        rows.append([t.get("engine", "?"), sig, t.get("direction","?"), t.get("symbol","?"),
                    f"${t.get('entry_price',0):,.2f}", f"${t.get('exit_price',0):,.2f}",
                    fmt_pnl(pnl), t.get("exit_date","")[:10]])
    dframe(rows, ["Engine", "Signal", "Dir", "Symbol", "Entry", "Exit", "P&L", "Date"])

# ═════════════════════════════════════════════════════════════════════
# TAB 2: SIGNALS
# ═════════════════════════════════════════════════════════════════════
with tabs[1]:
    qd = load_quant()
    idd = load_intraday()
    
    sc1, sc2 = st.columns(2)
    with sc1:
        st.subheader("📊 Quant Ensemble")
        if qd:
            ens = qd.get("ensemble", {}).get("signals", {})
            if ens:
                rows = []
                for t, m in sorted(ens.items()):
                    mc_ok = qd.get("signals", {}).get(t, {}).get("monte-carlo", {}).get("passed", False)
                    rows.append([t, m.get("ensemble_score", 0), m.get("direction", "?"), "✅" if mc_ok else "⏳"])
                dframe(rows, ["Ticker", "Score", "Direction", "MC"])
            else:
                st.caption("No quant signals")
        else:
            st.caption("Quant signals not available")

    with sc2:
        st.subheader("⚡ Intraday Signals")
        if idd:
            sigs = idd.get("signals", [])
            if sigs:
                rows = [[s.get("ticker","?"), s.get("direction","?"), s.get("pattern","?"), s.get("confidence","?")]
                        for s in sigs[:15]]
                dframe(rows, ["Ticker", "Direction", "Pattern", "Conf"])
            else:
                st.caption("No intraday signals")
        else:
            st.caption("Intraday signals not available")

    st.divider()
    st.subheader("📡 Signal Activity (Today)")
    sigs = all_signals()
    today = now_ist().strftime("%Y-%m-%d")
    recent = [s for s in sigs if s.get("check_date", "").startswith(today)]
    trig = [s for s in recent if s.get("triggered")]
    executed = [s for s in trig if s.get("executed")]
    st.metric("Today", f"{len(recent)} checked / {len(trig)} triggered / {len(executed)} executed")
    if trig:
        rows = [[s.get("signal_id","?").replace("_"," "), s.get("check_date","?")[-8:],
                "✅" if s.get("executed") else "⏳", s.get("engine","?")]
                for s in trig[-20:]]
        dframe(rows, ["Signal", "Time", "Exec", "Engine"])

# ═════════════════════════════════════════════════════════════════════
# TAB 3: THESIS
# ═════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("🎯 Thesis Conviction Monitor")
    st.caption("Structural positions are conviction-managed, NOT hard-stop-managed. Price drawdowns are noise unless thesis triggers fire.")
    
    tc1, tc2, tc3 = st.columns(3)
    
    with tc1:
        st.markdown("**🛢️ COMMODITY — Currie**")
        st.markdown("*Mag7→Mun7 rotation. XLE/XLK ratio is the canary.*")
        drift_days = 0
        for p in engines["commodity"]["open"]:
            entry = p.get("trade_date", "")
            if entry:
                age = (now_ist() - parse_date(entry)).days
                drift_days = max(drift_days, age)
        st.metric("Synthesizer Bias", synth.get("commodity_bias", "NEUTRAL"))
        st.metric("Regime", synth.get("regime", "?"))
        st.metric("Oldest Position", f"{drift_days}d")
        st.metric("Invalidation", "⚠️ Stale" if drift_days > 90 else "None")
        st.caption("Triggers: Brent pullback/breakout, energy rotation, gold tactical short")
    
    with tc2:
        st.markdown("**🤖 AI — Aschenbrenner**")
        st.markdown("*AGI by 2027 requires compute. SOXX >520 = buildout.*")
        drift_days = 0
        for p in engines["ai"]["open"]:
            entry = p.get("trade_date", "")
            if entry:
                age = (now_ist() - parse_date(entry)).days
                drift_days = max(drift_days, age)
        soxx_live = prices.get("SOXX", 0)
        st.metric("Synthesizer Bias", synth.get("ai_bias", "NEUTRAL"))
        st.metric("SOXX Live", f"${soxx_live:,.0f}" if soxx_live else "—")
        st.metric("Oldest Position", f"{drift_days}d")
        st.metric("Invalidation", "⚠️ SOXX below floor" if soxx_live < 400 else "None")
        st.caption("Triggers: Capex, GPU, software, datacenter, renewables")
    
    with tc3:
        st.markdown("**🪙 CRYPTO — Fink**")
        st.markdown("*Institutional Inevitability. ETFs = GLD moment.*")
        inv = load_json("/tmp/crypto_invalidation.json")
        etf_f = etf.get("signals", {}) if etf else {}
        st.metric("E1 ETF Flow", "🔥 FIRING" if etf_f.get("E1_firing") else "— idle")
        st.metric("X1 Retreat", "🚨 FIRING" if etf_f.get("X1_firing") else "— idle")
        st.metric("Threshold", "0.03% BTC mcap")
        if inv:
            sigs = inv.get("signals", {})
            for sid, sd in sigs.items():
                if isinstance(sd, dict):
                    st.metric(sid, sd.get("status", "?") or f"dormant {sd.get('consecutive_dormant',0)}d")
        st.caption("Triggers: ETF flows, custody, regulation, sovereign, liquidity")

# ═════════════════════════════════════════════════════════════════════
# TAB 4: ARCHITECTURE
# ═════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("🏗 V12 3-Engine Architecture")
    st.code("""$300K TOTAL — 3 ISOLATED $100K ENGINES — 80% HARD CAP

┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────────────┐
│ COMMODITY ENGINE    │  │   AI ENGINE          │  │    CRYPTO ENGINE          │
│ Currie "Mag7→Mun7"  │  │ Aschenbrenner "AGI27"│  │ Fink "Institutional"     │
│ 9:00 AM IST         │  │ 9:15 AM IST          │  │ Every 5 min               │
│ 4 entry / 5 exit    │  │ 5 entry / 5 exit     │  │ 5 thesis + tactical       │
│ 2 open · $17K dep   │  │ 5 open · $25K dep    │  │ 0 open · clean start      │
└─────────┬───────────┘  └─────────┬───────────┘  └──────────┬───────────────┘
          └─────────────────────────┼──────────────────────────┘
                         ┌──────────┴───────────┐
                         │  SHARED LEARNING      │
                         │  db_helper UNION ALL  │
                         │  weekly-review        │
                         │  missed-audit         │
                         │  correlator           │
                         └───────────────────────┘""", language=None)
    
    st.divider()
    st.subheader("⏰ Cron Pipeline (IST)")
    st.code("""08:50  ETF Flow Scanner      → /tmp/etf_flows.json
08:55  Invalidation Watchdog → /tmp/crypto_invalidation.json
09:00  COMMODITY ENGINE      → 📡 Channel
09:15  AI ENGINE             → 📡 Channel
every  CRYPTO ENGINE         → 📡 Channel (thesis+tactical+regime)
5 min
Sun    Meta-Optimizers ×3    → /tmp/*_params.json
22:00
KILLED: 12 old trading crons · CREATED: 6 new v12 crons""", language=None)

# ═════════════════════════════════════════════════════════════════════
# TAB 5: PULSE
# ═════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("🔍 Market Pulse")
    
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown("**ETF Flow Scanner**")
        if etf:
            f = etf.get("signals", {})
            st.metric("E1 Accumulation", "🔥 FIRING" if f.get("E1_firing") else "— idle")
            st.metric("X1 Retreat", "🚨 FIRING" if f.get("X1_firing") else "— idle")
            mcap = etf.get("btc_market_cap", 0)
            flows = etf.get("weekly_flows_usd", 0)
            st.metric("BTC Market Cap", f"${mcap:,.0f}" if mcap else "—")
            st.metric("Weekly Flows", f"${flows:,.0f}" if flows else "—")
            st.caption("Threshold: 0.03% BTC mcap · 2 consecutive weeks")
        else:
            st.caption("ETF scanner not yet run")
    
    with pc2:
        st.markdown("**Synthesizer State**")
        st.code(f"""Regime: {synth.get('regime', '?')}
Risk: {synth.get('risk_factor', '?')} ({synth.get('risk_severity', '?')})
Commodity: {synth.get('commodity_bias', '?')}
AI: {synth.get('ai_bias', '?')}
Crypto: {synth.get('crypto_bias', '?')}""", language=None)
    
    st.divider()
    st.subheader("🔗 Cross-Thesis Summary")
    total_eq = sum(e["equity"] for e in engines.values())
    total_dep = sum(e["deployed_mtm"] for e in engines.values())
    total_ur = sum(e["unrealized"] for e in engines.values())
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Total Equity", f"${total_eq:,.0f}")
    mc2.metric("Deployed (MTM)", f"${total_dep:,.0f} ({total_dep/3000:.0f}%)")
    mc3.metric("Unrealized P&L", fmt_pnl(total_ur))

    st.divider()
    st.subheader("⚠️ Risk Events (Circuit Breakers)")
    try:
        conn = get_engine_db("crypto")
        events = conn.execute("SELECT event_at, event_type, detail FROM risk_events ORDER BY event_at DESC LIMIT 10").fetchall()
        if events:
            for e in events:
                ts = e["event_at"][:19] if e["event_at"] else "?"
                st.markdown(f"`{ts}` **{e['event_type']}**: {e['detail'][:80]}")
        else:
            st.caption("No risk events triggered")
        conn.close()
    except:
        st.caption("Risk events table not available")

st.divider()
st.caption(f"v12 · {now_ist().strftime('%H:%M:%S IST')} · 3 engines · pandas-backed dataframes")
