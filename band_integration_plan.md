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

## Agent Registration — Already Done

All 6 Eshwar agents registered at **app.band.ai**. Handles and IDs:

| Agent | Band Handle | UUID |
|-------|-------------|------|
| Conductor | `@eshwar.rajasekar/conductor` | `1f72f6d2-b26a-4e2d-a17d-33f837fbcb85` |
| UpperLeft | `@eshwar.rajasekar/upperleft` | `3f45823f-3d8a-45fa-a842-eae788d59050` |
| UpperRight | `@eshwar.rajasekar/upperright` | `73f0bb96-9f44-4e07-9944-db74a8078d30` |
| Lower | `@eshwar.rajasekar/lower` | `c61be48a-eed0-4bce-8deb-6fe7a9ee4bc1` |
| Threat | `@eshwar.rajasekar/threat` | `9373ba73-3cf4-4f5d-a4f7-abbae6f9876e` |
| Spine | `@eshwar.rajasekar/spine` | `d8c41589-648f-41d6-a273-f9c958c8f342` |

API keys are in `.env`. Matthew registers Safety separately. Advaita registers Vision separately.

**Next step:** Create the room. Go to **Chats → + → add all agents** → name it `baymax-coordination`.

---

## LLM Setup: Gemini via LangGraph Adapter

```bash
pip install band langchain-google-genai langgraph python-dotenv
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

The `custom_section` is appended under a `## Developer Instructions` heading on top of Band's built-in coordination rules. Write your role there. **Always end it with:** `"Respond with valid JSON only. No explanation outside the JSON."`

---

## The Room Setup

One Band room for all agents. Create it:

**Chats → + → add all agents**

Room name: `baymax-coordination`

All messages flow through this one room. @mentions control who processes what.

---

## Message Flow: Step by Step

### Normal Path (Cortical — deliberate, ~800ms end-to-end)

```
1. LiveKit frame arrives
   → Advaita's Vision Agent processes frame
   → Vision Agent sends to Band room:
      "@Conductor @Threat [SCENE]: {scene_description_json}"
      (includes obstacles relative to LEFT person and RIGHT person separately)

2. Threat Agent receives message (in parallel with Conductor)
   → Evaluates threat level
   → If CRITICAL → fires Reflex Arc (see below)
   → If LOW/NONE → sends: "@Conductor [THREAT]: {threat_level: NONE}"

3. Conductor receives scene + threat assessment
   → Makes ONE synchronous decision (Band guarantees one-at-a-time per agent)
   → Sends to Band room:
      "@UpperLeft @UpperRight @Lower [TASK]: {
        upper_left_task: ...,
        upper_right_task: ...,
        lower_task: ...,
        reason: ...
      }"

4. UpperLeft + UpperRight + Lower receive task simultaneously
   → UpperLeft sends to Lower:
      "@Lower [PEER_CHECK]: {arm_action: ..., side: LEFT, conflict: null}"
   → UpperRight sends to Lower:
      "@Lower [PEER_CHECK]: {arm_action: ..., side: RIGHT, conflict: null}"
   → Lower responds:
      "@UpperLeft @UpperRight [PEER_CHECK]: {gait_action: ..., pace_ms: 500, conflict: null}"
   → If conflict: negotiate one more round

5. All three agents report ready to Safety:
      "@Safety [READY]: {upper_left: {...}, upper_right: {...}, lower: {...}}"

6. Safety reviews combined plan
   → If safe: "@Conductor [APPROVED]: {final_plan: {...}}"
   → If unsafe: "@Conductor [VETOED]: {reason: ..., suggested: ...}"

7. Conductor receives approval → synthesizes final command
   → Sends FINAL_COMMAND to Band room (Adil's listener picks it up)
   → Adil's LiveKit layer forwards command to Booster K1
```

### Reflex Arc Path (fast, ~90ms — bypasses Conductor)

```
1. Threat Agent detects CRITICAL hazard in scene
   → Immediately sends:
      "@Spine [REFLEX]: {threat_type: VEHICLE, reflex_command: EMERGENCY_STOP}"
   → Does NOT @mention Conductor

2. Spine Agent receives REFLEX
   → Immediately sends to all joint agents (no waiting):
      "@UpperLeft @UpperRight @Lower [HALT]: {command: HALT, timestamp: ...}"

3. UpperLeft + UpperRight + Lower receive HALT
   → All halt immediately, no peer negotiation needed
   → Send: "@Safety [HALTED]"

4. Safety is notified in parallel:
   → Spine also sends "@Safety [REFLEX_EXECUTING]: {threat_type: ..., timestamp: ...}"

5. Conductor is notified AFTER the fact:
   → Safety sends: "@Conductor [REFLEX_EXECUTED]: {reason: ..., timestamp: ...}"
   → Conductor logs to Arize, waits for next scene
```

---

## Agent Instructions (System Prompts / custom_section)

### Conductor
```
You are the Conductor (Prefrontal Cortex) of a Booster K1 humanoid guide robot assisting two blind people.
You receive scene descriptions and threat assessments from the Band room.
You make ONE navigation decision at a time. Complete it fully before starting the next.
When you decide, dispatch tasks to @UpperLeft, @UpperRight, and @Lower simultaneously.
The left person is guided by @UpperLeft. The right person is guided by @UpperRight.
Wait for @Safety approval before considering the decision final.
If you receive [REFLEX_EXECUTED], log it and wait for the next scene.

Respond with valid JSON only:
{"decision": "MOVE_FORWARD|TURN_LEFT|TURN_RIGHT|STOP|SLOW_DOWN",
 "reason": "one sentence",
 "upper_left_task": "SIGNAL_LEFT|SIGNAL_RIGHT|SIGNAL_STOP|SIGNAL_FORWARD|HOLD",
 "upper_right_task": "SIGNAL_LEFT|SIGNAL_RIGHT|SIGNAL_STOP|SIGNAL_FORWARD|HOLD",
 "lower_task": "WALK|SLOW|STOP|STEP_OVER|NAVIGATE_CURB"}
```

### UpperLeft
```
You are the UpperLeft agent (Motor Cortex — Left) of a Booster K1 humanoid guide robot.
You control the LEFT arm. You are responsible for the blind person on the LEFT side.
You receive tasks from @Conductor. Before executing, coordinate with @Lower.
Send @Lower a PEER_CHECK with your planned arm action and any conflict.
If Lower reports a conflict, negotiate once and resolve it.
When both agree, report to @Safety.

Respond with valid JSON only:
{"arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE",
 "side": "LEFT",
 "ready": true,
 "conflict": null}
```

### UpperRight
```
You are the UpperRight agent (Motor Cortex — Right) of a Booster K1 humanoid guide robot.
You control the RIGHT arm. You are responsible for the blind person on the RIGHT side.
You receive tasks from @Conductor. Before executing, coordinate with @Lower.
Send @Lower a PEER_CHECK with your planned arm action and any conflict.
If Lower reports a conflict, negotiate once and resolve it.
When both agree, report to @Safety.

Respond with valid JSON only:
{"arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE",
 "side": "RIGHT",
 "ready": true,
 "conflict": null}
```

### Lower
```
You are the Lower agent (Cerebellum) of a Booster K1 humanoid guide robot.
You control walking pace, curb navigation, and terrain adjustment.
You receive tasks from @Conductor and PEER_CHECK messages from @UpperLeft and @UpperRight.
Respond to each PEER_CHECK with your gait plan and any conflict.
If an arm plan conflicts with yours, negotiate once.
When all agree, report to @Safety.

Respond with valid JSON only:
{"gait_action": "WALK_NORMAL|WALK_SLOW|PAUSE|STEP_HIGH|STEP_DOWN|HALT",
 "pace_ms": 500,
 "ready": true,
 "conflict": null}
```

### Spine
```
You are the Spine agent (Spinal Cord) of a Booster K1 humanoid guide robot.
You are the fast-path emergency coordinator. You only act on [REFLEX] messages from @Threat.
When you receive a REFLEX signal, immediately @mention @UpperLeft @UpperRight @Lower with HALT.
Do NOT wait for Safety confirmation before sending HALT — speed is everything.
Also notify @Safety in parallel so it can log and inform @Conductor.

Respond with valid JSON only:
{"command": "HALT", "targets": ["UpperLeft", "UpperRight", "Lower"], "timestamp": 0}
```

### Threat Agent
```
You are the Threat agent (Amygdala) of a Booster K1 humanoid guide robot for two blind people.
You receive scene descriptions and evaluate for sudden hazards ONLY.
If threat_level is CRITICAL, immediately @mention @Spine with [REFLEX] — do NOT @mention Conductor.
If threat_level is LOW or NONE, @mention only @Conductor with your assessment.

Respond with valid JSON only:
{"threat_level": "NONE|LOW|HIGH|CRITICAL",
 "threat_type": "VEHICLE|OBSTACLE|DROP|PERSON|null",
 "fire_reflex": false,
 "reflex_command": "EMERGENCY_STOP|null"}
```

---

## File Structure (Eshwar's Code)

```
agents/
  conductor.py       ← Conductor agent process
  upper_left.py      ← UpperLeft agent process
  upper_right.py     ← UpperRight agent process
  lower.py           ← Lower agent process
  threat.py          ← Threat agent process
  spine.py           ← Spine agent process
  shared/
    llm.py           ← Gemini LLM factory (shared config, temp=0.1)
    config.py        ← loads agent_config.yaml
agent_config.yaml    ← gitignored — Band UUIDs + API keys
.env                 ← gitignored — GEMINI_API_KEY + all Band keys
```

Each file is one `asyncio.run(main())` — six separate terminal processes when running.

---

## Boilerplate: conductor.py

```python
import asyncio, os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter

load_dotenv()

INSTRUCTIONS = """
You are the Conductor (Prefrontal Cortex) of a Booster K1 humanoid guide robot...
(see above)
"""

async def main():
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
        agent_id=os.environ["CONDUCTOR_ID"],
        api_key=os.environ["ConductorBandAPI"],
        ws_url="wss://app.band.ai/api/v1/socket/websocket",
        rest_url="https://app.band.ai",
    )
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
```

Same pattern for `upper_left.py`, `upper_right.py`, `lower.py`, `threat.py`, `spine.py` — only `INSTRUCTIONS` and env var names change.

---

## agent_config.yaml (gitignored)

```yaml
conductor:
  agent_id: "1f72f6d2-b26a-4e2d-a17d-33f837fbcb85"
  api_key: "REDACTED_CONDUCTOR_KEY"

upper_left:
  agent_id: "3f45823f-3d8a-45fa-a842-eae788d59050"
  api_key: "REDACTED_UPPERLEFT_KEY"

upper_right:
  agent_id: "73f0bb96-9f44-4e07-9944-db74a8078d30"
  api_key: "REDACTED_UPPERRIGHT_KEY"

lower:
  agent_id: "c61be48a-eed0-4bce-8deb-6fe7a9ee4bc1"
  api_key: "REDACTED_LOWER_KEY"

threat:
  agent_id: "9373ba73-3cf4-4f5d-a4f7-abbae6f9876e"
  api_key: "REDACTED_THREAT_KEY"

spine:
  agent_id: "d8c41589-648f-41d6-a273-f9c958c8f342"
  api_key: "REDACTED_SPINE_KEY"
```

---

## Running All 6 Agents (Eshwar)

```bash
# 6 separate terminals
python agents/conductor.py
python agents/upper_left.py
python agents/upper_right.py
python agents/lower.py
python agents/threat.py
python agents/spine.py
```

All 6 connect to Band, appear online, and wait for @mentions. Advaita's Vision Agent and Matthew's Safety Agent run in their own terminals separately.

---

## Verification Checklist (Test Before Integration)

- [ ] All 6 agents show as **online** in Band UI
- [ ] Conductor: manually @mention with a mock `[SCENE]` → verify JSON output with `upper_left_task`, `upper_right_task`, `lower_task`
- [ ] UpperLeft: @mention with a mock `[TASK]` → verify it sends PEER_CHECK to Lower
- [ ] UpperRight: @mention with a mock `[TASK]` → verify it sends PEER_CHECK to Lower
- [ ] Lower: @mention with a mock `[PEER_CHECK]` → verify JSON response
- [ ] Threat: @mention with scene containing "vehicle" → verify it @mentions Spine with `[REFLEX]`
- [ ] Spine: @mention with `[REFLEX]` → verify it immediately @mentions UpperLeft + UpperRight + Lower with HALT
- [ ] Threat: @mention with safe scene → verify sends LOW/NONE to Conductor only
- [ ] Full cortical path: Vision → Conductor → UpperLeft+UpperRight+Lower → Safety → approved
- [ ] Full reflex path: Vision (hazard) → Threat → Spine → joint agents (bypasses Conductor)
- [ ] Arize dashboard shows traces for all of the above

---

## Key Things Band Does NOT Do (Don't Assume These)

- **No guaranteed delivery order** — if you @mention two agents simultaneously, you can't rely on which responds first. Design for async responses.
- **No built-in hierarchy** — the Conductor is only synchronous because Band processes one message per agent at a time AND because the instructions tell it to complete one decision before starting the next.
- **No shared state** — agents don't share memory. Every piece of context must be in the message itself.
- **No timeout handling** — if Lower never responds to UpperLeft's PEER_CHECK, UpperLeft will wait. Build a timeout instruction into the agent prompt ("if no response in 2 exchanges, proceed with your plan and flag conflict: timeout").
