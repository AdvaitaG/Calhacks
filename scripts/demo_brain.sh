#!/bin/bash
# The BRAIN half of the full pipeline: the agents + synthetic camera, publishing
# FINAL_COMMANDs to the Band room in .env (BAYMAX_ROOM). Run on the ORIGINAL
# Ubuntu 24.04 distro (its .venv has langchain/band/livekit). The robot-side
# listener — `command_bridge.py band real` on the 22.04 distro — receives those
# commands and drives the Webots sim.
#
#   bash scripts/demo_brain.sh
#
# NOTE: deliberately does NOT run clean_and_reset, so the room stays the one the
# listener already joined. If the conductor lags on a stale room, stop, run
# `python clean_and_reset.py`, restart this AND the listener (both reread .env).
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export PYTHONUNBUFFERED=1
mkdir -p logs
pids=()
cleanup() { echo; echo "stopping brain ..."; kill "${pids[@]}" 2>/dev/null; }
trap cleanup EXIT INT TERM

ROOM=$(grep -oP '(?<=^BAYMAX_ROOM=).*' .env)
echo "starting agents + synthetic camera -> Band room ${ROOM} (logs/ ) ..."
$PY agents/vision_agent.py > logs/vision.log 2>&1 & pids+=($!)
for a in conductor upper_left upper_right lower threat spine safety; do
  $PY "agents/$a.py" > "logs/$a.log" 2>&1 & pids+=($!)
done
( cd robot && exec ../$PY sim_camera.py ) > logs/sim_camera.log 2>&1 & pids+=($!)

echo ""
echo "brain running. Conductor decisions -> Band -> the listener drives the robot."
echo "watch a log:  tail -f logs/conductor.log    (Ctrl-C here stops the brain)"
wait
