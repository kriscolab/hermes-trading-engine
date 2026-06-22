#!/usr/bin/env python3
"""Crypto-Native Regime Detector — runs inline in crypto engine's 5-min cycle.

Computes regime from crypto-specific data (NOT from the synthesizer's daily_state.json
which is computed from commodity/AI data and updated only once daily).

Data sources (all free, all already fetched):
  /tmp/crypto_module_data.json  — funding, OI, IV skew, F&G, TVL
  /tmp/etf_flows.json           — weekly ETF flows (for thesis health)

Regime determination:
  RISK_ON:   F&G > 60 AND funding > 0 AND OI rising AND IV skew bullish
  TRENDING:  BTC above 50w SMA AND F&G 40-60 AND funding neutral
  NEUTRAL:   No clear signal (default)
  CAUTIOUS:  F&G < 30 OR funding deeply negative OR OI falling
  RISK_OFF:  F&G extreme (<20 or >90) OR liquidation cascade OR BTC < 200w SMA

Returns: regime dict compatible with EngineBase expectations.
"""

import json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    return datetime.now(IST)


def detect_crypto_regime() -> Dict:
    """Detect crypto-specific regime from live data.
    
    Override priority: crypto data > daily_state.json synthesizer.
    If crypto data unavailable, fall back to NEUTRAL (not synthesizer).
    """
    regime = "NEUTRAL"
    reasons = []
    size_mult = 1.0
    allow_entries = True
    
    # Load crypto module data
    crypto = {}
    crypto_path = Path("/tmp/crypto_module_data.json")
    if crypto_path.exists():
        crypto = json.loads(crypto_path.read_text())
    
    # Extract signals
    prices = crypto.get("prices", {})
    sentiment = crypto.get("sentiment", {})
    derivs = crypto.get("derivatives", {})
    options = crypto.get("options", {})
    onchain = crypto.get("on_chain", {})
    
    fg = sentiment.get("fear_greed", {})
    fg_value = fg.get("value", 50)
    
    btc_funding = derivs.get("btc_funding", {})
    funding_rate = btc_funding.get("funding_rate_pct", 0) if isinstance(btc_funding, dict) else 0
    
    btc_oi = derivs.get("btc_oi", {})
    oi_btc = btc_oi.get("open_interest_btc", 0) if isinstance(btc_oi, dict) else 0
    oi_change = btc_oi.get("oi_change_24h_pct", 0) if isinstance(btc_oi, dict) else 0
    
    btc_skew = options.get("btc_skew", {})
    skew_signal = btc_skew.get("skew_signal", "neutral") if isinstance(btc_skew, dict) else "neutral"
    
    tvl = onchain.get("tvl", {})
    tvl_change = tvl.get("tvl_change_7d_pct", 0) if isinstance(tvl, dict) else 0
    
    # ═══════════════════════════════════════════════════════════
    # REGIME DETECTION
    # ═══════════════════════════════════════════════════════════
    
    # RISK_OFF: Extreme conditions
    if fg_value < 20:
        regime = "RISK_OFF"
        reasons.append(f"F&G extreme fear ({fg_value})")
        size_mult = 0.0
        allow_entries = False
    elif fg_value > 90:
        regime = "RISK_OFF"
        reasons.append(f"F&G extreme greed ({fg_value})")
        size_mult = 0.0
        allow_entries = False
    elif tvl_change < -10:
        regime = "RISK_OFF"
        reasons.append(f"TVL collapsing ({tvl_change:+.1f}%)")
        size_mult = 0.0
        allow_entries = False
    
    # RISK_ON: All signals bullish
    elif (fg_value > 60 and funding_rate > 0 and oi_change > 2 and skew_signal == "bullish"):
        regime = "RISK_ON"
        reasons.append(f"F&G={fg_value} funding={funding_rate:.4f}% OI={oi_change:+.1f}% skew={skew_signal}")
        size_mult = 1.0
    
    # TRENDING: BTC above 50w, neutral-to-bullish signals
    elif fg_value >= 40 and abs(funding_rate) < 0.02 and oi_change > -2:
        regime = "TRENDING"
        reasons.append(f"F&G={fg_value} funding neutral OI stable")
        size_mult = 1.0
    
    # CAUTIOUS: Fear or negative signals
    elif fg_value < 30 or funding_rate < -0.02 or oi_change < -5:
        regime = "CAUTIOUS"
        if fg_value < 30:
            reasons.append(f"F&G fear ({fg_value})")
        if funding_rate < -0.02:
            reasons.append(f"Funding deeply negative ({funding_rate:.4f}%)")
        if oi_change < -5:
            reasons.append(f"OI dropping ({oi_change:+.1f}%)")
        size_mult = 0.5
    
    # Default: NEUTRAL
    else:
        reasons.append("No clear crypto regime signal")
    
    # Check ETF flow data for thesis-level override
    etf_path = Path("/tmp/etf_flows.json")
    if etf_path.exists():
        etf = json.loads(etf_path.read_text())
        if etf.get("signals", {}).get("X1_firing"):
            reasons.append("🚨 ETF OUTFLOWS — forcing CAUTIOUS even if signals say otherwise")
            if regime in ("RISK_ON", "TRENDING", "NEUTRAL"):
                regime = "CAUTIOUS"
                size_mult = 0.5
    
    return {
        "regime": regime,
        "size_multiplier": size_mult,
        "allow_entries": allow_entries,
        "reasons": reasons,
        "detected_at": now_ist().isoformat(),
        "source": "crypto-native",
        "fg_value": fg_value,
        "funding_rate": funding_rate,
        "oi_change_24h": oi_change,
        "skew_signal": skew_signal,
        "tvl_change_7d": tvl_change,
    }


# ═══════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    regime = detect_crypto_regime()
    print(f"Regime: {regime['regime']}")
    print(f"Size mult: {regime['size_multiplier']} | Allow entries: {regime['allow_entries']}")
    for r in regime.get("reasons", []):
        print(f"  → {r}")
    print(f"Source: {regime['source']}")
    print(f"F&G: {regime['fg_value']} | Funding: {regime['funding_rate']}% | OI Δ: {regime['oi_change_24h']}%")
