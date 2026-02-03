#!/bin/bash
# Audit Log Streamer
# - Forwards Discord messages (incoming AND outgoing)
# - Styles internal activity
# Reads configuration from audit-config.json

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/audit-config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE" >&2
    echo "Copy audit-config.sample.json to audit-config.json and fill in values." >&2
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required but not installed." >&2
    exit 1
fi

SESSIONS_DIR="$(jq -r '.sessions_dir' "$CONFIG_FILE")"
FORMAT_SCRIPT="$SCRIPT_DIR/format-log.py"
OUTGOING_SCRIPT="$SCRIPT_DIR/forward-outgoing.py"

# Start outgoing message forwarder in background
python3 "$OUTGOING_SCRIPT" &
OUTGOING_PID=$!

cleanup() {
    kill $OUTGOING_PID 2>/dev/null
    exit 0
}
trap cleanup SIGTERM SIGINT

cd "$SESSIONS_DIR"
current_session=""
current_short=""

tail -n 0 -F *.jsonl 2>/dev/null | while IFS= read -r line; do
    if [[ "$line" =~ ^==\>\ (.+)\.jsonl\ \<== ]]; then
        current_session="${BASH_REMATCH[1]}"
        current_short="${current_session:0:8}"
    elif [ -n "$line" ] && [ -n "$current_session" ]; then
        echo "$line" | python3 "$FORMAT_SCRIPT" "$current_short"
    fi
done
