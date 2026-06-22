#!/usr/bin/env python3
"""Daily Invalidation Watchdog — Crypto Thesis v2.

Runs at 8:55 AM IST (before 9 AM thesis check).
Checks ALL active thesis signals for invalidation, dormancy, or exit triggers.

If an exit signal fires → DM alert immediately.
If a signal invalidated since last check → flag.
If a signal dormant for 14+ days → warn.

Output: /tmp/crypto_invalidation.json
  { signals: { signal_id: {status, last_active, alert} }, exit_firing: bool, alerts: [...] }

Run: daily at 8:55 AM IST (cron or manual).
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

OUTPUT_PATH = Path("/tmp/crypto_invalidation.json")
STATE_PATH = Path("/tmp/crypto_invalidation_state.json")
ETF_FLOWS_PATH = Path("/tmp/etf_flows.json")


def now_ist():
    return datetime.now(IST)


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"signals": {}, "last_check": None}


def save_state(state):
    state["last_check"] = now_ist().isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str))


def check_etf_flows(state):
    """Check ETF flow data from scanner."""
    signal_state = state["signals"].get("E1", {"status": "unknown", "last_active": None, "consecutive_dormant": 0})
    
    if ETF_FLOWS_PATH.exists():
        flows = json.loads(ETF_FLOWS_PATH.read_text())
        e1_firing = flows.get("signals", {}).get("E1_firing", False)
        x1_firing = flows.get("signals", {}).get("X1_firing", False)
        
        if e1_firing:
            signal_state["status"] = "active"
            signal_state["last_active"] = now_ist().isoformat()
            signal_state["consecutive_dormant"] = 0
        else:
            signal_state["consecutive_dormant"] = signal_state.get("consecutive_dormant", 0) + 1
        
        state["signals"]["E1"] = signal_state
        
        # Check X1 (exit: institutional retreat)
        if x1_firing:
            state["signals"]["X1"] = {
                "status": "firing",
                "alert": "🚨 CRYPTO_X1 FIRING: ETF outflows exceeding threshold. Reduce core by 50%.",
                "checked_at": now_ist().isoformat(),
            }
    else:
        signal_state["consecutive_dormant"] = signal_state.get("consecutive_dormant", 0) + 1
        state["signals"]["E1"] = signal_state
    
    return state


def generate_alerts(state):
    """Generate alert messages for any firing or dormant signals."""
    alerts = []
    
    for sig_id, sig in state.get("signals", {}).items():
        # Exit signals firing
        if sig.get("status") == "firing":
            alerts.append(sig.get("alert", f"🚨 {sig_id} FIRING"))
            continue
        
        # Dormant for 14+ days
        if sig.get("consecutive_dormant", 0) >= 14:
            alerts.append(f"⚠️ {sig_id}: dormant for {sig['consecutive_dormant']} days — no signal activity")
        
        # Just invalidated (was active, now dormant for 1 day)
        if sig.get("consecutive_dormant", 0) == 1 and sig.get("status") == "was_active":
            alerts.append(f"⚡ {sig_id}: INVALIDATED — was active, now inactive")
    
    return alerts


def main():
    print("Invalidation Watchdog — Crypto Thesis v2")
    print(f"  {now_ist().strftime('%Y-%m-%d %H:%M IST')}")
    
    state = load_state()
    
    # Check each signal source
    state = check_etf_flows(state)
    
    # Manual signal checks (E2-E4, X2-X5) — these are event-driven
    # For now, we only auto-check E1/X1. E2-E4 are checked by the engine when
    # signal data is provided via /tmp files or web search results.
    
    # For remaining signals, check dormancy
    for sig_id in ["E2", "E3", "E3bis", "E4"]:
        if sig_id not in state["signals"]:
            state["signals"][sig_id] = {"status": "unknown", "consecutive_dormant": 0, "last_active": None}
        s = state["signals"][sig_id]
        # These are event-driven — if no new data, increment dormancy
        if s.get("status") not in ("active", "firing"):
            s["consecutive_dormant"] = s.get("consecutive_dormant", 0) + 1
        state["signals"][sig_id] = s
    
    # Generate alerts
    alerts = generate_alerts(state)
    
    # Build output
    output = {
        "checked_at": now_ist().isoformat(),
        "signals": state["signals"],
        "exit_firing": any(s.get("status") == "firing" for s in state["signals"].values()),
        "alerts": alerts,
        "alert_count": len(alerts),
    }
    
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    save_state(state)
    
    # Summary
    active = sum(1 for s in state["signals"].values() if s.get("status") == "active")
    dormant = sum(1 for s in state["signals"].values() if s.get("consecutive_dormant", 0) >= 14)
    firing = sum(1 for s in state["signals"].values() if s.get("status") == "firing")
    
    print(f"\n  Active: {active} | Dormant ≥14d: {dormant} | Exit firing: {firing}")
    
    if alerts:
        print("\n  ALERTS:")
        for a in alerts:
            print(f"    {a}")
    else:
        print("  ✅ No alerts")
    
    print(f"\n  Output: {OUTPUT_PATH}")
    return output


if __name__ == "__main__":
    main()
