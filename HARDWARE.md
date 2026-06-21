# Connecting Baymax Software to the Real Booster K1

Everything in this repo was built to run against real hardware with one config change.
The pipeline (Band → agents → FINAL_COMMAND → command_bridge) does not change at all.

---

## What You Need

1. The Booster K1 powered on and standing
2. A machine on the same network as the K1 (the K1 connects over DDS/UDP)
3. Ubuntu 22.04 (WSL or native) with `booster_robotics_sdk_python` installed
4. `.env` with `RobotID` and `RobotBandAPI` filled in

---

## Step 1 — Find the Robot's IP

The K1 has an onboard Jetson. On the same WiFi network, find its IP:

```bash
# Option A: check the router's DHCP table
# Option B: the K1 may broadcast its hostname — try pinging it
ping booster-k1.local

# Option C: ask the Booster team at the booth — they know the IP
```

Set it in your shell:
```bash
export BOOSTER_ROBOT_ADDR=<k1_ip>   # e.g. 192.168.1.42
```

---

## Step 2 — Verify the SDK Can Reach It

Run the smoke test from the Ubuntu 22.04 distro:

```bash
# In the 22.04 WSL distro, with baymax-venv active:
source ~/baymax-venv/bin/activate
cd /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/robot

BOOSTER_ROBOT_ADDR=<k1_ip> python sdk_smoke_test.py
```

Expected output:
```
[smoke] connecting to DDS endpoint <ip> ...
[smoke] connected; mode=Walking. Sending motion ...
[smoke] walk forward: Move(0.3, 0.0, 0.0) for 2.0s
[smoke] turn left in place: Move(0.0, 0.0, 0.4) for 2.0s
[smoke] WaveHand (greeting)
[smoke] stop + damp
[smoke] done.
```

If you see this, the K1 will walk and wave. The full pipeline will work.

---

## Step 3 — Run the Full Live Pipeline

### On the Ubuntu 22.04 machine (robot bridge):
```bash
source ~/baymax-venv/bin/activate
cd /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/robot

# Load .env so RobotID/RobotBandAPI are available
source ../.env   # or: export $(cat ../.env | grep -v '#' | xargs)

BOOSTER_ROBOT_ADDR=<k1_ip> python command_bridge.py band real
```

### On your Mac (all 8 agents + vision):
```bash
cd /path/to/Calhacks
bash scripts/mac/start_all.sh
```

### On your Mac (dashboard):
```bash
python dashboard.py
# Open http://localhost:8000
```

The pipeline is now live: camera → Vision → Band → 8 agents → FINAL_COMMAND → command_bridge → K1.

---

## Step 4 — Verify It's Working

1. Dashboard at `http://localhost:8000` should show agent cards activating
2. End-to-end latency number should appear in the top right after the first cycle
3. The K1 should start moving based on what the camera sees

---

## Swapping Between Targets (sim vs hardware)

| Target | Command | Notes |
|--------|---------|-------|
| Log only (no robot) | `python command_bridge.py band stub` | Safe for testing agents |
| Booster Studio (sim) | `python command_bridge.py band real` | `BOOSTER_ROBOT_ADDR=127.0.0.1`, Studio must be running in same WSL distro |
| Real K1 | `python command_bridge.py band real` | `BOOSTER_ROBOT_ADDR=<k1_ip>` |
| MuJoCo fallback | `python command_bridge.py band mujoco --view` | Mac-compatible, no SDK needed |

Only the `BOOSTER_ROBOT_ADDR` env var changes. Everything else is identical.

---

## If the K1 Won't Connect

- **DDS domain mismatch**: SDK uses domain 0 by default. K1 firmware must also be on domain 0.
- **Firewall**: UDP ports 7400–7500 must be open between your machine and the K1.
- **Wrong network**: Confirm both machines are on the same subnet (`ip route` on the K1 Jetson).
- **Mode not set**: The K1 must be in `kWalking` mode for `Move()` to do anything. `sdk_smoke_test.py` sets this automatically.
- **Safety hold**: If the K1 was emergency-stopped, it enters `kDamping`. Call `ChangeMode(kWalking)` again — `B1LocoClientSink` does this automatically when the next `Move()` is non-zero.

---

## Hardware-Specific Limits

- **Max safe speed**: `vx=0.3 m/s` forward, `vyaw=0.4 rad/s` turning — already tuned in `COMMAND_MAP` in `command_bridge.py`
- **Arm reach**: `MoveHandEndEffector` targets are in the robot's body frame. Posture positions in `b1_loco_client_sink.py` are initial estimates — tune against the real robot if arms look wrong.
- **WaveHand**: `client.WaveHand(HandAction.kHandOpen)` is a built-in preset. Works on real hardware and Studio.
- **Emergency**: `ChangeMode(kDamping)` locks all joints. The robot will not fall but won't move until `kWalking` is set again.
