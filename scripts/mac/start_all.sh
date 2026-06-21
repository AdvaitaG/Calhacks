#!/usr/bin/env bash
# Start all Baymax agents. Logs go to logs/<agent>.log. PIDs saved to .pids.
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$ROOT/logs"
PID_FILE="$ROOT/.pids"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
    echo "Agents may already be running (.pids exists). Run scripts/mac/stop_all.sh first."
    exit 1
fi

cd "$ROOT"

start_agent() {
    local name="$1"
    local script="$2"
    echo "Starting $name..."
    python "$script" > "$LOG_DIR/$name.log" 2>&1 &
    echo "$!" >> "$PID_FILE"
    echo "  $name  PID=$!"
}

# Cortical path: conductor first, then peers, then reflex arc, then safety, then vision last
start_agent "conductor"   "agents/conductor.py"
sleep 0.5
start_agent "threat"      "agents/threat.py"
start_agent "spine"       "agents/spine.py"
start_agent "upper_left"  "agents/upper_left.py"
start_agent "upper_right" "agents/upper_right.py"
start_agent "lower"       "agents/lower.py"
start_agent "safety"      "agents/safety.py"
sleep 1
start_agent "vision"      "agents/vision_agent.py"

echo ""
echo "All agents started. Logs: logs/<agent>.log"
echo "To tail all logs:  tail -f logs/*.log"
echo "To stop:           scripts/mac/stop_all.sh"
