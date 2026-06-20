# ADVAITA READ THIS — Vision Agent Spec

Your job is the Vision Agent. You receive the robot's camera feed from Adil's LiveKit stream, describe what you see, and post it to the Band room. Eshwar's Conductor and Threat agents consume your output — so the format below is a hard contract. Do not change field names without talking to Eshwar.

---

## Your Stack

- **LiveKit** (Adil sets this up) — you consume frames from room `baymax-robot`, track `front_camera`
- **Band** — you publish scene descriptions to room `baymax-coordination`
- **LangChain + ChatGoogleGenerativeAI** — your LLM, same as Eshwar's agents
- **Gemini API key** — in your `.env` as `GEMINI_API_KEY`

---

## What You Receive (From Adil)

LiveKit video frames at ~30fps from the robot's front camera. You do NOT need to process every frame — run inference on a cadence (every 500ms is fine). Pull the latest frame, describe it, post to Band, repeat.

```python
# Pseudocode — Adil will give you the exact LiveKit subscribe pattern
frame = await livekit_room.get_latest_frame("front_camera")
# → numpy array or PIL image, 640x480, h264 decoded
```

---

## What You Output (To Band Room)

Post to Band room `baymax-coordination` mentioning both Conductor and Threat:

```
@Conductor @Threat [SCENE]: <json>
```

The JSON must match this schema **exactly** — field names, types, and enum values:

```json
{
  "description": "Clear sidewalk ahead, person walking toward robot at 4 meters on the left side, parked car on the right at 2 meters",
  "obstacles": [
    {
      "type": "PERSON | VEHICLE | OBJECT | WALL | STEP | DROP | CURB | NONE",
      "distance_m": 4.0,
      "direction": "LEFT | RIGHT | CENTER | AHEAD | BEHIND",
      "moving": true
    }
  ],
  "clear_path": "FORWARD | LEFT | RIGHT | NONE",
  "surface": "FLAT | CURB | STAIRS_UP | STAIRS_DOWN | UNEVEN | UNKNOWN",
  "hazard_level": "NONE | LOW | HIGH | CRITICAL",
  "timestamp": 1718900000000
}
```

### Field definitions

| Field | What it means |
|-------|--------------|
| `description` | One sentence plain English summary of the scene |
| `obstacles` | List of every notable obstacle. Empty array `[]` if none. |
| `obstacles[].type` | Category — pick the closest match from the enum |
| `obstacles[].distance_m` | Estimated distance in meters. If unsure, estimate. |
| `obstacles[].direction` | Where the obstacle is relative to the robot |
| `obstacles[].moving` | True if it's moving (person walking, vehicle passing) |
| `clear_path` | Best available direction with no obstacles. `NONE` if blocked all around. |
| `surface` | What the floor/ground looks like directly ahead |
| `hazard_level` | Your top-level threat assessment. `CRITICAL` = imminent danger (vehicle, sudden drop). |
| `timestamp` | Unix milliseconds — `int(time.time() * 1000)` |

---

## Hazard Level Guide

Use `hazard_level` as your summary signal. Threat Agent reads this first.

| Level | When to use |
|-------|-------------|
| `NONE` | Clear path, no obstacles within 5m |
| `LOW` | Obstacles present but plenty of space to navigate |
| `HIGH` | Obstacle close (<2m) or surface change ahead |
| `CRITICAL` | Moving vehicle, sudden drop, stairs with no railing, person directly in path <1m |

---

## Your Agent Code Pattern

Same boilerplate as Eshwar's agents — LangChain + Band:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter

VISION_INSTRUCTIONS = """
You are the Vision Agent (Sensory Cortex) of a humanoid guide robot for blind people.
You receive camera frames and describe the scene for the robot's brain agents.
Post your description to the room mentioning @Conductor and @Threat.
Respond ONLY with valid JSON matching the scene schema exactly. No explanation outside the JSON.
"""

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.1, google_api_key=...)
adapter = LangGraphAdapter(llm=llm, checkpointer=InMemorySaver(), custom_section=VISION_INSTRUCTIONS)
agent = Agent.create(adapter=adapter, agent_id=..., api_key=..., ws_url="wss://app.band.ai/api/v1/socket/websocket", rest_url="https://app.band.ai")
```

---

## Band Registration (Do This First)

Go to **app.band.ai → Agents → New Agent → External Agent**

- **Name:** `Vision`
- **Description:** `Perceives the robot's camera feed and describes the scene: obstacles, people, vehicles, terrain, hazards. Posts scene descriptions to the room mentioning Conductor and Threat.`

Save your API Key (shown once) and UUID. Give them to Eshwar for `agent_config.yaml`.

---

## Cadence

- Run vision inference every **500ms** — don't post every frame, LLMs are slow
- Always post even if scene hasn't changed — Conductor needs a heartbeat
- If LiveKit stream drops, post: `@Conductor @Threat [SCENE]: {"description": "Camera feed lost", "obstacles": [], "clear_path": "NONE", "surface": "UNKNOWN", "hazard_level": "HIGH", "timestamp": ...}`

---

## What You Do NOT Own

- How Conductor or Threat interpret your output — that's Eshwar
- The LiveKit room setup — that's Adil (coordinate with him on frame format)
- Arize logging — Matthew handles that, your calls will be traced automatically
- Any robot commands — you only describe, never command

---

## Coordinate With

- **Adil** — get the LiveKit room name, track name, and frame format before you write any code
- **Eshwar** — if you want to add a field to the scene schema, ask him first (he has to update his parsing)
