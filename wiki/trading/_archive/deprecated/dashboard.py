#!/usr/bin/env python3
"""
Trading Dashboard — Headless Server
=====================================
Reads journal.db, generates self-contained HTML with equity curve,
positions, signal performance. Served on port 8484 via Python http.server.

Usage:
    python3 dashboard.py                  # Serve on port 8484
    python3 dashboard.py --port 9000      # Custom port
    python3 dashboard.py --generate       # Just generate HTML, don't serve

Access:
    ssh -L 8484:localhost:8484 hermes-pilot@104.223.42.16
    Then open http://localhost:8484 on laptop
"""

import sqlite3
import json
import os
import sys
import http.server
import socketserver
from datetime import datetime
from pathlib import Path

PORT = 8484
HTML_PATH = Path("/tmp/trading_dashboard.html")
DB_PATH = Path(__file__).resolve().parent.parent / "paper-trader" / "journal.db"

# ── Data Fetchers ──────────────────────────────────────────────────────

def fetch_data():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    positions = [dict(r) for r in conn.execute(
        "SELECT * FROM trades WHERE status = 'open' ORDER BY trade_date"
    ).fetchall()]

    closed = [dict(r) for r in conn.execute(
        "SELECT * FROM trades WHERE status = 'closed' ORDER BY exit_date DESC LIMIT 30"
    ).fetchall()]

    snapshots = [dict(r) for r in conn.execute(
        "SELECT snap_date, equity, deployed, realized_pnl FROM portfolio_snapshots ORDER BY snap_date"
    ).fetchall()]

    all_closed = [dict(r) for r in conn.execute(
        "SELECT * FROM trades WHERE status = 'closed'"
    ).fetchall()]

    conn.close()

    wins = [t for t in all_closed if t["pnl_realized"] > 0]
    losses = [t for t in all_closed if t["pnl_realized"] <= 0]
    total_realized = sum(t["pnl_realized"] for t in all_closed)
    deployed = sum(p["entry_price"] * p["shares"] for p in positions)
    cash = 100_000 - deployed + total_realized
    equity = cash + deployed  # realized only baseline
    
    # Add unrealized P&L if price data available
    unrealized = 0.0
    try:
        prices = json.loads(Path("/tmp/portfolio_prices.json").read_text())
        for p in positions:
            sym = p["symbol"]
            mkt = prices.get(sym)
            if mkt and mkt > 0:
                if p["direction"] == "long":
                    unrealized += (mkt - p["entry_price"]) * p["shares"]
                else:
                    unrealized += (p["entry_price"] - mkt) * p["shares"]
    except Exception:
        pass
    
    equity_with_upnl = equity + unrealized

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "positions": positions,
        "closed_trades": closed[:10],
        "snapshots": snapshots,
        "stats": {
            "cash": round(cash, 2), "deployed": round(deployed, 2),
            "equity": round(equity_with_upnl, 2), "realized_pnl": round(total_realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "open_count": len(positions), "closed_count": len(all_closed),
            "win_count": len(wins), "loss_count": len(losses),
            "win_rate": len(wins) / len(all_closed) * 100 if all_closed else 0,
            "avg_win": sum(t["pnl_realized"] for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t["pnl_realized"] for t in losses) / len(losses) if losses else 0,
        }
    }


def build_html(data):
    s = data["stats"]
    snap_json = json.dumps([{"date": x["snap_date"], "equity": x["equity"]} for x in data["snapshots"]])

    pnl_class = "green" if s["realized_pnl"] >= 0 else "red"
    wr_class = "green" if s["win_rate"] >= 50 else "red"

    parts = []

    # Header
    parts.append(f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="refresh" content="60">
<title>Trading Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}}
h1{{font-size:1.5rem;margin-bottom:5px}}
.header{{text-align:center;margin-bottom:25px}}
.header p{{color:#94a3b8;font-size:.85rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:15px;margin-bottom:25px}}
.card{{background:#1e293b;border-radius:12px;padding:18px;text-align:center}}
.card .label{{font-size:.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px}}
.card .value{{font-size:1.5rem;font-weight:700;margin-top:5px}}
.card .sub{{font-size:.8rem;color:#94a3b8;margin-top:3px}}
.green{{color:#10b981}}.red{{color:#ef4444}}.yellow{{color:#f59e0b}}
.chart-container{{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:25px}}
.chart-container canvas{{max-height:300px}}
.section{{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:25px}}
.section h2{{font-size:1.1rem;margin-bottom:15px;color:#94a3b8}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th{{text-align:left;padding:10px 8px;border-bottom:1px solid #334155;color:#94a3b8}}
td{{padding:8px;border-bottom:1px solid #1e293b}}
tr:hover{{background:#334155}}
.footer{{text-align:center;color:#475569;font-size:.75rem;margin-top:20px}}
@media(max-width:600px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>
<div class="header"><h1>Trading Dashboard</h1><p>Updated: {data['generated_at']} · Auto-refresh 60s</p></div>
<div class="grid">
<div class="card"><div class="label">Equity</div><div class="value">${s['equity']:,.0f}</div><div class="sub">${s['cash']:,.0f} cash · ${s['deployed']:,.0f} deployed · UPNL ${s.get('unrealized_pnl',0):+,.0f}</div></div>
<div class="card"><div class="label">Realized P&L</div><div class="value {pnl_class}">${s['realized_pnl']:+,.0f}</div></div>
<div class="card"><div class="label">Open Positions</div><div class="value">{s['open_count']}</div></div>
<div class="card"><div class="label">Win Rate</div><div class="value {wr_class}">{s['win_rate']:.0f}%</div><div class="sub">{s['win_count']}W / {s['loss_count']}L</div></div>""")

    if s["avg_win"] > 0:
        parts.append(f'<div class="card"><div class="label">Avg Win</div><div class="value green">${s["avg_win"]:+,.0f}</div></div>')
    if s["avg_loss"] < 0:
        parts.append(f'<div class="card"><div class="label">Avg Loss</div><div class="value red">${s["avg_loss"]:,.0f}</div></div>')

    parts.append("</div>")

    # Equity chart
    if data["snapshots"]:
        parts.append('<div class="chart-container"><canvas id="eqChart"></canvas></div>')

    # Open positions
    if data["positions"]:
        parts.append('<div class="section"><h2>Open Positions</h2><table><thead><tr><th>Type</th><th>Symbol</th><th>Shares</th><th>Entry</th><th>Signal</th><th>Date</th></tr></thead><tbody>')
        for p in data["positions"]:
            d = "LONG" if p["direction"] == "long" else "SHORT"
            c = "#10b981" if d == "LONG" else "#ef4444"
            parts.append(f'<tr><td><span style="color:{c}">●</span> {d}</td><td>{p["symbol"]}</td><td>{p["shares"]:.2f}</td><td>${p["entry_price"]:,.2f}</td><td>{p["entry_signal"]}</td><td>{p["trade_date"]}</td></tr>')
        parts.append("</tbody></table></div>")

    # Closed trades
    if data["closed_trades"]:
        parts.append('<div class="section"><h2>Recent Closed Trades</h2><table><thead><tr><th>Symbol</th><th>Dir</th><th>P&L</th><th>Signal</th><th>Date</th></tr></thead><tbody>')
        for t in data["closed_trades"]:
            pc = "#10b981" if t["pnl_realized"] >= 0 else "#ef4444"
            parts.append(f'<tr><td>{t["symbol"]}</td><td>{t["direction"]}</td><td style="color:{pc}">${t["pnl_realized"]:+,.2f}</td><td>{t["entry_signal"]} → {t.get("exit_signal","?")}</td><td>{t.get("exit_date",t["trade_date"])}</td></tr>')
        parts.append("</tbody></table></div>")

    # Footer + Chart JS
    parts.append(f'<div class="footer">Hermes Dashboard · Port {PORT}</div>')
    parts.append(f'<script>const snaps={snap_json};if(snaps.length){{new Chart(document.getElementById("eqChart"),{{type:"line",data:{{labels:snaps.map(s=>s.date),datasets:[{{label:"Equity",data:snaps.map(s=>s.equity),borderColor:"#10b981",backgroundColor:"rgba(16,185,129,0.1)",fill:true,tension:.3,pointRadius:2}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:"#94a3b8",maxTicksLimit:10}}}},y:{{ticks:{{color:"#94a3b8",callback:v=>"$"+v.toLocaleString()}}}}}}}})}};</script>')
    parts.append("</body></html>")

    return "\n".join(parts)


def serve(port=PORT):
    class DashboardHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                data = fetch_data()
                html = build_html(data)
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode())
            else:
                super().do_GET()
        def log_message(self, format, *args):
            pass

    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"\nDashboard live at: http://localhost:{port}")
        print(f"SSH tunnel: ssh -L {port}:localhost:{port} hermes-pilot@104.223.42.16")
        print("Then open http://localhost:8484 on your laptop/phone")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main():
    port = PORT
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        elif arg == "--generate":
            data = fetch_data()
            html = build_html(data)
            HTML_PATH.write_text(html)
            print(f"HTML: {HTML_PATH}")
            return
    serve(port)


if __name__ == "__main__":
    main()
