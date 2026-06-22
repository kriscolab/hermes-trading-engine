#!/bin/bash
# quant-executor.sh — Execute quant ensemble signals if NEW signals present
# Called by cron every 5 min. Reads /tmp/quant_signals.json ensemble.
# Runs engine.py --thesis quant --execute only when signal file CHANGED
# AND ensemble crosses threshold (>0.25).
# Silent when idle — no output = no delivery to Telegram.
# Output only trade executions/closes, not portfolio dumps.
#
# IDEMPOTENT: same signal file hash = silent. Only fires once per unique signal set.
# COOLDOWN: max 1 delivery per 30 min (COOLDOWN_SEC=1800). Prevents spam.
# NOISE FILTER: strips "already executed"/"skipping" lines — they're not actionable.

set -e

SCRIPT_DIR="/home/hermes-pilot/vault/wiki/trading"
QUANT_FILE="/tmp/quant_signals.json"
HASH_FILE="/tmp/quant_last_hash.txt"
COOLDOWN_FILE="/tmp/quant_last_delivery.txt"
ENGINE="$SCRIPT_DIR/paper-trader/engine.py"
COOLDOWN_SEC=1800  # 30 minutes

# ── Guard 1: signal file must exist ──
if [ ! -f "$QUANT_FILE" ]; then
    exit 0
fi

# ── Guard 2: ensemble threshold must be crossed (>0.25) ──
BEST_SCORE=$(python3 -c "
import json
d = json.load(open('$QUANT_FILE'))
ens = d.get('ensemble', {}).get('signals', {})
if not ens:
    print('0')
else:
    best = max(abs(m['ensemble_score']) for m in ens.values())
    print(f'{best:.3f}')
" 2>/dev/null || echo "0")

PASSES=$(python3 -c "print('1' if float('$BEST_SCORE') > 0.25 else '0')")

if [ "$PASSES" = "0" ]; then
    exit 0
fi

# ── Guard 3: idempotency — only fire on NEW signal content ──
CURRENT_HASH=$(md5sum "$QUANT_FILE" | awk '{print $1}')

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
# Also strip "already executed" / "skipping" lines — they're noise, not signal
OUTPUT=$(python3 engine.py --thesis quant --execute --data /tmp/live_market_data.json 2>&1)
EXEC_LINES=$(echo "$OUTPUT" | grep -v '^  ' | grep -E '✅|🔴|⚡|⚠|CLOSED|ENTERED' | grep -v 'skipping\|already executed' || true)

if [ -n "$EXEC_LINES" ]; then
    echo "🤖 QUANT — $(date '+%H:%M IST')"
    echo "$EXEC_LINES"
    # Record delivery timestamp for cooldown
    date +%s > "$COOLDOWN_FILE"
fi
