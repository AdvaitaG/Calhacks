# Booster Studio Integration — What Adil Needs To Do

## The Situation

The pipeline is: **Band → Conductor → FINAL_COMMAND → `command_bridge.py` → robot**

`command_bridge.py` already has a clean sink abstraction. Right now it supports:
- `stub` — logs velocities, no sim
- `mujoco` — kinematic sim (robot starts collapsed, no real physics walking)

We need to add a `studio` sink that uses the real Booster SDK pointed at Booster Studio.

---

## Why Booster Studio > MuJoCo for this demo

| | MuJoCo (current) | Booster Studio |
|---|---|---|
| Walking | Kinematic hack (fake) | Real built-in locomotion controller |
| Arms | Direct qpos manipulation | `MoveHandEndEffectorV2` (real SDK) |
| SDK needed | No | Yes (`booster_robotics_sdk`) |
| RL policy needed | Yes for real physics, no for our hack | No |
| Looks good | Stiff/floaty | Proper robot motion |

---

## What Adil Needs To Build

### 1. Add a `BoosterStudioSink` class to `robot/command_bridge.py`

This class needs to:
- Import `B1LocoClient`, `RobotMode`, `B1HandIndex`, `MoveHandPosture` (or whatever the posture enum is called in the SDK)
- On init: create `B1LocoClient`, call `ChangeMode(RobotMode.kWalking)`
- Implement `Move(vx, vy, vyaw)` → `client.Move(vx, vy, vyaw)`
- Implement `damp()` → stop or change mode
- Implement `apply_actions(cmd)` → map arm action strings to `MoveHandEndEffectorV2` calls

```python
class BoosterStudioSink:
    def __init__(self, ip: str = "127.0.0.1") -> None:
        from booster_robotics_sdk import B1LocoClient, RobotMode
        self._loco = B1LocoClient(ip)
        self._loco.ChangeMode(RobotMode.kWalking)

    def Move(self, vx, vy, vyaw):
        self._loco.Move(vx, vy, vyaw)

    def damp(self):
        self._loco.Move(0.0, 0.0, 0.0)

    def apply_actions(self, cmd):
        if cmd is None:
            return
        from booster_robotics_sdk import B1HandIndex
        # Map arm action strings -> postures (Adil fills in correct posture values)
        ARM_MAP = {
            "GENTLE_LEFT_PULL":  <POSTURE_FOR_PULL>,
            "GENTLE_RIGHT_PULL": <POSTURE_FOR_PULL>,
            "FORWARD_PUSH":      <POSTURE_FOR_PUSH>,
            "HOLD_STEADY":       <POSTURE_FOR_NEUTRAL>,
            "RELEASE":           <POSTURE_FOR_NEUTRAL>,
            "HALT_EXTEND":       <POSTURE_FOR_EXTEND>,
        }
        la = ARM_MAP.get(cmd.left_arm_action or "HOLD_STEADY", <POSTURE_FOR_NEUTRAL>)
        ra = ARM_MAP.get(cmd.right_arm_action or "HOLD_STEADY", <POSTURE_FOR_NEUTRAL>)
        self._loco.MoveHandEndEffectorV2(la, duration=1.0, hand=B1HandIndex.kLeftHand)
        self._loco.MoveHandEndEffectorV2(ra, duration=1.0, hand=B1HandIndex.kRightHand)
```

### 2. Add `studio` to `_make_sink()` in `command_bridge.py`

```python
def _make_sink(name: str):
    if name == "mujoco":
        from sim_mujoco import MujocoSink, _front_view
        ...
    elif name == "studio":
        ip = os.environ.get("BOOSTER_STUDIO_IP", "127.0.0.1")
        return BoosterStudioSink(ip)
    return B1LocoClientStub()
```

### 3. Add `BOOSTER_STUDIO_IP` to `.env` (optional)

Only needed if Studio runs on a different machine. Default `127.0.0.1` works if it's local.

```
BOOSTER_STUDIO_IP=127.0.0.1
```

---

## How to Run (once integrated)

```bash
# Full live pipeline: Band commands -> Booster Studio
python command_bridge.py band studio

# Test Studio connection without Band (mock commands)
python command_bridge.py mock studio
```

---

## The One Thing Adil Needs to Figure Out

**The posture constants for `MoveHandEndEffectorV2`.**

The SDK has a posture enum (something like `MoveHandPosture` or `B1HandPosture`). Adil needs to check the SDK docs or look at existing Booster examples to find:
- Which posture = arm forward/extended (for FORWARD_PUSH / HALT_EXTEND)
- Which posture = arm out to side (for LEFT_PULL / RIGHT_PULL)  
- Which posture = neutral hang (for HOLD_STEADY)

Everything else in `command_bridge.py` is already written and working — parsing, arbitration, failsafe, Band subscription. Adil only needs to write `BoosterStudioSink` and wire it into `_make_sink()`.

---

## What Does NOT Change

- All 8 Band agents (conductor, upper_left, upper_right, lower, threat, spine, safety, vision) — untouched
- `parse_final_command()` — already handles the `@robot [FINAL_COMMAND] {json}` format
- The failsafe (2s no-command → STOP) — works the same
- `band_command_source()` — already listens for FINAL_COMMANDs from Band
