# Project Context — Baymax: Agentic Nervous System for a Humanoid Guide Robot
### UC Berkeley AI Hackathon 2026 | June 20–21 | MLK Jr. Student Union | Deadline: 11:00 AM Sunday 6/21

> **This is the single source of truth for coding agents.** Read this before writing any code.

---

## The Idea (One Sentence)
A humanoid guide robot that assists blind people — powered by a nervous system of AI agents: one synchronous conductor brain that makes decisions, tactical agents that coordinate with each other to execute safely, and Arize making every decision visible like an fMRI of the robot's mind.

---

## Use Case: Assistive Robot for the Blind
The robot helps a visually impaired person navigate their environment. It perceives the world through its sensors (camera, depth, audio), makes decisions about how to assist (guide around an obstacle, signal a turn, warn of a hazard, stop for a curb), and executes those decisions by coordinating movement across its body safely and in sync.

The flagship demo: **guiding a blindfolded person along a route** — detecting hazards, planning a safe path, and steering with gentle physical guidance (left / right / stop / forward). Real-world impact, clear user need, and the multi-agent decomposition is *necessary* — navigation and manipulation have genuinely conflicting physical constraints (guiding someone through a doorway while detecting a step hazard requires different limbs doing different things with tight coordination).

---

## What We Are Building

**Baymax** — a hierarchical multi-agent system controlling a humanoid guide robot, architected as a biological nervous system. Think Big Hero 6's Baymax: a personal, safe, caring physical companion.

**Two architectural layers:**
- **Strategic layer (synchronous):** One Conductor agent processes all sensory input and makes the primary navigation decision. Synchronous by design — it completes one decision at a time, ensuring nothing desyncs. Low latency on the critical path because only one agent is deciding.
- **Tactical layer (coordinated):** Tactical agents receive the Conductor's decision and coordinate *with each other* via Band to execute their piece. They don't just receive orders — they negotiate to ensure the robot's movements are physically coherent before executing.

**Three things make this novel:**
1. **Hierarchical latency design** — synchronous conductor prevents desync; parallel tactical agents maximize execution speed
2. **Peer tactical coordination** — tactical agents talk to each other through Band, not just up to the conductor. They resolve physical conflicts before acting.
3. **Neuroplasticity** — Arize traces every decision. Between runs, the Conductor reads traces, identifies failures, rewrites tactical agent prompts. The robot visibly improves run over run.

---

## Narrative for Presentation
> *"The human nervous system doesn't send one giant command to the whole body. Your brain makes a decision — synchronously, one at a time — then your limbs negotiate how to carry it out. We built that architecture. Baymax is the first humanoid guide robot with a real nervous system: a brain that decides, and a body that coordinates."*

**Demo arc:**
- **Run 1:** Baymax guides a blindfolded person along a route with baseline agent prompts — hesitant, jerky, over-cautious. Arize dashboard runs live beside the walk; judges watch every agent decision light up like brain regions firing.
- **Between runs:** Conductor reads Arize traces, identifies failures (e.g. Lower Body stopped too abruptly, Upper Body hesitated on turn signal), rewrites agent prompts live (neuroplasticity).
- **Run 2:** Baymax guides more smoothly and safely. Arize shows the before/after prompt diff.
- **Reflex demo:** a sudden hazard appears → Baymax STOPS in ~90ms via the reflex path, bypassing the Conductor entirely.
- **Closing line:** *"This is what it looks like when a robot has a nervous system — not a script."*

---

## Sponsor Technologies

### 1. UFB — Ultimate Bots (Physical AI / Robot Target)
- Humanoid robotics platform providing the robot or simulator we are controlling
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
- Band SDK supports LangChain and CrewAI — Eshwar picks one, everyone follows
- Minimum 2 agents for prize — we will have 5+
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

### 6. Claude API (LLM — "The Neurons")
- Powers every agent's reasoning
- Use `claude-sonnet-4-6` or latest capable model
- One tight system prompt per agent — one brain region, one job

---

## Agent Architecture — The Nervous System

```
        ENVIRONMENT (what the blind user is navigating)
                        │
           Robot sensors (camera, depth, audio)
                        │
                   LiveKit stream
                        │
                   Vision Agent
          [Sensory Cortex — perceives scene:
           obstacles, people, vehicles, curbs, terrain]
                        │
                   Band Room
                        │
          ┌──── Conductor Agent ────┐
          │    [Prefrontal Cortex]  │
          │    SYNCHRONOUS —        │
          │    one decision         │
          │    at a time            │
          └──────────┬──────────────┘
                     │ dispatches task
         ┌───────────┼────────────┐
         │           │            │
  Upper Body    Lower Body    Safety Agent
    Agent         Agent       [Brainstem —
 [Motor Cortex— [Cerebellum—   veto + STOP]
  guiding arm,   walking pace,
  hand signals]  curbs/terrain]
         │           │
         └── peer coordination via Band ──┘
         (agents negotiate physical conflicts
          before executing — e.g. arm needed
          for balance vs arm needed for signal)
                     │
           Conductor receives coordinated plan
                     │
             LiveKit → Robot executes
                     │
              Arize Phoenix (traces everything)
```

### Two Decision Paths

**Cortical Path (deliberate, ~800ms):**
Vision → Conductor → Upper Body + Lower Body (parallel, via Band) → peer coordination → Safety review → Conductor → Command
Used for: route planning, turns, walking pace, curb/crosswalk decisions

**Reflex Arc (fast, ~90ms):**
Threat Agent detects critical hazard → directly triggers Safety STOP + Joint Agents, **bypassing Conductor**
Used for: emergency stop, sudden obstacle or vehicle avoidance
Arize logs which path was taken for every decision.

### Agent Roles

| Agent | Brain Region | Job | Input | Output |
|-------|-------------|-----|-------|--------|
| **Vision Agent** | Sensory Cortex | Perceives the scene | LiveKit camera/depth feed | Scene description → Band room |
| **Conductor Agent** | Prefrontal Cortex | Makes primary navigation decision, synchronously | Vision output + Arize traces (between runs) | Task dispatched to tactical agents; final command to LiveKit |
| **Upper Body Agent** | Motor Cortex | Controls guiding arm + hand signals (left/right/stop/forward) | Conductor task + peer negotiation with Lower Body | Arm + hand-signal action plan |
| **Lower Body Agent** | Cerebellum | Manages walking pace, stops at curbs/stairs, adjusts for terrain | Conductor task + peer negotiation with Upper Body | Pace + footing action plan |
| **Threat Agent** | Amygdala | Detects sudden hazards (vehicles, obstacles, drops) | Scene description | Urgency signal; fires Reflex Arc if critical |
| **Safety Agent** | Brainstem | Vetoes unsafe commands, fires emergency STOP | All agent outputs | Approved or vetoed + reason (logged to Arize) |

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
1. Robot sensors → LiveKit → Vision Agent (sees the world)
2. Vision Agent → Band room (broadcasts scene description)
3. Threat Agent reads scene → if critical hazard, fires Reflex Arc (jumps to step 8)
4. Conductor reads scene → makes ONE synchronous decision → dispatches task to Band room
5. Upper Body + Lower Body agents receive task
6. Upper Body ↔ Lower Body: peer negotiation via Band (resolve physical conflicts)
7. Safety Agent reviews coordinated plan, vetoes if unsafe
8. Conductor synthesizes approved plan → final command → LiveKit → Robot guides the person
9. All steps → Arize Phoenix (traced)
```

---

## Observability (Arize Phoenix)

Every agent call instrumented:
- **Prompt in** — full system prompt + context
- **Output** — agent decision / plan
- **Latency** — per agent, surfaced in dashboard
- **Decision path** — cortical (slow) or reflex (fast)
- **Peer coordination messages** — Upper Body ↔ Lower Body negotiation
- **Veto events** — when Safety Agent blocks a command and why
- **Neuroplasticity diff** — before/after prompt changes between runs, correlated with smoother/safer navigation

Evaluator prompt: *did this decision keep the blind user safe and successfully navigate the environment?*

---

## Build Order

Follow strictly. Do not skip ahead.

1. **Nebius Physical Workbench** — required compute for UFB. Set up first, claim $150 credit via UFB Slack.
2. **LiveKit room** — connect to robot camera/depth stream (or webcam/sim fallback). Verify frames flowing.
3. **Vision Agent + Conductor in Band** — two agents passing messages. Minimum viable loop, unblocks everyone.
4. **Arize tracing** — instrument both agents. Verify traces appear in local dashboard.
5. **Upper Body + Lower Body agents** — add tactical agents responding to Conductor tasks in parallel.
6. **Peer coordination** — wire Upper Body ↔ Lower Body to negotiate via Band before executing.
7. **Threat Agent + Safety Agent** — hazard detection and veto/STOP logic live. Test an unsafe command getting blocked.
8. **Reflex Arc** — wire Threat Agent to bypass Conductor for fast-path STOP. Measure and log latency difference.
9. **Neuroplasticity loop** — Conductor reads Arize traces, rewrites agent prompts. One visible before/after.
10. **Demo dashboard** — Arize traces + robot feed side by side.

---

## Target Prizes

| Prize | Sponsor | Amount | How We Win |
|-------|---------|--------|------------|
| Physical AI Hack | UFB | $3,000 | End-to-end assistive robot control, production-grade hierarchical architecture |
| Multi-agent collaboration | Band | $1,000 | 5+ agents, two distinct comms patterns (top-down + peer), all external agents |
| Observability improves the app | Arize | $1,000 | Live fMRI dashboard + neuroplasticity before/after, evaluator on user safety |
| Science/Engineering | Ddoski's Lab | $5,000 | Novel hierarchical latency design + peer tactical coordination + social impact framing |

**Total potential: $10,000**

---

## Team

| Member | Area | Owns |
|--------|------|------|
| **Eshwar** | Agent Architecture & Band (The Brain) | Conductor, Upper Body, Lower Body, Threat agents; Reflex Arc; Neuroplasticity loop |
| **Advaita** | Nebius & Vision Agent (The Eyes) | Nebius compute platform setup; Vision Agent perception |
| **Adil** | LiveKit & Robot I/O (The Body) | LiveKit room/streaming; Conductor command → LiveKit → robot return path; webcam fallback sim; UFB booth lead |
| **Matthew** | Observability, Safety & Demo (The Reflexes & fMRI) | Arize Phoenix; Safety Agent; evaluator prompt; demo dashboard; Arize booth lead |

See `roles.md` for full responsibilities, deliverables, and hour-by-hour build order.

---

## Tech Stack

| Tool | Notes |
|------|-------|
| Python 3.11+ | Primary language |
| `anthropic` SDK | Claude API — `claude-sonnet-4-6` or latest |
| Band SDK | LangChain or CrewAI — Eshwar decides early, everyone follows |
| Arize Phoenix | `pip install arize-phoenix` — local, no API key |
| LiveKit Python SDK | Sensor stream in, motor commands out |
| LangChain or CrewAI | Agent framework — consistent across all agents |
| Nebius Physical Workbench | UFB's required compute platform — set up before anything else |

---

## Key Constraints

- **Hackathon rule**: no pre-built code. Everything written June 20–21.
- **Conductor is synchronous** — one decision at a time. Intentional. Prevents desync on the critical path.
- **Tactical agents coordinate peer-to-peer** — they negotiate with each other via Band before executing, not just receive top-down orders.
- **One job per agent** — short, focused system prompts. Do not combine responsibilities.
- **External agents on Band** — register with `agent name` + `API key`, run in our process.
- **Nebius first** — Advaita sets this up before LiveKit or anything else robot-side.
- **Fallback**: webcam sim if UFB hardware unavailable. Do not block on hardware.

---

## Open Questions

- LangChain vs CrewAI — Eshwar decides early, everyone follows
- Band room message schema — how do peer-to-peer tactical messages differ from top-down conductor messages? Same room, tagged differently?
- UFB robot API and control interface at the event
- Arize trace API — how Conductor reads traces programmatically for neuroplasticity loop

---

## Status

**Architecture locked. Use case locked (assistive guide robot for blind people). Name: Baymax. No code written yet.**

Waiting on:
- [ ] Nebius Physical Workbench setup + UFB compute credit
- [ ] Band docs / API
- [ ] Arize Phoenix integration docs
- [ ] UFB robot API / simulator details
- [ ] LiveKit setup
