# Project Context — Baymax: Agentic Nervous System for a Humanoid Guide Robot
### UC Berkeley AI Hackathon 2026 | June 20–21 | MLK Jr. Student Union | Deadline: 11:00 AM Sunday 6/21

> **This is the single source of truth for coding agents.** Read this before writing any code.

---

## The Idea (One Sentence)
We built a nervous system for a humanoid robot — each AI agent maps to a region of the human brain, they communicate through Band the way neurons fire signals, and Arize makes every decision visible like an fMRI of the robot's mind — all to safely guide a person through the world.

---

## What We Are Building

**Baymax** — a multi-agent AI system that controls a humanoid GUIDE robot (UFB hardware or sim) in real time, architected explicitly as a biological nervous system. Instead of one monolithic AI, control is decomposed across specialized agents that each mirror a brain region: the conductor (prefrontal cortex) plans the safe route, the motor cortex (upper body) drives the guiding arm and hand signals, the cerebellum (lower body) manages walking pace and terrain, the amygdala (threat agent) detects hazards, and the brainstem (safety agent) handles reflexes and vetoes. The flagship demo is guiding a **blindfolded person** along a route — detecting hazards and steering them with gentle physical guidance. This is an assistive / accessibility framing — think Big Hero 6's Baymax, a personal healthcare companion.

Three layers make this novel:
1. **Baymax** — the brain-mapped agent architecture (the structure)
2. **Reflex Arc** — a fast path (~90ms) where the Threat Agent bypasses the Conductor for time-critical decisions (e.g. emergency STOP when a vehicle or obstacle suddenly appears), just like a spinal-cord reflex bypasses the brain
3. **Neuroplasticity** — between runs, Arize traces are read by the Conductor to rewrite agent prompts, visibly improving how smoothly and safely the robot guides the person between runs

---

## Narrative for Presentation
> *"The human body isn't controlled by one brain region — your cerebellum handles balance, your motor cortex handles movement, your amygdala handles threat response, all firing in parallel. We built that architecture in AI. Baymax is the first humanoid robot that safely guides a person through the world controlled by a nervous system, not a script."*

The demo arc:
- **Run 1:** Baymax guides a blindfolded person along a route with baseline agent prompts — hesitant, jerky, over-cautious. The Arize dashboard runs live beside the walk; judges watch every agent decision light up like brain regions firing.
- **Between runs:** Conductor reads Arize traces, identifies failures (e.g. Lower Body stopped too abruptly), rewrites agent prompts live (neuroplasticity).
- **Run 2:** Baymax guides more smoothly and safely. Arize shows the before/after prompt diff.
- **Reflex demo:** a sudden hazard appears (someone steps in / an obstacle drops in) → Baymax STOPS in ~90ms via the reflex path.
- **Closing line:** *"This is what it looks like when a robot has a nervous system — not a script."*

---

## Sponsor Technologies

### 1. UFB — Ultimate Bots (Physical AI / Robot Target)
- Humanoid robotics platform providing the robot or simulator we are controlling as a guide
- Prize track: **Physical AI Hack — $3,000**
- UFB provides **$150 free compute per team** (via their Slack channel)
- If real hardware is unavailable at the event, fall back to their simulator or a webcam-based sim
- Judging bar: "Would a real robotics team use it?" — Baymax answers yes: real robotics teams decompose control exactly this way (separate controllers for pace, arm movement, hazard response)
- **Nebius is the required compute platform for UFB** — do not attempt to run UFB without Nebius

### 2. Nebius (GPU Cloud Compute — Essential for UFB)
- Nebius Physical Workbench is the compute layer that makes the UFB robot/sim accessible
- **Required** — UFB integration does not work without Nebius. Set this up before anything else in the robot I/O layer.
- Provides the GPU infrastructure for running agent inference at the speed needed for real-time robot control
- UFB's $150 free compute per team is provisioned through Nebius (claim via UFB Slack channel)
- Advaita owns setup and integration (see roles.md)

### 3. Band (Multi-Agent Communication Platform)
- Prize track: **Multi-agent collaboration — $1,000**
- Band is the "neural pathway" — agents communicate through a shared Band room the way brain regions send signals
- Each agent is an **external/remote agent** — runs in whatever framework we choose, registers with Band via `agent name` + `API key`
- Agents do NOT live on Band — they communicate through it
- Band SDK supports **LangChain** and **CrewAI** — pick one and stay consistent
- Minimum **2 agents through Band** to qualify for prize — we will have 5+
- Key design rule: **one job per agent**, short focused prompts, mirrors single-responsibility of brain regions

### 5. Arize Phoenix (Observability — "The fMRI")
- Prize track: **Observability improves the app — $1,000**
- Fully open source, runs locally, **no API key needed** (`pip install arize-phoenix`)
- In our framing: Arize is the fMRI of the robot's brain — judges watch agent decisions light up in real time alongside the walk
- Traces every agent call: prompt in, output, latency, which path was taken (cortical vs reflex)
- **Neuroplasticity loop:** between runs, Conductor reads Arize traces → identifies underperforming agents → rewrites their system prompts → measurable improvement next run
- Arize prize checklist:
  1. Tracing on for every agent call
  2. Dashboard visible during demo
  3. Evaluator prompt built (judges: did this decision keep the person safe and moving?)
  4. Feedback used to improve agent behavior (neuroplasticity = the before/after)
  5. Tell them at their booth

### 6. LiveKit (Real-Time Streaming — "The Senses")
- Real-time video/audio/data streaming between robot and cloud agents
- Vision Agent (sensory cortex) receives robot camera feed via LiveKit
- Conductor sends final navigation commands back to robot via LiveKit
- Fallback: if UFB doesn't support real-time control, use LiveKit for video only and simulate robot commands
- Adil owns this layer and the robot I/O return path (see roles.md)

### 7. Claude API (LLM — "The Neurons")
- Powers every agent's reasoning
- Use `claude-sonnet-4-6` or latest capable model
- Each agent has a tight, single-responsibility system prompt — one brain region, one job

---

## Agent Architecture — The Nervous System

```
                        ROBOT (UFB hardware or sim)
                              │
                    LiveKit stream (camera in)
                              │
                        Vision Agent
                  [Sensory Cortex — perceives scene,
                   obstacles, people, vehicles, terrain]
                              │
                         Band Room
              ┌──────────────┼──────────────────┐
              │              │                  │
    Conductor Agent    Threat Agent       Safety Agent
   [Prefrontal Cortex] [Amygdala —      [Brainstem —
    plans safe route]   detects hazards] reflexes, STOP veto]
              │
      ┌───────┴───────┐
      │               │
Upper Body Agent  Lower Body Agent
[Motor Cortex —   [Cerebellum —
 hand signals:     walking pace,
 left/right/stop]  curbs/stairs/terrain]
              │
    Conductor finalizes
              │
        LiveKit → Robot command (out)
```

### Two Decision Paths

**Cortical Path (deliberate, ~800ms):**
Vision → Conductor → Joint Agents (Upper + Lower in parallel) → Safety → Conductor → Command
Used for: route planning, turns, walking pace, crosswalk and curb decisions

**Reflex Arc (fast, ~90ms):**
Threat Agent detects critical hazard → directly triggers Safety STOP + Joint Agents, bypassing Conductor
Used for: emergency stop, sudden obstacle or vehicle avoidance
Arize logs which path was taken for every decision.

### Agent Roles

| Agent | Brain Region | Job | Input | Output |
|-------|-------------|-----|-------|--------|
| **Vision Agent** | Sensory Cortex | Perceives the scene: obstacles, people, vehicles, terrain, crosswalks | LiveKit camera feed | Scene description broadcast to Band room |
| **Conductor Agent** | Prefrontal Cortex | Plans the safe navigation route, synthesizes final command | Vision output + Arize traces (between runs) | Navigation task to all agents; final command to LiveKit |
| **Upper Body Agent** | Motor Cortex | Controls the guiding arm + hand signals: gentle left, right, stop, forward | Conductor task + scene | Arm + hand-signal action plan |
| **Lower Body Agent** | Cerebellum | Manages walking pace, stops at curbs/stairs, adjusts for terrain | Conductor task + scene | Pace + footing action plan |
| **Threat Agent** | Amygdala | Detects vehicles/obstacles/sudden danger | Scene description | Urgency signal; fires reflex arc if critical |
| **Safety Agent** | Brainstem | Vetoes unsafe navigation commands, fires the STOP signal | All agent outputs | Approved or vetoed action + reason (logged to Arize) |

### Neuroplasticity Loop (between runs)
```
Run ends
  → Arize has full trace of every agent decision + outcome
  → Conductor reads traces via Arize API
  → Identifies: which agent decisions correlated with hesitation / abrupt stops / unsafe steps
  → Rewrites underperforming agents' system prompts with corrected guidance strategy
  → Next run begins with updated "brain"
  → Arize shows before/after prompt diff
```

### Data Flow (full cortical path)
```
1. Robot → LiveKit → Vision Agent (sees the world)
2. Vision Agent → Band Room (broadcasts scene description)
3. Threat Agent reads scene → if critical, fires Reflex Arc (skip to step 7)
4. Conductor reads scene → issues navigation task to Band room
5. Upper Body + Lower Body agents plan in parallel (via Band)
6. Safety Agent reviews all plans, vetoes if unsafe
7. Conductor synthesizes approved plans → final command
8. Conductor → LiveKit → Robot guides the person
9. All steps → Arize Phoenix (traced)
```

---

## Observability Layer (Arize Phoenix — "The fMRI")

Every agent call instrumented:
- **Prompt in** — full system prompt + context passed to agent
- **Output** — agent decision / plan
- **Latency** — per agent, surfaced in dashboard
- **Decision path** — cortical (slow) or reflex (fast)
- **Veto events** — when Safety Agent blocks a command and why
- **Neuroplasticity diff** — before/after prompt changes between runs, correlated with smoother, safer navigation

Live Arize dashboard = the demo visual. Runs locally next to the robot feed. Judges watch the brain light up.

---

## Build Order

Follow strictly. Do not jump ahead.

1. **Nebius Physical Workbench** — required compute platform for UFB. Set up first, claim the $150 credit via UFB Slack.
2. **LiveKit room** — connect to robot video stream (or webcam/sim fallback). Verify frames are flowing.
3. **Vision Agent + Conductor** — two agents in a Band room passing scene descriptions and navigation tasks. Minimum viable loop.
4. **Arize tracing** — instrument both agents. Verify traces appear in local dashboard.
5. **Upper Body + Lower Body agents** — add joint agents responding to Conductor tasks in parallel.
6. **Threat Agent + Safety Agent** — add amygdala (hazard detection) and brainstem (veto + STOP logic). Test an unsafe command getting blocked.
7. **Reflex Arc** — wire Threat Agent to bypass Conductor for fast-path STOP. Measure and log latency difference.
8. **Neuroplasticity loop** — Conductor reads Arize traces between runs, rewrites agent prompts. Get one visible before/after.
9. **Frontend dashboard** — Arize traces + robot feed side by side for demo.

---

## Target Prizes

| Prize | Sponsor | Amount | How We Win It |
|-------|---------|--------|---------------|
| Physical AI Hack | UFB | $3,000 | End-to-end robot control, production-grade robotics architecture, real robotics framing |
| Multi-agent collaboration | Band | $1,000 | 5+ agents coordinating through Band, clear coordination story |
| Observability improves the app | Arize Phoenix | $1,000 | fMRI demo + neuroplasticity before/after, evaluator prompt built |
| Science/Engineering track | Ddoski's Lab | $5,000 | Reflex Arc = novel engineering + social impact (assistive guide robot) + bio-inspired architecture |

**Total potential: $10,000**

> Nebius is the **required** compute platform for UFB ($150 free compute/team via UFB Slack). Set up first.

---

## Tech Stack

| Tool | Notes |
|------|-------|
| Python 3.11+ | Primary language |
| `anthropic` SDK | Claude API — `claude-sonnet-4-6` or latest |
| Band SDK | LangChain or CrewAI integration — pick one, stay consistent |
| Arize Phoenix | `pip install arize-phoenix` — local, no API key |
| LiveKit Python SDK | Robot video stream in, commands out |
| LangChain or CrewAI | Agent framework for all agents (Eshwar decides, all follow) |
| **Nebius Physical Workbench** | Required compute platform for UFB — set up first, before LiveKit. Provisions GPU infrastructure for real-time agent inference. |

---

## Key Constraints

- **Hackathon rule**: no pre-built code. Everything written June 20–21.
- **One job per agent** — single responsibility, short system prompts. Do not combine roles.
- **External agents only** on Band — each registers with `agent name` + `API key`, runs in our process.
- **Fallback**: if UFB hardware unavailable, use sim or webcam + simulated commands. Do not block on hardware.
- **Arize is local** — no API key, no account. `pip install` and run.
- **Band prize floor**: 2 agents minimum, but we target 5+.

---

## Team

| Member | Area | Owns |
|--------|------|------|
| **Eshwar** | Agent Architecture & Band (The Brain) | Conductor, Upper Body, Lower Body, Threat agents; Reflex Arc; Neuroplasticity loop |
| **Advaita** | Nebius & Vision Agent (The Eyes) | Nebius compute platform + Vision Agent perception |
| **Adil** | LiveKit & Robot I/O (The Body) | LiveKit room/streaming; the return path (Conductor command → LiveKit → robot); webcam fallback sim; frame/command format docs; leads the UFB booth |
| **Matthew** | Observability, Safety & Demo (The Reflexes & fMRI) | Arize Phoenix; Safety Agent; evaluator prompt; demo dashboard |

See `roles.md` for full responsibilities, deliverables, and the hour-by-hour build order.

---

## Open Questions

- Which agent framework: LangChain vs CrewAI? (Band supports both — Eshwar decides early)
- UFB hardware API and control interface at the event
- Band room message schema — how agents publish/subscribe
- Arize trace API — how Conductor reads traces programmatically for neuroplasticity loop

---

## Status

**Idea locked. No code written yet.**

Waiting on:
- [ ] Nebius Physical Workbench setup + UFB compute credit
- [ ] Band docs / API
- [ ] Arize Phoenix integration docs
- [ ] UFB robot API / simulator details
- [ ] LiveKit setup
