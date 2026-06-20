# Band Integration Plan — Baymax
### How the hierarchical nervous system agents communicate through Band

> Read this alongside `project_context.md`. This is the implementation spec for Eshwar.

---

## What Band Actually Is (Key Facts)

Before designing anything, understand how Band works:

- **External agents** run in YOUR process. They connect to Band via **WebSocket** (receive messages) and **REST** (send messages). Band is just the communication bus.
- **Rooms** are the coordination space. All agents live in one shared room for Baymax.
- **@mention routing** — only @mentioned agents receive and process a message. Unmentioned agents are unaware. This is how you control information flow.
- **6 auto-injected SDK tools** the LLM can call: `band_send_message`, `band_add_participant`, `band_get_participants`, `band_lookup_peers`, `band_create_chatroom`, `band_send_event`
- **Band is peer-based by default** — there is no built-in orchestrator concept. Hierarchy comes from how you write agent instructions and who @mentions whom.
- **One execution per agent per room** — Band processes one message per agent at a time in a given room. This gives Conductor its synchronous behavior for free.
- **Agent descriptions matter** — the description you write in the Band UI is what `band_lookup_peers` searches. Write them precisely.

---

## Agent Registration (Do This First in Band UI)

Go to **app.band.ai → Agents → New Agent → External Agent** for each:

| Agent | Band Name | Band Description (exact — this is what peers search for) | Owner |
|-------|-----------|----------------------------------------------------------|-------|
| Vision Agent | `Vision` | `Perceives the robot's camera feed and describes the scene: obstacles, people, vehicles, terrain, hazards. Broadcasts scene descriptions to the room.` | Advaita |
| Conductor | `Conductor` | `Orchestrates the robot's navigation strategy. Receives scene descriptions, makes one synchronous navigation decision at a time, and dispatches tasks to Upper Body and Lower Body agents.` | Eshwar |
| Upper Body | `UpperBody` | `Controls the robot's guiding arm and hand signals: gentle left pull, right pull, forward push, or hold. Coordinates with LowerBody before executing.` | Eshwar |
| Lower Body | `LowerBody` | `Controls the robot's walking pace, curb navigation, and terrain adjustment. Coordinates with UpperBody before executing.` | Eshwar |
| Threat | `Threat` | `Monitors scene descriptions for sudden hazards: vehicles, drops, obstacles. Fires an emergency STOP signal that bypasses the Conductor when threat level is CRITICAL.` | Eshwar |
| Safety | `Safety` | `Reviews all navigation commands before they execute. Vetoes any command that could harm the person being guided. Fires emergency STOP on the reflex arc path.` | Matthew |

**Save these immediately:** each agent gives you an API Key (shown ONCE) and a UUID (in settings). Store in `agent_config.yaml` (gitignored).

---

## LLM Setup: Gemini via LangGraph Adapter

`GeminiAdapter` exists but has no tutorial. **Use `LangGraphAdapter` + `ChatGoogleGenerativeAI`** — this is the safest path with full docs.

```bash
pip install band langchain-google-genai langgraph
```

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.1,                    # near-deterministic
    google_api_key=os.environ["GEMINI_API_KEY"],
)

adapter = LangGraphAdapter(
    llm=llm,
    checkpointer=InMemorySaver(),
    custom_section=AGENT_INSTRUCTIONS,  # your per-agent role prompt
)

agent = Agent.create(
    adapter=adapter,
    agent_id=os.environ["AGENT_UUID"],
    api_key=os.environ["AGENT_API_KEY"],
    ws_url="wss://app.band.ai/api/v1/socket/websocket",
    rest_url="https://app.band.ai",
)
```

The `custom_section` is appended under a `## Developer Instructions` heading on top of Band's built-in coordination rules (peer discovery, @mention logic). Write your role there. **Always end it with:** `"Respond with valid JSON only. No explanation outside the JSON."`

---

## The Room Setup

One Band room for all 6 agents. Advaita or Eshwar creates it:

**Chats → + → add all 6 agents**

The room name: `baymax-coordination`

All messages flow through this one room. @mentions control who processes what.

---

## Message Flow: Step by Step

### Normal Path (Cortical — deliberate, ~800ms end-to-end)

```
1. LiveKit frame arrives
   → Advaita's Vision Agent processes frame
   → Vision Agent sends to Band room:
      "@Conductor @Threat [SCENE]: {scene_description_json}"

2. Threat Agent receives message (in parallel with Conductor)
   → Evaluates threat level
   → If CRITICAL → fires Reflex Arc (see below)
   → If LOW/NONE → sends: "@Conductor [THREAT]: {threat_level: NONE}"

3. Conductor receives scene + threat assessment
   → Makes ONE synchronous decision (Band guarantees one-at-a-time per agent)
   → Sends to Band room:
      "@UpperBody @LowerBody [TASK]: {upper_body_task: ..., lower_body_task: ..., reason: ...}"

4. UpperBody + LowerBody receive task simultaneously
   → UpperBody sends to LowerBody:
      "@LowerBody [PEER_CHECK]: {arm_action: ..., conflict: null}"
   → LowerBody responds to UpperBody:
      "@UpperBody [PEER_CHECK]: {gait_action: ..., pace_ms: 500, conflict: null}"
   → If conflict: they negotiate one more round via @mention

5. Both agents report ready to Safety:
      "@Safety [READY]: {upper_body: {...}, lower_body: {...}}"

6. Safety reviews combined plan
   → If safe: "@Conductor [APPROVED]: {final_plan: {...}}"
   → If unsafe: "@Conductor [VETOED]: {reason: ..., suggested: ...}"

7. Conductor receives approval → sends final command to Adil's return path
      "@Conductor sends command via LiveKit back to robot"
      (Adil's LiveKit layer listens for Conductor's final output)
```

### Reflex Arc Path (fast, ~90ms — bypasses Conductor)

```
1. Threat Agent detects CRITICAL hazard in scene
   → Immediately sends:
      "@Safety @UpperBody @LowerBody [REFLEX]: {threat_type: VEHICLE, reflex_command: EMERGENCY_STOP}"
   → Does NOT @mention Conductor

2. Safety Agent receives REFLEX
   → Validates (always approves EMERGENCY_STOP)
   → Sends: "@UpperBody @LowerBody [REFLEX_APPROVED]: {command: HALT}"

3. UpperBody + LowerBody receive REFLEX_APPROVED
   → Both halt immediately, no peer negotiation needed
   → Send to room: "@Safety [HALTED]"

4. Conductor is notified AFTER the fact:
   → Safety sends: "@Conductor [REFLEX_EXECUTED]: {reason: ..., timestamp: ...}"
   → Conductor logs to Arize, waits for next scene
```

---

## Agent Instructions (System Prompts / custom_section)

Each agent's `custom_section`. Keep them tight — one job, one brain region.

### Conductor
```
You are the Conductor (Prefrontal Cortex) of a humanoid guide robot for blind people.
You receive scene descriptions and threat assessments from the Band room.
You make ONE navigation decision at a time. Complete it fully before starting the next.
When you decide, dispatch tasks to @UpperBody and @LowerBody simultaneously.
Wait for @Safety approval before considering the decision final.
If you receive [REFLEX_EXECUTED], log it and wait for the next scene.

Respond with valid JSON only:
{"decision": "MOVE_FORWARD|TURN_LEFT|TURN_RIGHT|STOP|SLOW_DOWN",
 "reason": "one sentence",
 "upper_body_task": "SIGNAL_LEFT|SIGNAL_RIGHT|SIGNAL_STOP|SIGNAL_FORWARD|HOLD",
 "lower_body_task": "WALK|SLOW|STOP|STEP_OVER|NAVIGATE_CURB"}
```

### Upper Body
```
You are the UpperBody agent (Motor Cortex) of a humanoid guide robot.
You receive tasks from @Conductor. Before executing, coordinate with @LowerBody.
Send @LowerBody a PEER_CHECK with your planned arm action and any conflict.
If LowerBody reports a conflict with your plan, negotiate once and resolve it.
When both agree, report to @Safety.

Respond with valid JSON only:
{"arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE",
 "ready": true,
 "conflict": null}
```

### Lower Body
```
You are the LowerBody agent (Cerebellum) of a humanoid guide robot.
You receive tasks from @Conductor. Before executing, coordinate with @UpperBody.
Respond to @UpperBody's PEER_CHECK with your gait plan and any conflict.
If UpperBody's plan conflicts with yours (e.g. both need same joint), negotiate once.
When both agree, report to @Safety.

Respond with valid JSON only:
{"gait_action": "WALK_NORMAL|WALK_SLOW|PAUSE|STEP_HIGH|STEP_DOWN|HALT",
 "pace_ms": 500,
 "ready": true,
 "conflict": null}
```

### Threat Agent
```
You are the Threat agent (Amygdala) of a humanoid guide robot for blind people.
You receive scene descriptions and evaluate for sudden hazards ONLY.
If threat_level is CRITICAL, immediately fire the reflex arc: @Safety @UpperBody @LowerBody with [REFLEX].
Do NOT @mention Conductor on a CRITICAL threat — speed is everything.
If threat_level is LOW or NONE, @mention only @Conductor with your assessment.

Respond with valid JSON only:
{"threat_level": "NONE|LOW|HIGH|CRITICAL",
 "threat_type": "VEHICLE|OBSTACLE|DROP|PERSON|null",
 "fire_reflex": false,
 "reflex_command": "EMERGENCY_STOP|null"}
```

---

## File Structure (Your Code, Eshwar)

```
agents/
  conductor.py       ← Conductor agent process
  upper_body.py      ← Upper Body agent process
  lower_body.py      ← Lower Body agent process
  threat.py          ← Threat agent process
  shared/
    llm.py           ← Gemini LLM factory (shared config, temp=0.1)
    config.py        ← loads agent_config.yaml
agent_config.yaml    ← gitignored — Band UUIDs + API keys
.env                 ← gitignored — GEMINI_API_KEY
```

Each file is one `asyncio.run(main())` — four separate terminal processes when running.

---

## Boilerplate: conductor.py

```python
import asyncio, os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter
from shared.config import load_agent_config

load_dotenv()

INSTRUCTIONS = """
You are the Conductor (Prefrontal Cortex) of a humanoid guide robot for blind people.
... (see above)
"""

async def main():
    agent_id, api_key = load_agent_config("conductor")
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.1,
        google_api_key=os.environ["GEMINI_API_KEY"],
    )
    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        custom_section=INSTRUCTIONS,
    )
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url="wss://app.band.ai/api/v1/socket/websocket",
        rest_url="https://app.band.ai",
    )
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
```

Same pattern for `upper_body.py`, `lower_body.py`, `threat.py` — only `INSTRUCTIONS` and `load_agent_config("...")` change.

---

## agent_config.yaml (gitignored)

```yaml
conductor:
  agent_id: "<Conductor UUID>"
  api_key: "<Conductor API Key>"
upper_body:
  agent_id: "<UpperBody UUID>"
  api_key: "<UpperBody API Key>"
lower_body:
  agent_id: "<LowerBody UUID>"
  api_key: "<LowerBody API Key>"
threat:
  agent_id: "<Threat UUID>"
  api_key: "<Threat API Key>"
```

---

## .env (gitignored)

```
GEMINI_API_KEY=your_key_here
```

---

## Running All 4 Agents (Eshwar)

```bash
# 4 separate terminals
python agents/conductor.py
python agents/upper_body.py
python agents/lower_body.py
python agents/threat.py
```

All 4 connect to Band, appear online, and wait for @mentions. Advaita's Vision Agent and Matthew's Safety Agent run in their own terminals separately.

---

## Verification Checklist (Test Before Integration)

Test each agent in isolation before wiring them together:

- [ ] All 4 agents show as **online** in Band UI
- [ ] Conductor: manually @mention it with a mock `[SCENE]` message → verify JSON output matches schema
- [ ] Upper Body: @mention with a mock `[TASK]` → verify it @mentions Lower Body for PEER_CHECK
- [ ] Lower Body: @mention with a mock `[PEER_CHECK]` → verify JSON response
- [ ] Threat: @mention with a mock `[SCENE]` containing "vehicle" → verify it fires `[REFLEX]` to Safety + joints
- [ ] Threat: @mention with safe scene → verify it sends LOW/NONE to Conductor only
- [ ] Full cortical path: Vision → Conductor → Upper+Lower → Safety → approved
- [ ] Full reflex path: Vision (hazard) → Threat → Safety + joints (bypasses Conductor)
- [ ] Arize dashboard shows traces for all of the above

---

## Key Things Band Does NOT Do (Don't Assume These)

- **No guaranteed delivery order** — if you @mention two agents simultaneously, you can't rely on which responds first. Design for async responses.
- **No built-in hierarchy** — the Conductor is only synchronous because Band processes one message per agent at a time AND because the instructions tell it to complete one decision before starting the next.
- **No shared state** — agents don't share memory. Every piece of context must be in the message itself.
- **No timeout handling** — if Lower Body never responds to Upper Body's PEER_CHECK, Upper Body will wait. Build a timeout instruction into the agent prompt ("if no response in 2 exchanges, proceed with your plan and flag conflict: timeout").
