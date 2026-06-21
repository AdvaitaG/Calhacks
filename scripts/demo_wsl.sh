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

# Fresh room every run: the 422 mark-processed bug means stale rooms replay old
# scenes and the Conductor lags. clean_and_reset makes an empty room + writes
# BAYMAX_ROOM to .env so every process agrees on it.
echo "creating a fresh Band room (clean_and_reset) ..."
$PY clean_and_reset.py > logs/clean_and_reset.log 2>&1 \
  && grep -i "DONE" logs/clean_and_reset.log || { echo "clean_and_reset failed — see logs/clean_and_reset.log"; exit 1; }
# Band rate-limits reconnecting the same identity right after clean_and_reset
# ("recent supersede"). Wait out the window before the agents reconnect.
echo "cooldown 30s (Band reconnect rate-limit) ..."
sleep 30

echo "starting agents + synthetic camera (logs/) ..."
$PY agents/vision_agent.py > logs/vision.log 2>&1 & pids+=($!)
for a in conductor upper_left upper_right lower threat spine safety; do
  $PY "agents/$a.py" > "logs/$a.log" 2>&1 & pids+=($!)
done
( cd robot && exec ../$PY sim_camera.py ) > logs/sim_camera.log 2>&1 & pids+=($!)

echo "warming up 12s (agents connect to Band, camera starts) ..."
sleep 12

echo "launching bridge + K1 viewer — real decisions drive the robot. Ctrl-C to stop."
cd robot && exec ../$PY command_bridge.py band mujoco --view
