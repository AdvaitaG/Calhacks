# Booster K1 SDK → Booster Studio (real presets in sim)

Working notes. Goal: drive the K1 in a simulator using the **real Booster SDK**
(`B1LocoClient`) so motion comes from Booster's **firmware presets** (real walk
cycle, `WaveHand`, `MoveHandEndEffector`) — not the hand-rolled kinematic poses
in `robot/sim_mujoco.py`.

## Why not MuJoCo
`robot/sim_mujoco.py` never imports the SDK — it just *mimics* the `B1LocoClient`
method names and animates the model with hardcoded arm/leg poses. Good enough for
a fallback demo, but the motion is ours, not Booster's. Booster Studio runs the
real control stack, so `client.Move(vx,vy,vyaw)` produces the genuine gait.

## Architecture
```
FINAL_COMMAND (Band) → command_bridge.py → B1LocoClientSink
                                              │  (b1_loco_client_sink.py)
                                              ▼  Fast-DDS, domain 0, 127.0.0.1
                                         Booster Studio  ← runs firmware presets
```
The SDK is a **client**; Booster Studio is the **server/controller** it talks to
over Fast-DDS. Same interface points at the real K1 by changing the address.

## Hard requirement: Ubuntu 22.04
The SDK only builds/runs on **Ubuntu 18/20/22** (target: 22.04 + gcc 11.4). It
will NOT work on 24.04 (proven: builds on 22.04, structurally impossible on 24.04).
So all SDK + Studio work lives in a dedicated **Ubuntu-22.04 WSL distro**.

- Created with: `wsl --install -d Ubuntu-22.04`
- Make default (optional): `wsl --set-default Ubuntu-22.04`
- The 24.04 distro is fine for everything else (agents, camera, MuJoCo fallback).

## Environment gotchas (these bit us)
- **Repo is on the Windows mount** (`/mnt/c/.../Calhacks`). Reading/running code
  there is fine, but **`git clone`, `python -m venv`, and builds fail on /mnt/c**
  (DrvFs can't do Unix chmod/symlinks). So: build the SDK and create venvs in the
  **Linux home (`~`)**, not on `/mnt/c`.
- **Terminal mangles long/multi-line pastes** (jams newlines mid-command). Run
  setup via the script files in `scripts/`, or one short line at a time.

## Status
- [x] SDK C++ libs + Fast-DDS installed on 22.04 (`sudo ./install.sh` succeeded).
- [ ] Python binding `booster_robotics_sdk_python` — last step was the pybind11
      CMake path fix; gate is `python3 -c "import booster_robotics_sdk_python"`.
- [ ] Python venv on 22.04 — via `scripts/setup_22.sh` (venv lives in `~`).
- [ ] **Booster Studio installed** — download is in the login-gated K1 manual
      (we own a K1, so we have access): https://booster.feishu.cn/wiki/E3q5wF5SnitXZgkY18Uc8odBnXb
- [ ] Smoke test connects to Studio: `robot/sdk_smoke_test.py`.
- [ ] Full pipeline → Studio: `python command_bridge.py band real`.

## Key files
| File | Role |
| ---- | ---- |
| `robot/sdk_smoke_test.py` | Minimal standalone SDK test — walk/turn/wave/damp vs 127.0.0.1. Verifies the SDK↔Studio link with no Band/agents. |
| `robot/b1_loco_client_sink.py` | Real SDK sink (`B1LocoClientSink`). `Move`/`damp`/`WaveHand`/`apply_actions`. Already written; targets `BOOSTER_ROBOT_ADDR` (default 127.0.0.1). |
| `robot/command_bridge.py` | Bridge: FINAL_COMMAND → velocity → sink. `python command_bridge.py band real`. |
| `robot/sim_mujoco.py` | No-SDK MuJoCo fallback demo (`python sim_mujoco.py --view`). |
| `scripts/setup_22.sh` | Builds the Python venv in `~` on the 22.04 distro. |

## Next steps (in order)
1. In the 22.04 distro: `bash /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/scripts/setup_22.sh`
2. Finish the SDK Python binding until `import booster_robotics_sdk_python` works.
3. Open the K1 manual, download + install **Booster Studio**, load a K1 scene, press play.
4. Confirm Studio's connect address (likely `127.0.0.1`); set `BOOSTER_ROBOT_ADDR` if different.
5. `python3 robot/sdk_smoke_test.py` → K1 should walk/turn/wave in Studio.
6. `python command_bridge.py band real` → live pipeline drives Studio.

## Fallback if Studio is blocked
`socrob/booster_webots_sim` (open-source Docker: Webots + Booster Control Runner +
Fast-DDS) gives the same real presets without the gated download — needs Docker
Desktop with WSL integration.
