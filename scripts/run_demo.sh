#!/bin/bash
# ============================================================================
# ONE-COMMAND BAYMAX DEMO  (run in ONE terminal on the Ubuntu 22.04 distro)
#
#   bash scripts/run_demo.sh
#
# Brings up the whole pipeline in order, in this one terminal:
#   fresh Band room -> Webots (T1 world) -> control runner -> agents + camera
#   -> listener (drives the robot). Ctrl-C stops EVERYTHING cleanly.
#
# Prereq (once):  bash scripts/setup_demo_venv.sh
# Tuning:  BAYMAX_SPEED=1.2 bash scripts/run_demo.sh   (faster; 0.8 = safer)
# ============================================================================
# (no `set -u`: env.sh expands $LD_LIBRARY_PATH/$PATH which may be unset)
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM="$HOME/booster_sim"
VENV="$HOME/baymax-bridge"
PY="$VENV/bin/python"
RUNNER="$SIM/sim_control/booster-runner-webots-full-0.0.10.run"
WORLD="$SIM/worlds/T1_release.wbt"

export PYTHONUNBUFFERED=1
source "$SIM/env.sh"            # WEBOTS_HOME, FastDDS profile, PATH
mkdir -p "$REPO/logs"
cd "$REPO"

pids=()
cleanup() { echo; echo "[demo] stopping everything ..."; kill "${pids[@]}" 2>/dev/null; }
trap cleanup EXIT INT TERM

# 0. Kill ANY lingering agents / camera / listener from previous runs FIRST.
# They share agent identities (ConductorID, ...) with this run; a zombie stuck on
# a deleted room makes Band split/misroute scenes between it and the live agent,
# so the Conductor silently never acts. One clean instance per identity is the fix.
echo "[demo] 0/5  killing stale agents/camera/listener/sim from previous runs ..."
pkill -f 'bin/python agents/' 2>/dev/null
pkill -f 'bin/python .*sim_camera' 2>/dev/null
pkill -f 'bin/python command_bridge' 2>/dev/null
pkill -f 'booster-runner-webots' 2>/dev/null   # stale control runner (DDS conflict)
pkill -f '[/ ]mck' 2>/dev/null                 # runner's extracted control binary
pkill -f 'webots.*T1_release' 2>/dev/null       # stale Webots window
sleep 3

echo "[demo] 1/5  fresh Band room (so the Conductor isn't on a stale room) ..."
"$PY" clean_and_reset.py 2>&1 | tail -n 3

echo "[demo] 2/5  launching Webots — a window opens; it auto-plays. (~22s) ..."
webots --mode=realtime "$WORLD" > logs/webots.log 2>&1 & pids+=($!)
sleep 22                        # Webots load + world start (also covers Band cooldown)

echo "[demo] 3/5  starting the control runner (balance/gait) ..."
"$RUNNER" > logs/runner.log 2>&1 & pids+=($!)
sleep 8

echo "[demo] 4/5  starting the LISTENER first (stands the robot, connects to Band, waits) ..."
( cd robot && "$PY" command_bridge.py band real ) > logs/listener.log 2>&1 & pids+=($!)
echo "[demo]      ~16s for the robot to stand + the listener to be ready BEFORE the brain ..."
sleep 16

echo "[demo] 5/5  starting the brain (8 agents + camera) — decisions now drive the robot."
"$PY" agents/vision_agent.py > logs/vision.log 2>&1 & pids+=($!)
for a in conductor upper_left upper_right lower threat spine safety; do
  "$PY" "agents/$a.py" > "logs/$a.log" 2>&1 & pids+=($!)
done
( cd robot && "$PY" sim_camera.py ) > logs/sim_camera.log 2>&1 & pids+=($!)

echo "[demo] ----> live robot output below. If the robot is frozen, click Play in Webots."
echo "[demo] ----> Ctrl-C stops the WHOLE demo."
tail -n +1 -f logs/listener.log       # show listener output; trap cleans up all on Ctrl-C
