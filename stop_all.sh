#!/usr/bin/env bash
# Stop all Baymax agents started by start_all.sh
ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT/.pids"

if [ ! -f "$PID_FILE" ]; then
    echo "No .pids file found — nothing to stop."
    exit 0
fi

while read -r pid; do
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping PID $pid"
        kill "$pid"
    fi
done < "$PID_FILE"

rm -f "$PID_FILE"
echo "Done."
