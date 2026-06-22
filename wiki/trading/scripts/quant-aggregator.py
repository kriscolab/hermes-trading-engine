#!/usr/bin/env python3
"""
Quant Signal Aggregator
========================
Runs all quant modules, collects edge scores into unified JSON.
Output: /tmp/quant_signals.json — read by dashboard + engine.

Usage:
    python3 quant-aggregator.py            # All modules, all tickers
    python3 quant-aggregator.py --json     # Print JSON only
"""

import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime

QUANT_DIR = Path(__file__).resolve().parent.parent / "crypto-engine" / "quant"
OUTPUT_PATH = Path("/tmp/quant_signals.json")

MODULES = [
    {"name": "mean-reversion",       "script": "mean-reversion.py",       "args": ["--all", "--json"]},
    {"name": "momentum",             "script": "momentum.py",             "args": ["--all", "--json"]},
    {"name": "correlation",          "script": "correlation.py",          "args": ["--json"]},
    {"name": "stat-arbitrage",       "script": "stat-arbitrage.py",       "args": ["--json"]},
    {"name": "monte-carlo",          "script": "monte-carlo.py",          "args": ["--all", "--json"]},
    {"name": "volatility-arbitrage", "script": "volatility-arbitrage.py", "args": ["--all", "--json"]},
    {"name": "ml-signals",           "script": "ml-signals.py",           "args": ["--all", "--json"]},
    {"name": "event-driven",         "script": "event-driven.py",         "args": ["--all", "--json"]},
    {"name": "market-making",        "script": "market-making.py",        "args": ["--all", "--json"]},
    {"name": "microstructure",       "script": "microstructure.py",       "args": ["--all", "--json"]},
    {"name": "orderflow",            "script": "orderflow.py",            "args": ["--all", "--json"]},
    {"name": "tape-reading",         "script": "tape_reading.py",         "args": ["--all", "--json"]},
    {"name": "volume-profile",       "script": "volume_profile.py",       "args": ["--all", "--json"]},
]


def run_module(module_info):
    """Run a quant module, return parsed JSON output."""
    script_path = QUANT_DIR / module_info["script"]
    if not script_path.exists():
        return {"error": f"script not found: {script_path}"}
    
    try:
        result = subprocess.run(
            ["python3", str(script_path)] + module_info["args"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=90,
            cwd=str(QUANT_DIR)
        )
        if result.returncode != 0:
            return {"error": result.stderr[:200]}
        return json.loads(result.stdout) if result.stdout.strip() else []
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except json.JSONDecodeError:
        return {"error": f"invalid JSON: {result.stdout[:100]}"}
    except Exception as e:
        return {"error": str(e)[:100]}


def aggregate():
    """Run all modules, build per-ticker quant signal map."""
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "modules_ran": [],
        "signals": {},  # {BTC: {mean_reversion: {edge, direction}, ...}, ...}
    }
    
    for mod in MODULES:
        name = mod["name"]
        print(f"  {name}...", end=" ")
        data = run_module(mod)
        
        if isinstance(data, dict) and "error" in data:
            print(f"❌ {data['error'][:60]}")
            output["modules_ran"].append({"name": name, "status": "error", "error": data["error"]})
            continue
        
        output["modules_ran"].append({"name": name, "status": "ok"})
        print("✓")
        
        # Parse into per-ticker structure
        if name == "correlation":
            # Correlation returns list of pairs
            _parse_correlation(data, output["signals"])
        elif name == "stat-arbitrage":
            _parse_stat_arb(data, output["signals"])
        elif name == "monte-carlo":
            _parse_monte_carlo(data, output["signals"])
        elif isinstance(data, list):
            # Mean-reversion + momentum return per-ticker list
            for entry in data:
                _parse_ticker_signal(entry, name, output["signals"])
    
    return output


def _parse_ticker_signal(entry, module_name, signals):
    """Parse a per-ticker signal entry."""
    symbol = entry.get("symbol", "")
    base = symbol.split("-")[0].upper() if "-" in symbol else symbol
    
    if base not in signals:
        signals[base] = {}
    
    data = {
        "edge": entry.get("edge_score", 0),
        "direction": entry.get("direction", "NEUTRAL"),
        "size_pct": entry.get("recommended_size_pct", 0),
        "close": entry.get("close"),
    }
    
    # Include module-specific diagnostic fields
    if module_name == "ml-signals":
        data["dominant_regime"] = entry.get("dominant_regime", "UNKNOWN")
        data["recommended_strategy"] = entry.get("recommended_strategy", "NEUTRAL")
        data["anomalies"] = entry.get("anomalies", [])
    elif module_name == "volatility-arbitrage":
        data["vol_regime"] = entry.get("vol_regime", "STABLE")
        data["vol_of_vol"] = entry.get("vol_of_vol_30d", 0)
    elif module_name == "microstructure":
        data["trade_size_regime"] = entry.get("trade_size_regime", "NORMAL")
    elif module_name == "event-driven":
        data["funding_pct"] = entry.get("funding_rate_pct", 0)
        data["liq_count"] = entry.get("liquidation_count", 0)
    
    signals[base][module_name] = data


def _parse_monte_carlo(data, signals):
    """Parse monte-carlo validation output — per-ticker gatekeeper results."""
    if not isinstance(data, list):
        return
    for entry in data:
        symbol = entry.get("symbol", "")
        base = symbol.split("-")[0].upper() if "-" in symbol else symbol
        if base not in signals:
            signals[base] = {}
        v = entry.get("validation", {})
        s = entry.get("sizing", {})
        signals[base]["monte-carlo"] = {
            "edge": v.get("confidence", 50),  # graduated: uses actual confidence 0-100
            "direction": entry.get("direction_tested", "LONG"),
            "p_value": v.get("p_value", 1.0),
            "sharpe": v.get("sharpe_ratio", 0),
            "is_significant": v.get("is_significant", False),
            "confidence": v.get("confidence", 50),
            "optimal_size_pct": s.get("optimal_size_pct", 0),
            "signal_tested": entry.get("signal", "?"),
        }


def _parse_correlation(data, signals):
    """Parse correlation module output."""
    for entry in data:
        pair = entry.get("pair", "")
        label = _corr_label(pair)
        # Store under first asset's base ticker
        first = entry.get("symbols", ["", ""])[0].split("-")[0].upper()
        if first not in signals:
            signals[first] = {}
        signals[first]["correlation"] = {
            "pair": pair,
            "label": label,
            "corr_30d": entry.get("correlations", {}).get("30d", {}).get("value"),
            "signal": entry.get("signal", "MODERATE"),
        }


def _parse_stat_arb(data, signals):
    """Parse stat-arb module output."""
    for entry in data:
        pair = entry.get("pair", "")
        first = entry.get("symbols", ["", ""])[0].split("-")[0].upper()
        if first not in signals:
            signals[first] = {}
        signals[first]["stat_arb"] = {
            "pair": pair,
            "edge": entry.get("edge_score", 0),
            "direction": entry.get("direction", "NEUTRAL"),
            "z_score": entry.get("spread_z_score", 0),
            "correlation": entry.get("correlation"),
        }


def _corr_label(pair):
    mapping = {
        "BTC/SPY": "BTC-SPY",
        "ETH/NASDAQ": "ETH-NQ",
        "ETH/BTC": "ETH-BTC",
        "SOL/BTC": "SOL-BTC",
        "BTC/GLD": "BTC-GLD",
    }
    return mapping.get(pair, pair.replace("/", "-"))


def main():
    print("Quant Aggregator — running modules...")
    output = aggregate()
    
    # Write
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n✅ Quant signals → {OUTPUT_PATH}")
    
    # ── Ensemble meta-model (post-processing) ──
    ensemble_script = QUANT_DIR / "ensemble-meta.py"
    ok_modules = sum(1 for m in output.get("modules_ran", []) if m.get("status") == "ok")
    min_modules = 5
    
    if ok_modules < min_modules:
        print(f"⚠️  Ensemble skipped: only {ok_modules}/{min_modules} modules healthy (min {min_modules} required)")
        output["ensemble"] = {
            "status": "degraded",
            "healthy_modules": ok_modules,
            "min_required": min_modules,
            "signals": {},
        }
    elif ensemble_script.exists():
        print("🧠 Running ensemble meta-model...")
        subprocess.run(
            ["python3", str(ensemble_script)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30,
            cwd=str(QUANT_DIR.parent.parent)
        )
        # Re-read to include ensemble data
        if OUTPUT_PATH.exists():
            output = json.loads(OUTPUT_PATH.read_text())
    
    if "--json" in sys.argv:
        print(json.dumps(output, indent=2))
    else:
        # Summary
        for ticker, sigs in sorted(output["signals"].items()):
            parts = []
            for name, s in sigs.items():
                e = s.get("edge", s.get("corr_30d", "?"))
                d = s.get("direction", s.get("signal", "?"))
                parts.append(f"{name}={e}.{d}")
            if parts:
                print(f"  {ticker}: {', '.join(parts)}")


if __name__ == "__main__":
    main()
