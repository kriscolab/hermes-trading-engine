#!/bin/bash
# intraday-executor.sh — Execute intraday signals if NEW signals present
# Called by cron every 5 min. Reads /tmp/intraday_signals.json
# Runs engine.py --thesis intraday --execute only when signal file CHANGED.
# Silent when idle — no output = no delivery to Telegram.
# Output only trade executions/closes, not full portfolio dumps.
#
# IDEMPOTENT: same signal file hash = silent. Only fires once per unique signal set.
# COOLDOWN: max 1 delivery per 30 min (COOLDOWN_SEC=1800). Prevents spam.

set -e

SCRIPT_DIR="/home/hermes-pilot/vault/wiki/trading"
SIGNAL_FILE="/tmp/intraday_signals.json"
HASH_FILE="/tmp/intraday_last_hash.txt"
COOLDOWN_FILE="/tmp/intraday_last_delivery.txt"
ENGINE="$SCRIPT_DIR/paper-trader/engine.py"
COOLDOWN_SEC=1800  # 30 minutes

# ── Guard 1: signal file must exist ──
if [ ! -f "$SIGNAL_FILE" ]; then
    exit 0
fi

# ── Guard 2: must have signals ──
SIGNAL_COUNT=$(python3 -c "import json; d=json.load(open('$SIGNAL_FILE')); print(d.get('signals_generated', 0))" 2>/dev/null || echo "0")

if [ "$SIGNAL_COUNT" -eq 0 ]; then
    exit 0
fi

# ── Guard 3: idempotency — only fire on NEW signal content ──
CURRENT_HASH=$(md5sum "$SIGNAL_FILE" | awk '{print $1}')

if [ -f "$HASH_FILE" ]; then
    LAST_HASH=$(cat "$HASH_FILE")
    if [ "$CURRENT_HASH" = "$LAST_HASH" ]; then
        exit 0  # Same signals as last tick — already reported, stay silent
    fi
fi

# Record that we're about to process these signals
echo "$CURRENT_HASH" > "$HASH_FILE"

# ── Guard 4: cooldown — max 1 delivery per 30 min ──
if [ -f "$COOLDOWN_FILE" ]; then
    LAST_DELIVERY=$(cat "$COOLDOWN_FILE")
    NOW=$(date +%s)
    ELAPSED=$((NOW - LAST_DELIVERY))
    if [ "$ELAPSED" -lt "$COOLDOWN_SEC" ]; then
        exit 0  # Within cooldown window — skip
    fi
fi

# ── Execute ──
cd "$SCRIPT_DIR/paper-trader"
python3 ../scripts/fetch-prices.py --portfolio > /dev/null 2>&1 || true

# Run engine and filter to only executed/closing lines (not portfolio dumps)
OUTPUT=$(python3 engine.py --thesis intraday --execute --data /tmp/live_market_data.json 2>&1)
# Lines starting with spaces are position listings — skip them
EXEC_LINES=$(echo "$OUTPUT" | grep -v '^  ' | grep -E '✅|🔴|⚡|⏭|⚠|CLOSED|ENTERED' || true)

if [ -n "$EXEC_LINES" ]; then
    echo "⚡ INTRADAY — $(date '+%H:%M IST')"
    echo "$EXEC_LINES"
    # Record delivery timestamp for cooldown
    date +%s > "$COOLDOWN_FILE"
fi
