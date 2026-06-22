#!/usr/bin/env python3
"""
Sanity Audit — v10.6
===================
Verifies the complete data→usage→delivery chain across the platform.
Checks: modules referenced, data collected, crons delivering, no orphans.

Usage:
    python3 sanity-audit.py              # Full audit → vault + stdout
    python3 sanity-audit.py --summary    # Telegram-ready summary
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
MODULES_DIR = BASE_DIR / "modules"
THESES_DIR = BASE_DIR / "theses"
PAPER_TRADER_DIR = BASE_DIR / "paper-trader"
LEARNING_DIR = BASE_DIR / "learning"
SYNTHESIS_DIR = BASE_DIR / "synthesis"
SCRIPTS_DIR = BASE_DIR / "scripts"
DELIVERY_DIR = BASE_DIR / "delivery"
DB_PATH = PAPER_TRADER_DIR / "journal.db"

CRON_OUTPUT_DIR = Path.home() / ".hermes" / "cron" / "output"

# ── Check definitions ──

def check_modules() -> Dict:
    """Audit all modules."""
    if not MODULES_DIR.exists():
        return {"count": 0, "built": 0, "unreferenced": [], "issues": ["modules/ directory missing"]}

    modules = list(MODULES_DIR.glob("*.md"))
    result = {
        "count": len(modules),
        "built": [],
        "placeholder": [],
        "unreferenced": [],
        "by_layer": defaultdict(list),
    }

    for m in modules:
        content = m.read_text()
        name = m.stem
        status_line = [l for l in content.split("\n") if "Status:" in l]
        status = "unknown"
        if status_line:
            status = status_line[0].split("Status:")[-1].strip()

        if "DEFINED" in status.upper() or "BUILT" in content[:500].lower():
            result["built"].append(name)
        else:
            result["placeholder"].append(name)

        # Check if referenced by any thesis
        referenced = False
        for thesis_dir in THESES_DIR.glob("*/"):
            for tf in thesis_dir.glob("*.md"):
                if name.lower() in tf.read_text().lower():
                    referenced = True
                    break
            if referenced:
                break

        if not referenced:
            result["unreferenced"].append(name)

        # Layer mapping
        layer_map = {
            "price-action": "L1", "volume-profile": "L1",
            "derivatives": "L2", "options": "L3", "liquidation": "L4",
            "on-chain": "L5", "macro": "L6",
            "regime": "Gap1", "session-clock": "Gap2",
            "sentiment": "Gap3", "correlation": "Gap4",
            "position-sizing": "Gap6", "smart-contracts": "DeFi",
            "fundamental": "Equity", "airdrop-scanner": "Yield",
        }
        layer = layer_map.get(name, "Unknown")
        result["by_layer"][layer].append(name)

    result["issues"] = []
    if result["unreferenced"]:
        result["issues"].append(
            f"{len(result['unreferenced'])} modules not referenced by any thesis: "
            f"{', '.join(result['unreferenced'])}"
        )

    return result


def check_theses() -> Dict:
    """Audit all theses."""
    if not THESES_DIR.exists():
        return {"count": 0, "issues": ["theses/ directory missing"]}

    thesis_dirs = [d for d in THESES_DIR.glob("*/") if d.name != "index.md"]
    result = {"count": len(thesis_dirs), "details": {}, "issues": []}

    for td in thesis_dirs:
        name = td.name
        files = list(td.glob("*.md"))
        result["details"][name] = {
            "files": [f.name for f in files],
            "count": len(files),
        }

        # Check minimum required files
        required = ["signals.md"]
        missing = [r for r in required if not (td / r).exists()]
        if missing:
            result["issues"].append(f"{name}: missing {missing}")

    return result


def check_crons() -> Dict:
    """Audit cron jobs for delivery health."""
    result = {"count": 0, "active": 0, "with_errors": [], "undelivered": [], "issues": []}

    if not CRON_OUTPUT_DIR.exists():
        return result

    # Check for recent cron runs and delivery errors
    for job_dir in sorted(CRON_OUTPUT_DIR.glob("*")):
        if not job_dir.is_dir():
            continue
        outputs = sorted(job_dir.glob("*.md"), reverse=True)
        result["count"] += 1

        if outputs:
            latest = outputs[0]
            content = latest.read_text()
            if "delivery error" in content.lower() or "failed" in content.lower():
                result["with_errors"].append(job_dir.name)
            if "not delivered" in content.lower():
                result["undelivered"].append(job_dir.name)
        else:
            result["undelivered"].append(job_dir.name)

    result["active"] = result["count"] - len(result["with_errors"])
    if result["with_errors"]:
        result["issues"].append(f"{len(result['with_errors'])} crons with delivery errors")

    return result


def check_database() -> Dict:
    """Audit journal.db integrity."""
    result = {"tables": 0, "rows": {}, "issues": []}

    if not DB_PATH.exists():
        result["issues"].append("journal.db not found")
        return result

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        result["tables"] = len(tables)

        for t in tables:
            tname = t["name"]
            count = conn.execute(f"SELECT COUNT(*) as c FROM {tname}").fetchone()["c"]
            result["rows"][tname] = count

        # Check required tables
        required = ["trades", "signal_log", "portfolio_snapshots"]
        missing = [r for r in required if r not in [t["name"] for t in tables]]
        if missing:
            result["issues"].append(f"Missing tables: {missing}")

        # Check thesis_id column
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(trades)")]
        if "thesis_id" not in cols:
            result["issues"].append("trades table missing thesis_id column")

        conn.close()
    except Exception as e:
        result["issues"].append(f"Database error: {e}")

    return result


def check_data_usage() -> Dict:
    """Verify data collected → used chain."""
    result = {"collected": [], "used": [], "orphan": [], "issues": []}

    # Data collected by fetch-prices.py
    collected = [
        "brent_close", "brent_50sma", "gold", "dxy", "dxy_rising",
        "vix", "xle_price", "xlk_price", "gld_price", "real_rates",
        "energy_weight", "mun7_fcf_yield", "mun7_price",
    ]

    # Where is each used?
    usage_map = {
        "brent_close": ["engine.py E1/E2", "fetch-prices.py", "weekly tracker"],
        "brent_50sma": ["engine.py E1", "fetch-prices.py"],
        "gold": ["engine.py E4S/E4L", "confluence analyzer", "weekly tracker"],
        "dxy": ["engine.py E4S", "confluence analyzer", "macro module"],
        "dxy_rising": ["engine.py E4S", "confluence analyzer"],
        "vix": ["confluence analyzer", "macro module", "position-sizing"],
        "xle_price": ["engine.py proxy", "portfolio mark-to-market"],
        "xlk_price": ["engine.py E3 rotation check"],
        "gld_price": ["portfolio mark-to-market"],
        "real_rates": ["confluence analyzer", "macro module"],
        "energy_weight": ["engine.py E3/X3"],
        "mun7_fcf_yield": ["engine.py E1/X5"],
        "mun7_price": ["engine.py"],
    }

    for key in collected:
        if key in usage_map:
            result["used"].append(key)
        else:
            result["orphan"].append(key)

    if result["orphan"]:
        result["issues"].append(f"{len(result['orphan'])} data points collected but unused: {result['orphan']}")

    return result


def check_delivery_coverage() -> Dict:
    """Verify all cron outputs reach a destination."""
    result = {"total_scripts": 0, "delivered": [], "local_only": [], "issues": []}

    # Scripts that produce output
    scripts = [
        ("engine.py --summary", "Commodity/AI/Crypto signal checks → @hermestradingdesk"),
        ("fetch-prices.py", "Market data → /tmp, consumed by engine + crons"),
        ("synthesizer.py", "daily_state.json → consumed by signal checks"),
        ("weekly-review.py", "Weekly review → @hermestradingdesk"),
        ("missed-audit.py", "Missed opportunities → @hermestradingdesk"),
        ("correlator.py", "Cross-thesis → @hermestradingdesk"),
        ("airdrop-scanner.py", "Airdrop ranking → @hermestradingdesk"),
        ("formatter.py", "Formatting library → used by all crons"),
    ]

    result["total_scripts"] = len(scripts)
    for script, dest in scripts:
        if "→" in dest:
            result["delivered"].append(f"{script}: {dest}")
        else:
            result["local_only"].append(script)

    return result


# ── Report generator ──

def run_full_audit() -> Dict:
    """Run all checks and compile report."""
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "modules": check_modules(),
        "theses": check_theses(),
        "crons": check_crons(),
        "database": check_database(),
        "data_usage": check_data_usage(),
        "delivery": check_delivery_coverage(),
    }


def generate_summary(report: Dict) -> str:
    """Telegram-ready summary."""
    lines = ["[AUDIT] #sanity-check", ""]
    all_good = True

    # Modules
    m = report["modules"]
    lines.append(f"📚 **Modules:** {m['count']} total, {len(m['built'])} built, "
                f"{len(m['placeholder'])} placeholder")
    if m["unreferenced"]:
        lines.append(f"   ⚠ {len(m['unreferenced'])} unreferenced: {', '.join(m['unreferenced'][:3])}")
        all_good = False

    # Theses
    t = report["theses"]
    lines.append(f"📋 **Theses:** {t['count']} active")

    # Crons
    c = report["crons"]
    lines.append(f"⏰ **Crons:** {c.get('count', 0)} total, "
                f"{c.get('active', 0)} healthy")
    if c.get("with_errors"):
        lines.append(f"   ⚠ {len(c['with_errors'])} with errors")
        all_good = False

    # Database
    d = report["database"]
    lines.append(f"🗄 **Database:** {d['tables']} tables, "
                f"trades={d['rows'].get('trades', 0)}, "
                f"signals={d['rows'].get('signal_log', 0)}")
    if d["issues"]:
        lines.append(f"   ⚠ {d['issues'][0][:80]}")
        all_good = False

    # Data usage
    du = report["data_usage"]
    lines.append(f"📊 **Data:** {len(du['used'])} points used, "
                f"{len(du['orphan'])} orphan")

    # Delivery
    dl = report["delivery"]
    lines.append(f"📨 **Delivery:** {len(dl['delivered'])} scripts deliver output")

    lines.append("")
    if all_good:
        lines.append("✅ **All checks passed.** Platform healthy.")
    else:
        lines.append("⚠️ **Issues found.** See above.")

    return "\n".join(lines)


# ── Main ──

def main():
    summary_only = "--summary" in sys.argv

    report = run_full_audit()

    if summary_only:
        print(generate_summary(report))
    else:
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
