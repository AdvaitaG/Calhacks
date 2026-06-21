# Project Context — Baymax: Agentic Nervous System for a Humanoid Guide Robot
### UC Berkeley AI Hackathon 2026 | June 20–21 | MLK Jr. Student Union | Deadline: 11:00 AM Sunday 6/21

> **This is the single source of truth for coding agents.** Read this before writing any code.

---

## The Idea (One Sentence)
A humanoid guide robot that assists **two blind people simultaneously** — one on each side — powered by a nervous system of AI agents: one synchronous conductor brain that makes decisions, independent left/right arm agents that each focus on their person, tactical agents that coordinate with each other to execute safely, and Arize making every decision visible like an fMRI of the robot's mind.

---

## Use Case: Dual-Person Assistive Robot for the Blind
The robot (a **Booster K1** humanoid) guides **two visually impaired people at once** — one on the left side, one on the right side. Each person holds one of the robot's hands. The robot perceives the world through its sensors (camera, depth, audio), makes decisions about how to assist each person independently, and executes those decisions by coordinating movement across its body safely and in sync.

**What makes this novel:** Each arm operates as an independent agent focused on its person's safety. The UpperLeft agent guides the person on the left; the UpperRight agent guides the person on the right. They can execute different signals simultaneously — the left person might need a STOP signal while the right person gets a FORWARD signal — while the Lower agent manages the robot's shared walking mechanics and Spine coordinates the fast-path reflexes.

The flagship demo: **guiding two blindfolded people along a route** — detecting hazards per-side, planning a safe shared path, and steering each person with gentle physical guidance (left / right / stop / forward). Real-world impact, clear user need, and the multi-agent decomposition is *necessary* — two people being guided with conflicting constraints (different obstacles on each side) genuinely requires independent per-arm decision-making.

---

## What We Are Building

**Baymax** — a hierarchical multi-agent system controlling a Booster K1 humanoid guide robot, architected as a biological nervous system. Think Big Hero 6's Baymax: a personal, safe, caring physical companion — but capable of helping two people at once.

**Two architectural layers:**
- **Strategic layer (synchronous):** One Conductor agent processes all sensory input and makes the primary navigation decision. Synchronous by design — it completes one decision at a time, ensuring nothing desyncs. Low latency on the critical path because only one agent is deciding.
- **Tactical layer (coordinated):** Tactical agents receive the Conductor's decision and coordinate *with each other* via Band to execute their piece. They don't just receive orders — they negotiate to ensure the robot's movements are physically coherent before executing.

**Four things make this novel:**
1. **Dual-person guidance** — one robot, two blind people, two independent arm agents. Each arm has its own agent focused on one person's safety.
2. **Hierarchical latency design** — synchronous conductor prevents desync; parallel tactical agents maximize execution speed
3. **Peer tactical coordination** — tactical agents talk to each other through Band, not just up to the conductor. They resolve physical conflicts before acting.
4. **Neuroplasticity** — Arize traces every decision. Between runs, the Conductor reads traces, identifies failures, rewrites tactical agent prompts. The robot visibly improves run over run.

---

## Narrative for Presentation
> *"The human nervous system doesn't send one giant command to the whole body. Your brain makes a decision — synchronously, one at a time — then your limbs negotiate how to carry it out. We built that architecture. And we pushed it further: Baymax guides two blind people simultaneously, one on each side. The left arm agent focuses entirely on the person to its left. The right arm agent focuses entirely on the person to its right. They can send different signals at the same time. That's not possible with a single monolithic AI. It requires a nervous system."*

**Demo arc:**
- **Run 1:** Baymax guides two blindfolded people along a route with baseline agent prompts — hesitant, jerky, over-cautious. Arize dashboard runs live beside the walk; judges watch every agent decision light up like brain regions firing.
- **Between runs:** Conductor reads Arize traces, identifies failures (e.g. Lower stopped too abruptly, UpperLeft hesitated on turn signal), rewrites agent prompts live (neuroplasticity).
- **Run 2:** Baymax guides more smoothly and safely. Arize shows the before/after prompt diff.
- **Reflex demo:** a sudden hazard appears → Baymax STOPS in ~90ms via the reflex path, bypassing the Conductor entirely.
- **Closing line:** *"This is what it looks like when a robot has a nervous system — not a script."*

---

## Sponsor Technologies

### 1. UFB — Ultimate Bots (Physical AI / Robot Target)
- Robot: **Booster K1** humanoid (on-site at event)
- Prize track: **Physical AI Hack — $3,000**
- UFB provides **$150 free compute per team** via their Slack channel (provisioned through Nebius)
- Judging bar: "Would a real robotics team use it?" — yes: hierarchical control with peer tactical coordination is production-grade robotics architecture
- **Nebius is the required compute platform for UFB** — set up before anything else

### 2. Nebius (GPU Cloud Compute)
- UFB's partner platform — required to access UFB robot/sim environment
- Provides GPU infrastructure for real-time agent inference
- **Set this up first, before LiveKit or anything else robot-side**
- $150 free compute per team — claim via UFB Slack

### 3. Band (Multi-Agent Communication — "The Neural Pathways")
- Prize track: **Multi-agent collaboration — $1,000**
- Two distinct communication patterns:
  - **Top-down (Conductor → Tactical):** strategic decision dispatched to all tactical agents
  - **Peer (Tactical ↔ Tactical):** agents negotiate with each other to resolve physical conflicts before executing
- Each agent is an **external/remote agent** — runs in our code, registers with Band via `agent name` + `API key`
- Framework: **LangGraph + LangChain** (`LangGraphAdapter` + `ChatGoogleGenerativeAI`) — decided by Eshwar, everyone follows
- 6 agents registered: Conductor, UpperLeft, UpperRight, Lower, Threat, Spine (+ Safety by Matthew = 7 total)
- **One job per agent.** Short, focused prompts. Do not combine responsibilities.

### 4. Arize Phoenix (Observability — "The fMRI")
- Prize track: **Observability improves the app — $1,000**
- Open source, runs locally, **no API key needed** (`pip install arize-phoenix`)
- Frames as the fMRI of the robot's brain — judges watch agent decisions light up in real time alongside the walk
- Traces every agent call: prompt in, output, latency, decision path (cortical vs reflex), peer coordination messages
- **Neuroplasticity loop:** between runs, Conductor reads Arize traces → identifies underperforming agents → rewrites their system prompts → measurable improvement next run
- Arize prize checklist:
  1. Tracing on for every agent call
  2. Dashboard visible during demo
  3. Evaluator prompt built (did this decision keep the person safe and on course?)
  4. Feedback used to visibly improve agent behavior (neuroplasticity = the before/after)
  5. Tell them at their booth

### 5. LiveKit (Real-Time Streaming — "The Senses")
- Real-time video/audio/data streaming between robot and cloud agents
- Vision Agent receives robot camera/depth feed via LiveKit
- Conductor sends final navigation commands back to robot via LiveKit
- Fallback: webcam sim if UFB hardware unavailable at event

### 6. Gemini (LLM — "The Neurons")
- Powers every agent's reasoning via `langchain-google-genai`
- Model: `gemini-1.5-flash` for all agents
- `GEMINI_API_KEY` in `.env`
- One tight system prompt per agent — one brain region, one job

---

## Agent Architecture — The Nervous System

```
        ENVIRONMENT (two blind people, one on each side of the robot)
                        │
           Robot sensors (camera, depth, audio) — Booster K1
                        │
                   LiveKit stream
                        │
                   Vision Agent
          [Sensory Cortex — perceives scene:
           obstacles per side, people, vehicles,
           curbs, terrain, left/right hazard levels]
                        │
                   Band Room (baymax-coordination)
                        │
          ┌──── Conductor Agent ────┐
          │    [Prefrontal Cortex]  │
          │    SYNCHRONOUS —        │
          │    one decision         │
          │    at a time            │
          └──────────┬──────────────┘
                     │ dispatches task
         ┌───────────┼───────────────┐
         │           │               │
   UpperLeft     UpperRight        Lower
    Agent          Agent           Agent
 [Motor Cortex— [Motor Cortex—  [Cerebellum—
  guides LEFT    guides RIGHT    walking pace,
  blind person,  blind person,   curbs/terrain]
  left arm]      right arm]
         │           │               │
         └─── peer coordination via Band ───┘
         (agents negotiate physical conflicts
          before executing)
                     │
            Spine Agent [Spinal Cord]
          (fast-path reflex coordinator)
                     │
              Safety Agent [Brainstem]
              (Matthew owns — veto + STOP gate)
                     │
           Conductor receives approved plan
                     │
             LiveKit → Robot executes
                     │
              Arize Phoenix (traces everything)
```

### Two Decision Paths

**Cortical Path (deliberate, ~800ms):**
Vision → Conductor → UpperLeft + UpperRight + Lower (parallel, via Band) → peer coordination → Safety review → Conductor → Command
Used for: route planning, turns, walking pace, curb/crosswalk decisions, per-person guidance signals

**Reflex Arc (fast, ~90ms):**
Threat Agent detects critical hazard → Spine → HALT to UpperLeft + UpperRight + Lower, **bypassing Conductor**
Used for: emergency stop, sudden obstacle or vehicle avoidance
Arize logs which path was taken for every decision.

### Agent Roles

| Agent | Brain Region | Band Handle | Job |
|-------|-------------|-------------|-----|
| **Vision Agent** | Sensory Cortex | (Advaita's) | Perceives the scene, reports obstacles relative to LEFT and RIGHT person separately |
| **Conductor** | Prefrontal Cortex | `@eshwar.rajasekar/conductor` | Makes primary navigation decision, synchronously; dispatches to UpperLeft/UpperRight/Lower |
| **UpperLeft** | Motor Cortex (Left) | `@eshwar.rajasekar/upperleft` | Controls LEFT guiding arm — guides the blind person on the left side |
| **UpperRight** | Motor Cortex (Right) | `@eshwar.rajasekar/upperright` | Controls RIGHT guiding arm — guides the blind person on the right side |
| **Lower** | Cerebellum | `@eshwar.rajasekar/lower` | Manages walking pace, stops at curbs/stairs, adjusts for terrain |
| **Spine** | Spinal Cord | `@eshwar.rajasekar/spine` | Fast-path reflex coordinator — receives CRITICAL threat, immediately HALTs UpperLeft/UpperRight/Lower |
| **Threat** | Amygdala | `@eshwar.rajasekar/threat` | Detects sudden hazards; fires Reflex Arc if CRITICAL |
| **Safety** | Brainstem | (Matthew's) | Vetoes unsafe commands, fires emergency STOP, logs to Arize |

### Neuroplasticity Loop (between runs)
```
Run ends
  → Arize has full trace of every agent decision + outcome
  → Conductor reads traces via Arize API
  → Identifies: which decisions caused hesitation / abrupt stops / unsafe steps
  → Rewrites underperforming agent system prompts with corrected guidance strategy
  → Next run begins with updated "brain"
  → Arize shows before/after prompt diff
```

### Full Data Flow
```
1. Robot sensors → LiveKit → Vision Agent (sees the world, describes obstacles per-side)
2. Vision Agent → Band room (broadcasts scene description with LEFT/RIGHT context)
3. Threat Agent reads scene → if CRITICAL, fires Reflex Arc (jump to step 8)
4. Conductor reads scene → makes ONE synchronous decision → dispatches tasks to Band room
5. UpperLeft + UpperRight + Lower agents receive task simultaneously
6. UpperLeft ↔ UpperRight ↔ Lower: peer negotiation via Band (resolve physical conflicts)
7. Safety Agent reviews coordinated plan, vetoes if unsafe
8. Conductor synthesizes approved plan → final command → LiveKit → Robot guides both people
9. All steps → Arize Phoenix (traced)

Reflex Arc (bypasses Conductor):
3b. Threat → Spine → @UpperLeft @UpperRight @Lower [HALT] (~90ms)
    Safety notified in parallel; Conductor notified after the fact
```

---

## Observability (Arize Phoenix)

Every agent call instrumented:
- **Prompt in** — full system prompt + context
- **Output** — agent decision / plan
- **Latency** — per agent, surfaced in dashboard
- **Decision path** — cortical (slow) or reflex (fast)
- **Peer coordination messages** — UpperLeft ↔ UpperRight ↔ Lower negotiation
- **Veto events** — when Safety Agent blocks a command and why
- **Neuroplasticity diff** — before/after prompt changes between runs

Evaluator prompt: *did this decision keep both blind users safe and successfully navigate the environment?*

---

## Build Order

Follow strictly. Do not skip ahead.

1. **Nebius Physical Workbench** — required compute for UFB. Set up first, claim $150 credit via UFB Slack.
2. **LiveKit room** — connect to robot camera/depth stream (or webcam/sim fallback). Verify frames flowing.
3. **Vision Agent + Conductor in Band** — two agents passing messages. Minimum viable loop, unblocks everyone.
4. **Arize tracing** — instrument both agents. Verify traces appear in local dashboard.
5. **UpperLeft + UpperRight + Lower agents** — add tactical agents responding to Conductor tasks in parallel.
6. **Peer coordination** — wire UpperLeft ↔ UpperRight ↔ Lower to negotiate via Band before executing.
7. **Threat Agent + Spine + Safety Agent** — hazard detection, fast reflex coordinator, veto/STOP logic.
8. **Reflex Arc** — wire Threat → Spine → joint agents, bypassing Conductor. Measure latency difference.
9. **Neuroplasticity loop** — Conductor reads Arize traces, rewrites agent prompts. One visible before/after.
10. **Demo dashboard** — Arize traces + robot feed side by side.

---

## Target Prizes

| Prize | Sponsor | Amount | How We Win |
|-------|---------|--------|------------|
| Physical AI Hack | UFB | $3,000 | End-to-end assistive robot control on Booster K1, production-grade hierarchical architecture, dual-person use case |
| Multi-agent collaboration | Band | $1,000 | 6+ agents, two distinct comms patterns (top-down + peer), all external agents |
| Observability improves the app | Arize | $1,000 | Live fMRI dashboard + neuroplasticity before/after, evaluator on dual-person safety |
| Science/Engineering | Ddoski's Lab | $5,000 | Novel hierarchical latency design + dual-person guidance + social impact framing |

**Total potential: $10,000**

---

## Team

| Member | Area | Owns |
|--------|------|------|
| **Eshwar** | Agent Architecture & Band (The Brain) | Conductor, UpperLeft, UpperRight, Lower, Threat, Spine agents; Reflex Arc; Neuroplasticity loop |
| **Advaita** | Nebius & Vision Agent (The Eyes) | Nebius compute platform setup; Vision Agent perception (with left/right scene split) |
| **Adil** | LiveKit & Robot I/O (The Body) | LiveKit room/streaming; Conductor command → LiveKit → robot return path; webcam fallback sim; UFB booth lead |
| **Matthew** | Observability, Safety & Demo (The Reflexes & fMRI) | Arize Phoenix; Safety Agent; evaluator prompt; demo dashboard; Arize booth lead |

See `roles.md` for full responsibilities, deliverables, and hour-by-hour build order.

---

## Tech Stack

| Tool | Notes |
|------|-------|
| Python 3.11+ | Primary language |
| `langchain-google-genai` | `gemini-1.5-flash` for all agents |
| `langgraph` | Agent framework — `LangGraphAdapter` for Band integration |
| Band SDK (`band`) | Multi-agent communication — external agents, `LangGraphAdapter` |
| Arize Phoenix | `pip install arize-phoenix` — local, no API key |
| LiveKit Python SDK | Sensor stream in, motor commands out |
| Nebius Physical Workbench | UFB's required compute platform — set up before anything else |
| Booster K1 | Target hardware robot (UFB on-site) |

### Agent LLM + Band Setup (Same Pattern for All Eshwar's Agents)

```python
import asyncio, os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.1,
    google_api_key=os.environ["GEMINI_API_KEY"],
)
adapter = LangGraphAdapter(llm=llm, checkpointer=InMemorySaver(), custom_section=AGENT_INSTRUCTIONS)
agent = Agent.create(
    adapter=adapter,
    agent_id=os.environ["AGENT_UUID"],       # from agent_config.yaml
    api_key=os.environ["AGENT_API_KEY"],     # from agent_config.yaml
    ws_url="wss://app.band.ai/api/v1/socket/websocket",
    rest_url="https://app.band.ai",
)
asyncio.run(run_with_graceful_shutdown(agent))
```

---

## Agent I/O Specification
*(Use this to verify each agent is working correctly in isolation before integration)*

### Conductor Agent — Input
```json
{
  "scene": "string — from Vision Agent via Band (includes left/right obstacle breakdown)",
  "last_action": "string — what was last sent to robot",
  "user_state": "WALKING | STOPPED | TURNING",
  "arize_feedback": "string — optional, injected between runs for neuroplasticity"
}
```
### Conductor Agent — Output
```json
{
  "decision": "MOVE_FORWARD | TURN_LEFT | TURN_RIGHT | STOP | SLOW_DOWN",
  "reason": "one sentence",
  "upper_left_task": "SIGNAL_LEFT | SIGNAL_RIGHT | SIGNAL_STOP | SIGNAL_FORWARD | HOLD",
  "upper_right_task": "SIGNAL_LEFT | SIGNAL_RIGHT | SIGNAL_STOP | SIGNAL_FORWARD | HOLD",
  "lower_task": "WALK | SLOW | STOP | STEP_OVER | NAVIGATE_CURB"
}
```

### UpperLeft Agent — Input / Output
Input: `{ "task": "...", "lower_status": "...", "upper_right_status": "...", "scene_left": "..." }`
Output: `{ "arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE", "ready": true, "conflict": null }`

### UpperRight Agent — Input / Output
Input: `{ "task": "...", "lower_status": "...", "upper_left_status": "...", "scene_right": "..." }`
Output: `{ "arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE", "ready": true, "conflict": null }`

### Lower Agent — Input / Output
Input: `{ "task": "...", "upper_left_status": "...", "upper_right_status": "...", "scene": "..." }`
Output: `{ "gait_action": "WALK_NORMAL|WALK_SLOW|PAUSE|STEP_HIGH|STEP_DOWN|HALT", "pace_ms": 500, "ready": true, "conflict": null }`

### Spine Agent — Input / Output
Input: `{ "reflex_command": "EMERGENCY_STOP", "threat_type": "VEHICLE|OBSTACLE|DROP|PERSON" }`
Output: immediately @mentions `@UpperLeft @UpperRight @Lower` with `{ "command": "HALT", "timestamp": ... }`
Spine does NOT wait — fires synchronously to all joint agents, Safety notified in parallel.

### Threat Agent — Input / Output
Input: `{ "scene": "string — from Vision Agent" }`
Output: `{ "threat_level": "NONE|LOW|HIGH|CRITICAL", "threat_type": "VEHICLE|OBSTACLE|DROP|PERSON|null", "fire_reflex": false, "reflex_command": "EMERGENCY_STOP|null" }`
If `fire_reflex: true` → @mentions Spine immediately, bypasses Conductor.

---

## Key Constraints

- **Hackathon rule**: no pre-built code. Everything written June 20–21.
- **Robot**: Booster K1 humanoid (UFB on-site). Fallback: sim or webcam.
- **Conductor is synchronous** — one decision at a time. Prevents desync on the critical path.
- **Tactical agents coordinate peer-to-peer** — negotiate with each other via Band before executing.
- **UpperLeft always initiates PEER_CHECK to Lower** — never the other way, to avoid deadlock.
- **One job per agent** — short, focused system prompts. Do not combine responsibilities.
- **External agents on Band** — register with `agent name` + `API key`, run in our process.
- **Nebius first** — Advaita sets this up before LiveKit or anything else robot-side.
- **Fallback**: webcam sim if UFB hardware unavailable. Do not block on hardware.

---

## Band Agent Config (Eshwar's 6 Agents — Already Registered)

```yaml
# agent_config.yaml (gitignored)
conductor:
  agent_id: "1f72f6d2-b26a-4e2d-a17d-33f837fbcb85"
  api_key: "REDACTED_CONDUCTOR_KEY"
  handle: "@eshwar.rajasekar/conductor"

upper_left:
  agent_id: "3f45823f-3d8a-45fa-a842-eae788d59050"
  api_key: "REDACTED_UPPERLEFT_KEY"
  handle: "@eshwar.rajasekar/upperleft"

upper_right:
  agent_id: "73f0bb96-9f44-4e07-9944-db74a8078d30"
  api_key: "REDACTED_UPPERRIGHT_KEY"
  handle: "@eshwar.rajasekar/upperright"

lower:
  agent_id: "c61be48a-eed0-4bce-8deb-6fe7a9ee4bc1"
  api_key: "REDACTED_LOWER_KEY"
  handle: "@eshwar.rajasekar/lower"

threat:
  agent_id: "9373ba73-3cf4-4f5d-a4f7-abbae6f9876e"
  api_key: "REDACTED_THREAT_KEY"
  handle: "@eshwar.rajasekar/threat"

spine:
  agent_id: "d8c41589-648f-41d6-a273-f9c958c8f342"
  api_key: "REDACTED_SPINE_KEY"
  handle: "@eshwar.rajasekar/spine"
```

---

## Status

**Architecture locked. Use case locked (dual-person assistive guide robot for blind people). Robot: Booster K1. Name: Baymax.**

Done:
- [x] All 6 Band agents registered (Conductor, UpperLeft, UpperRight, Lower, Threat, Spine)
- [x] API keys and UUIDs in `.env`

Waiting on:
- [ ] Band room `baymax-coordination` created (add all agents to it)
- [ ] `agent_config.yaml` created (gitignored) — copy from section above
- [ ] Nebius Physical Workbench setup + UFB compute credit (Advaita)
- [ ] Vision Agent registered in Band (Advaita)
- [ ] Safety Agent registered in Band (Matthew)
- [ ] LiveKit setup (Adil)
- [ ] Arize Phoenix integration (Matthew)
- [ ] UFB robot API / simulator details
