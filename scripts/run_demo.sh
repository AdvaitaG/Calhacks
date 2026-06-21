#!/bin/bash
# ============================================================================
# ONE-COMMAND BAYMAX DEMO  (run in ONE terminal on the Ubuntu 22.04 distro)
#
#   bash /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/scripts/run_demo.sh
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
REPO=/mnt/c/Users/mradi/OneDrive/Desktop/Calhacks
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

echo "[demo] 1/5  fresh Band room (so the Conductor isn't on a stale room) ..."
"$PY" clean_and_reset.py 2>&1 | tail -n 3

echo "[demo] 2/5  launching Webots — a window opens; it auto-plays. (~22s) ..."
webots --mode=realtime "$WORLD" > logs/webots.log 2>&1 & pids+=($!)
sleep 22                        # Webots load + world start (also covers Band cooldown)

echo "[demo] 3/5  starting the control runner (balance/gait) ..."
"$RUNNER" > logs/runner.log 2>&1 & pids+=($!)
sleep 8

echo "[demo] 4/5  starting the brain (8 agents + synthetic camera) ..."
"$PY" agents/vision_agent.py > logs/vision.log 2>&1 & pids+=($!)
for a in conductor upper_left upper_right lower threat spine safety; do
  "$PY" "agents/$a.py" > "logs/$a.log" 2>&1 & pids+=($!)
done
( cd robot && "$PY" sim_camera.py ) > logs/sim_camera.log 2>&1 & pids+=($!)
sleep 12                        # agents connect, first scenes flow

echo "[demo] 5/5  starting the listener — robot stands, then walks on decisions."
echo "[demo] ---> If the robot stays frozen, click Play ▶ in the Webots window. <---"
echo "[demo] ---> Ctrl-C here stops the whole demo.                              <---"
cd robot
"$PY" command_bridge.py band real      # foreground; trap cleans up the rest on Ctrl-C
