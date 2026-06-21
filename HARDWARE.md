# Connecting Baymax to the Real Booster K1

## How the Connection Works

The Booster SDK communicates over **Fast-DDS** (a real-time pub/sub protocol over UDP).
`ChannelFactory.Instance().Init(0, <ip>)` opens a DDS session on domain 0 to the given IP:

- `127.0.0.1` → Booster Studio running locally (sim)
- `<robot_ip>` → real K1 over WiFi/Ethernet

**That one env var is the only difference between sim and hardware:**

```bash
# Sim (Booster Studio on localhost)
BOOSTER_ROBOT_ADDR=127.0.0.1 python command_bridge.py band real

# Real K1
BOOSTER_ROBOT_ADDR=192.168.1.42 python command_bridge.py band real
```

Everything else — Band agents, FINAL_COMMAND parsing, arm actions, gait — is identical.

---

## Step 1 — Physical Startup Sequence

The K1 must be in the right mode before the SDK can move it.

```
Power on K1
  └─> Robot initializes in kDamping (joints locked, won't fall)
        └─> Call ChangeMode(kPrepare)   ← robot stands up slowly
              └─> Call ChangeMode(kWalking) ← locomotion controller active
                    └─> Call Move() / MoveHandEndEffector() freely
```

`B1LocoClientSink.__init__()` already calls `ChangeMode(kWalking)` on startup.
If the robot was emergency-stopped (kDamping), the next non-zero `Move()` call
automatically calls `ChangeMode(kWalking)` first — also already handled in the sink.

---

## Step 2 — Find the Robot's IP

The K1 Jetson connects to the same network as your laptop. Find its IP:

```bash
# If the booth has a router, check its DHCP table
# Or: scan the subnet
nmap -sn 192.168.1.0/24 | grep -i booster

# Or: the Booster team at the booth will know — just ask
```

Set it:
```bash
export BOOSTER_ROBOT_ADDR=<k1_ip>
```

---

## Step 3 — Network Requirements

- Both machines must be on the **same subnet** (same WiFi or Ethernet switch)
- DDS uses **UDP multicast/unicast** — no special ports needed on most LANs
- If on a managed network (conference WiFi): multicast may be blocked. Use a dedicated router or hotspot between your laptop and the K1's Jetson
- Firewall: UDP ports 7400–7500 open between your machine and the K1

---

## Step 4 — Verify With the Smoke Test

Before running the full pipeline, confirm the DDS link:

```bash
# On Ubuntu 22.04 (WSL or native), baymax-venv active:
source ~/baymax-venv/bin/activate
cd /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/robot

BOOSTER_ROBOT_ADDR=<k1_ip> python sdk_smoke_test.py
```

Expected: robot walks forward 2s, turns left 2s, waves. If it moves, the SDK link is good.

---

## Step 5 — Run the Full Pipeline

### On Ubuntu 22.04 (robot bridge):
```bash
source ~/baymax-venv/bin/activate
cd /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks

# Load credentials
export $(grep -v '^#' .env | xargs)
export BOOSTER_ROBOT_ADDR=<k1_ip>

python robot/command_bridge.py band real
```

### On Mac (all agents + vision):
```bash
bash scripts/mac/start_all.sh
```

### On Mac (dashboard):
```bash
python dashboard.py
# Open http://localhost:8000
```

---

## Arm Positions — Real Coordinates

These are the actual body-frame coordinates from the SDK examples.
`x` = forward, `y` = left (+) / right (-), `z` = up.

### Guide Arm (RIGHT arm — holds person's hand)

| Action | Position (x, y, z) | Orientation (r, p, y) | Notes |
|--------|--------------------|-----------------------|-------|
| HOLD_STEADY | (0.28, -0.25, 0.05) | (0.0, 0.0, 0.0) | Neutral at side |
| FORWARD_PUSH | (0.42, -0.20, 0.10) | (0.0, 0.0, 0.0) | Arm extended forward |
| GENTLE_LEFT_PULL | (0.32, -0.12, 0.05) | (0.0, 0.0, 0.0) | Arm pulls toward center |
| GENTLE_RIGHT_PULL | (0.32, -0.35, 0.05) | (0.0, 0.0, 0.0) | Arm pulls outward right |
| RELEASE | (0.20, -0.25, -0.10) | (0.0, 0.0, 0.0) | Arm lowers and opens |

### Free Arm (LEFT arm — sweeps, barriers, halts)

| Action | Position (x, y, z) | Orientation (r, p, y) | Notes |
|--------|--------------------|-----------------------|-------|
| SWEEP | (0.35, 0.25, -0.10) | (-1.57, -1.57, 0.0) | Low sweep arc, cane-like |
| MIRROR | (0.35, 0.25, 0.10) | (-1.57, -1.57, 0.0) | Matches guide direction |
| BARRIER | (0.40, 0.30, 0.15) | (-1.57, 0.0, 0.0) | Extended out, palm forward |
| HALT_EXTEND | (0.25, 0.30, 0.30) | (0.0, -1.0, 0.0) | Raised high, palm out |

These are initial estimates — tune against the real robot once connected. Use
`client.GetFrameTransform(Frame.kBody, Frame.kLeftHand, transform)` to verify
actual hand position vs commanded position.

---

## Mode Reference

```python
from booster_robotics_sdk_python import RobotMode

RobotMode.kDamping   # all joints locked — safe hold, robot won't fall
RobotMode.kPrepare   # robot stands up from damping
RobotMode.kWalking   # locomotion controller active — Move() works
RobotMode.kCustom    # low-level joint control (arm SDK example uses this)
```

---

## Move() Reference

```python
client.Move(vx, vy, vyaw)
# vx   = forward speed m/s  (positive = forward)  — max safe ~0.8
# vy   = lateral speed m/s  (positive = left)      — max safe ~0.2
# vyaw = yaw rate rad/s     (positive = turn left) — max safe ~0.4
# Must be called repeatedly at ~20 Hz — it is a setpoint, not a one-shot
```

---

## Head Control

```python
client.RotateHead(pitch, yaw)
# pitch: down=1.0, up=-0.3
# yaw:   left=0.785 (~45°), right=-0.785
# center: (0.0, 0.0)
```

Point the camera at a scene by rotating the head before vision captures a frame.

---

## Fallback Hierarchy (if hardware fails at the booth)

```
Real K1 (BOOSTER_ROBOT_ADDR=<ip>)
   └─> Booster Studio sim (BOOSTER_ROBOT_ADDR=127.0.0.1, Ubuntu 22.04 WSL)
         └─> MuJoCo kinematic sim (python command_bridge.py band mujoco --view, Mac)
               └─> Dashboard only (python dashboard.py — shows pipeline thinking live)
```

Each fallback is one env var or one argument change. The agents and Band pipeline
never change regardless of which level you're at.
