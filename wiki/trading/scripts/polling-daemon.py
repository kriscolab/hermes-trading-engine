#!/usr/bin/env python3
"""
Data Polling Daemon — 5-Minute Market Refresh
===============================================
Runs crypto-data-fetch.py + fetch-prices.py every 300 seconds.
Dashboard reads /tmp/data_freshness.json for data age indicator.

Usage:
    python3 polling-daemon.py              # Run forever, 5-min cycles
    python3 polling-daemon.py --once       # Run once, exit (for cron)

Start:  tmux new-session -d -s polling "cd ~/vault/wiki/trading && python3 scripts/polling-daemon.py"
Status: cat /tmp/data_freshness.json
"""

import subprocess
import json
import time
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

INTERVAL = 300  # 5 minutes
FRESHNESS_PATH = Path("/tmp/data_freshness.json")
CRYPTO_SCRIPT = Path(__file__).resolve().parent / "crypto-data-fetch.py"
PRICES_SCRIPT = Path(__file__).resolve().parent / "fetch-prices.py"
QUANT_SCRIPT = Path(__file__).resolve().parent / "quant-aggregator.py"
EDGE_SCRIPT = Path(__file__).resolve().parent.parent / "synthesis" / "edge-generator.py"
SYNTH_SCRIPT = Path(__file__).resolve().parent.parent / "synthesis" / "synthesizer.py"
RISK_SCRIPT = Path(__file__).resolve().parent.parent / "synthesis" / "risk-engine.py"
INTRADAY_SCRIPT = Path(__file__).resolve().parent.parent / "crypto-engine" / "intraday" / "intraday-engine.py"
TRADING_DIR = Path(__file__).resolve().parent.parent


def run_script(script_path, *args, timeout=90):
    """Run a Python script, return (success, output)."""
    try:
        result = subprocess.run(
            ["python3", str(script_path)] + list(args),
            capture_output=True, text=True, timeout=timeout,
            cwd=str(TRADING_DIR)
        )
        return result.returncode == 0, result.stdout[-500:] if result.stdout else ""
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)[:100]


def write_freshness(success: bool, msg: str = ""):
    """Write freshness status for dashboard to read."""
    FRESHNESS_PATH.write_text(json.dumps({
        "last_refresh": datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "timestamp_epoch": time.time(),
        "status": "ok" if success else "stale",
        "message": msg[:200],
    }))


def refresh():
    """Run both data fetches."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Refreshing...")
    
    # Crypto module data (6-layer + L1)
    ok1, out1 = run_script(CRYPTO_SCRIPT)
    print(f"  crypto-data-fetch: {'✅' if ok1 else '❌'}")
    if not ok1 and out1:
        print(f"    {out1[:100]}")

    # Portfolio prices (commodity mark-to-market)
    time.sleep(2)  # brief gap between heavy API calls
    ok2, out2 = run_script(PRICES_SCRIPT, "--portfolio")
    print(f"  fetch-prices:      {'✅' if ok2 else '❌'}")

    # AI tracker prices (for AI thesis daily check)
    time.sleep(1)
    ok2b, out2b = run_script(PRICES_SCRIPT, "--all")
    print(f"  ai-tracker-prices:  {'✅' if ok2b else '❌'}")

    # Quant modules (edge scores for dashboard)
    time.sleep(2)
    ok3, out3 = run_script(QUANT_SCRIPT)
    print(f"  quant-aggregator:   {'✅' if ok3 else '❌'}")

    # Synthesizer (daily state — must run before edge-generator)
    time.sleep(2)
    ok4, out4 = run_script(SYNTH_SCRIPT)
    print(f"  synthesizer:        {'✅' if ok4 else '❌'}")

    # Edge generator (reads daily_state.json — needs fresh synth data)
    time.sleep(2)
    ok5, out5 = run_script(EDGE_SCRIPT)
    print(f"  edge-generator:     {'✅' if ok5 else '❌'}")

    # Risk engine (position-level TP/SL alerts)
    time.sleep(1)
    ok6, out6 = run_script(RISK_SCRIPT)
    print(f"  risk-engine:        {'✅' if ok6 else '❌'}")

    # Intraday engine (short-term TA signals)
    time.sleep(2)
    ok7, out7 = run_script(INTRADAY_SCRIPT)
    print(f"  intraday-engine:    {'✅' if ok7 else '❌'}")

    success = ok1 and ok2 and ok2b and ok3 and ok4 and ok5 and ok6 and ok7
    
    # Report ALL failures, not just the first two
    failures = []
    if not ok1: failures.append(f"crypto-data-fetch [{out1[:80]}]")
    if not ok2: failures.append(f"fetch-prices-portfolio [{out2[:80]}]")
    if not ok2b: failures.append(f"fetch-prices-all [{out2b[:80]}]")
    if not ok3: failures.append(f"quant-aggregator [{out3[:80]}]")
    if not ok4: failures.append(f"synthesizer [{out4[:80]}]")
    if not ok5: failures.append(f"edge-generator [{out5[:80]}]")
    if not ok6: failures.append(f"risk-engine [{out6[:80]}]")
    if not ok7: failures.append(f"intraday-engine [{out7[:80]}]")
    msg = "; ".join(failures) if failures else ""

    write_freshness(success, msg)
    return success


def main():
    if "--once" in sys.argv:
        refresh()
        return

    print(f"🔄 Data Polling Daemon started — every {INTERVAL}s")
    print(f"   Freshness: {FRESHNESS_PATH}")
    print(f"   Crypto:    {CRYPTO_SCRIPT}")
    print(f"   Prices:    {PRICES_SCRIPT}")
    print()

    consecutive_failures = 0
    while True:
        try:
            ok = refresh()
            if ok:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                # If 3 consecutive failures, increase interval to avoid hammering
                if consecutive_failures >= 3:
                    print(f"  ⚠ {consecutive_failures} consecutive failures — backing off 2x")
                    time.sleep(INTERVAL)  # double wait

            # Wait until next cycle
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\n🛑 Polling daemon stopped.")
            break
        except Exception as e:
            print(f"  ❌ Unexpected: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
