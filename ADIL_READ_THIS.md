# ADIL READ THIS — Interface Contract + LiveKit Setup Guide

This file has two sections:
1. **The interface contract** — what Eshwar sends you and what you do with it
2. **LiveKit setup** — how to get the robot streaming and receiving commands

Do not change the interface contract without talking to Eshwar first.

---

# PART 1 — Eshwar ↔ Adil Interface Contract

## The One Thing Eshwar Sends You

When the Conductor agent finishes a decision cycle (Safety approved), it publishes a final command to the Band room. **You listen for this message and forward it to the robot via LiveKit.**

Eshwar's Conductor posts to Band:

```json
{
  "type": "FINAL_COMMAND",
  "command": "GUIDE_LEFT | GUIDE_RIGHT | MOVE_FORWARD | SLOW_DOWN | STOP | EMERGENCY_STOP",
  "arm_action": "GENTLE_LEFT_PULL | GENTLE_RIGHT_PULL | FORWARD_PUSH | HOLD_STEADY | RELEASE",
  "gait_action": "WALK_NORMAL | WALK_SLOW | PAUSE | STEP_HIGH | STEP_DOWN | HALT",
  "pace_ms": 500,
  "reason": "one sentence — why this command was chosen",
  "path": "CORTICAL | REFLEX",
  "timestamp": 1718900000000
}
```

`path` tells you whether this came from the normal decision cycle (`CORTICAL`) or an emergency bypass (`REFLEX`). Prioritize REFLEX if two commands arrive close together.

---

## Command Definitions

| `command` | What the robot should do |
|-----------|--------------------------|
| `GUIDE_LEFT` | Gentle left pull on user's arm, maintain walking pace |
| `GUIDE_RIGHT` | Gentle right pull on user's arm, maintain walking pace |
| `MOVE_FORWARD` | Continue straight, normal pace |
| `SLOW_DOWN` | Reduce pace, keep direction |
| `STOP` | Halt movement, hold position |
| `EMERGENCY_STOP` | Immediate full stop — always comes via REFLEX path |

---

## The One Thing You Send (Upstream)

You don't send anything to Eshwar's agents directly. Your outbound responsibilities:

1. **Stream robot camera feed** via LiveKit → Advaita's Vision Agent consumes it
2. **Execute FINAL_COMMAND** → translate to UFB robot API call via LiveKit Portal
3. **EMERGENCY_STOP always wins** if two commands arrive close together

---

## How You Listen (Band Side)

Subscribe to Band room `baymax-coordination`. Filter for:
- Sender: `Conductor`
- Message contains `"type": "FINAL_COMMAND"`

No need to @mention or respond. Just consume and execute.

---

## Timing Expectations

- **Normal (CORTICAL) commands:** ~800ms–1s cadence during navigation
- **EMERGENCY_STOP (REFLEX):** ~90ms from hazard detection — highest priority
- **Between commands:** robot holds last state, does not drift

---

## Fallback Behavior

If no command arrives within **2 seconds**:
- Robot **STOPS** and holds position
- Covers agent crashes, network lag, processing delays

---

## Checklist Before Integration

- [ ] Eshwar and Adil have agreed on this file
- [ ] Band subscription filters for `Conductor` + `FINAL_COMMAND`
- [ ] Each `command` value maps to a LiveKit Portal robot API call
- [ ] EMERGENCY_STOP handled as highest priority
- [ ] 2-second timeout fallback implemented
- [ ] Tested with a mock `FINAL_COMMAND` in Band room before live integration

---

---

# PART 2 — LiveKit Setup Guide

Your job: get the robot camera streaming INTO the system, and get commands streaming OUT to the robot. LiveKit Portal is the tool for both.

---

## Step 0 — Claim Free Credits

Redeem code **`BERKELEY-AI-HACKATHON`** at:
👉 https://cloud.livekit.io/projects/p_/redeem

No credit card required. Gets you the "ship" tier free for the hackathon.

---

## Step 1 — Install LiveKit CLI + Authenticate

```bash
brew install livekit-cli        # macOS
# OR
curl -sSL https://get.livekit.io/cli | bash   # Linux

lk cloud auth                   # authenticate with your LiveKit Cloud account
```

---

## Step 2 — Environment Variables

Everything LiveKit needs lives in `.env`:

```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
LIVEKIT_ROOM=baymax-robot       # the shared room name — agree with the team
```

Load from LiveKit CLI:
```bash
lk app env -w -d .env
```

---

## Step 3 — Install Dependencies

```bash
pip install livekit livekit-agents livekit-portal
# or with uv:
uv add livekit livekit-agents livekit-portal
```

---

## Step 4 — The Reference Repo

The embodied-ai-hackathon repo is your bible:
👉 https://github.com/livekit-examples/embodied-ai-hackathon

Key files to read:
- `robot/robot.py` — connects robot to LiveKit, streams camera, receives actions
- `orchestrator/src/agent.py` — the agent side that sends commands
- `portal.yaml` — declares video tracks (camera names, codec, resolution)

---

## Step 5 — Robot Side (Streaming Camera + Receiving Commands)

Pattern from `robot/robot.py` — adapt for UFB hardware:

```python
import asyncio
from livekit.portal import Robot, RobotConfig, Action
import pathlib

CONFIG_PATH = pathlib.Path("portal.yaml")

async def main():
    cfg = RobotConfig.from_yaml_file(CONFIG_PATH, room=LIVEKIT_ROOM)
    robot = Robot(cfg)
    latest_action = {}

    def on_action(action: Action):
        # Fires when orchestrator sends a command
        latest_action.update({k: float(v) for k, v in action.values.items()})

    robot.on_action(on_action)

    token = mint_token("robot", LIVEKIT_ROOM)
    await robot.connect(LIVEKIT_URL, token)

    async for _ in pace(fps=30):
        frame = get_camera_frame()              # your camera capture here
        robot.send_video_frame("front_camera", frame, timestamp_us=now_us())

        if latest_action:
            robot.send_action(latest_action)

asyncio.run(main())
```

---

## Step 6 — portal.yaml (Video Track Config)

```yaml
room: baymax-robot
video_tracks:
  - name: front_camera
    codec: h264         # h264 = WebRTC media path (low latency, shows as video track)
    width: 640
    height: 480
    fps: 30
```

Use `h264` — mjpeg/png/raw ride a byte stream and won't appear as a proper video track for Advaita's Vision Agent.

---

## Step 7 — Sending Commands TO the Robot

When you receive a `FINAL_COMMAND` from Eshwar via Band, translate and fire via LiveKit:

```python
COMMAND_MAP = {
    "GUIDE_LEFT":     {"arm_direction": -1.0, "gait_speed": 0.5},
    "GUIDE_RIGHT":    {"arm_direction":  1.0, "gait_speed": 0.5},
    "MOVE_FORWARD":   {"arm_direction":  0.0, "gait_speed": 1.0},
    "SLOW_DOWN":      {"arm_direction":  0.0, "gait_speed": 0.3},
    "STOP":           {"arm_direction":  0.0, "gait_speed": 0.0},
    "EMERGENCY_STOP": {"arm_direction":  0.0, "gait_speed": 0.0},
}

def on_final_command(command_json: dict):
    cmd = command_json["command"]
    action_values = COMMAND_MAP[cmd]
    robot_operator.send_action(action_values)
```

**Coordinate with UFB team on exact joint value keys their robot accepts.** The keys above are placeholders.

---

## Step 8 — Webcam Fallback (If No UFB Hardware)

```python
import cv2
cap = cv2.VideoCapture(0)   # 0 = default webcam

def get_camera_frame():
    ret, frame = cap.read()
    return frame if ret else None
```

Point at a corridor. Advaita's Vision Agent just needs a real video stream — doesn't care if it's robot or webcam.

---

## Step 9 — Token Minting (Auth)

```python
from livekit import api

def mint_token(identity: str, room: str) -> str:
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.with_identity(identity)
    token.with_grants(api.VideoGrants(room_join=True, room=room))
    return token.to_jwt()
```

Call for each participant: `"robot"`, `"orchestrator"`, `"vision"`.

---

## Key Docs & Repos

| Resource | Link |
|----------|------|
| Embodied AI hackathon repo (main reference) | https://github.com/livekit-examples/embodied-ai-hackathon |
| LiveKit Python Agents | https://github.com/livekit/agents |
| LiveKit Portal | https://github.com/livekit/livekit-portal |
| LiveKit hacker docs | https://www.livekit.info/berkeley-ai-hackathon |
| LiveKit Cloud (redeem credits) | https://cloud.livekit.io/projects/p_/redeem |
| Nebius Physical AI Workbench | https://github.com/nebius/nebius-physical-ai |

---

## What Advaita Needs From You First

Before Advaita can build Vision Agent:
- Room name: `baymax-robot`
- Camera track name: `front_camera`
- A working stream (even webcam fallback)

**Get LiveKit + webcam fallback running in hour 1. This unblocks Advaita.**
