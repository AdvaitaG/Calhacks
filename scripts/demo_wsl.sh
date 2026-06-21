#!/bin/bash
# Full Baymax pipeline demo in WSL: all agents + synthetic camera + the bridge
# driving the K1 in a MuJoCo viewer, from real Conductor decisions.
#
#   bash scripts/demo_wsl.sh
#
# Stops everything on Ctrl-C. If the Band room fills up (1000 msgs) over many
# runs, run `python clean_and_reset.py` once to get a fresh room.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
export PYTHONUNBUFFERED=1
mkdir -p logs
pids=()
cleanup() { echo; echo "stopping..."; kill "${pids[@]}" 2>/dev/null; }
trap cleanup EXIT INT TERM

echo "starting agents + synthetic camera (logs/) ..."
for a in vision conductor upper_left upper_right lower threat spine safety; do
  $PY "agents/$a.py" > "logs/$a.log" 2>&1 & pids+=($!)
done
( cd robot && exec ../$PY sim_camera.py ) > logs/sim_camera.log 2>&1 & pids+=($!)

echo "warming up 12s (agents connect to Band, camera starts) ..."
sleep 12

echo "launching bridge + K1 viewer — real decisions drive the robot. Ctrl-C to stop."
cd robot && exec ../$PY command_bridge.py band mujoco --view
