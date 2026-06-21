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
- [x] **Python binding `booster_robotics_sdk_python` installed — `SDK ok`.**
      `python3 -c "import booster_robotics_sdk_python"` works.
- [ ] **Booster Studio installed** — download is in the login-gated K1 manual
      (we own a K1, so we have access): https://booster.feishu.cn/wiki/E3q5wF5SnitXZgkY18Uc8odBnXb
- [ ] Smoke test connects to Studio: `robot/sdk_smoke_test.py`.
- [ ] Full pipeline → Studio: `python command_bridge.py band real`.

### How the SDK actually got installed (avoid the dead ends we hit)
1. **Ubuntu 22.04 only.** 24.04 cannot build it. Clone into the **Linux home**
   (`~`), never `/mnt/c` (DrvFs breaks git/builds).
2. `cd ~/booster_robotics_sdk && sudo ./install.sh`  (installs Fast-DDS + C++ libs)
3. `pip install --user booster_robotics_sdk_python`  ← **this is the one that works.**
   It builds from source with pip's build isolation, which pulls the correct
   pybind11 automatically. Do NOT build the Python binding by hand with cmake —
   Ubuntu's apt pybind11 (2.9.1) is too old and fails on `SendApiRequest`; the
   pip build uses the right (latest) pybind11 and compiles cleanly.
   - There is NO prebuilt wheel on PyPI (source-only), so `--only-binary` fails.
   - `scripts/build_sdk_22.sh` was the manual route — kept for reference, but the
     pip install above is simpler and what succeeded.
4. Verify: `python3 -c "import booster_robotics_sdk_python; print('SDK ok')"`

Note: the venv (`scripts/setup_22.sh`) is NOT needed for the SDK/smoke test —
the SDK installs into system `python3`. The venv only matters later for the full
Band pipeline, which has its own Python 3.10-vs-3.11 (`band-sdk`) split to solve.

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

## BLOCKER (2026-06-21): no K1 sim runner access
A K1 sim with real presets needs Booster's **K1 control runner**
(`booster-runner-full-webots-k1-0.0.1.run`), which is gated behind the K1
**owner's** Booster account. No one on the team owns the K1 / has wiki access,
so this file is unobtainable for now → the real-preset K1 sim is **blocked by
access**, not by setup. The SDK itself is installed and ready (`SDK ok`); we're
blocked on exactly one external file.

Notes on the alternatives we checked:
- `socrob/booster_webots_sim` (open Docker) DOES give real `B1LocoClient` presets
  (its `sdk-client` = `b1_loco_example_client`, `start-runner` = Booster control
  runner) — BUT it ships only the **T1** (worlds `T1_*.wbt`, T1 runners). There is
  **no open-source K1 runner**. So it simulates a T1, not the K1, and is a heavy
  multi-GB GPU build (ROS2 Humble + SDK + Webots).
- There is no public K1 walk checkpoint for a MuJoCo RL gait either (see
  [[k1-sdk-presets]]) — that path needs GPU training.

### Decision
- **Demo path:** ship the existing no-SDK MuJoCo K1 (`robot/sim_mujoco.py --view`).
  Correct robot, works today, motion is approximated but reads fine in a demo.
- **To unlock real presets:** get the K1 `.run` or wiki login from whoever
  *provided* the K1 (Calhacks organizer / Booster sponsor rep / the buyer). The
  SDK side is done, so it's then a drop-in.
