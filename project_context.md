# Project Context — NeuralPilot: Agentic Nervous System for Humanoid Robots
### UC Berkeley AI Hackathon 2026 | June 20–21 | Deadline: 11:00 AM Sunday 6/21

> **This is the single source of truth for coding agents.** Read this before writing any code.

---

## The Idea (One Sentence)
We built a nervous system for a humanoid robot — each AI agent maps to a region of the human brain, they communicate through Band the way neurons fire signals, and Arize makes every decision visible like an fMRI of the robot's mind.

---

## What We Are Building

**NeuralPilot** — a multi-agent AI system that controls a humanoid robot (UFB hardware or sim) in real time, architected explicitly as a biological nervous system. Instead of one monolithic AI, control is decomposed across specialized agents that each mirror a brain region: the conductor (prefrontal cortex) issues strategy, the motor cortex (upper body) plans strikes, the cerebellum (lower body) manages balance, the amygdala (threat agent) detects danger, and the brainstem (safety agent) handles reflexes and vetoes.

Three layers make this novel:
1. **NeuralPilot** — the brain-mapped agent architecture (the structure)
2. **Reflex Arc** — a fast path that bypasses the conductor for time-critical decisions, just like spinal cord reflexes bypass the brain
3. **Neuroplasticity** — after each round, Arize traces are read by the Conductor to rewrite joint agent prompts, visibly improving the robot's behavior between rounds

---

## Narrative for Presentation
> *"The human body isn't controlled by one brain region — your cerebellum handles balance, your motor cortex handles movement, your amygdala handles threat response, all firing in parallel. We built that architecture in AI. NeuralPilot is the first humanoid robot controlled by a nervous system, not a script."*

The demo arc:
- **Round 1:** Robot fights with baseline agent prompts. Loses or struggles. Arize dashboard shows every agent decision in real time — judges watch the "brain" light up.
- **Between rounds:** Conductor reads Arize traces, identifies failures, rewrites joint agent prompts (neuroplasticity).
- **Round 2:** Robot fights differently. Visibly better. Arize shows the "before brain vs after brain" prompt diff.

---

## Sponsor Technologies

### 1. UFB — Ultimate Bots (Physical AI / Robot Target)
- Humanoid sports league providing the robot or fight simulator we are controlling
- Prize track: **Physical AI Hack — $3,000**
- UFB provides **$150 free compute per team** (via their Slack channel)
- If real hardware is unavailable at the event, fall back to their simulator or a webcam-based sim
- Judging bar: "Would a real robotics team use it?" — NeuralPilot answers yes: real robotics teams decompose control exactly this way (separate controllers for balance, arm movement, threat response)
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
- In our framing: Arize is the fMRI of the robot's brain — judges watch agent decisions light up in real time alongside the fight
- Traces every agent call: prompt in, output, latency, which path was taken (cortical vs reflex)
- **Neuroplasticity loop:** between rounds, Conductor reads Arize traces → identifies underperforming agents → rewrites their system prompts → measurable improvement next round
- Arize prize checklist:
  1. Tracing on for every agent call
  2. Dashboard visible during demo
  3. Evaluator prompt built (judges: did this decision lead to a good outcome?)
  4. Feedback used to improve agent behavior (neuroplasticity = the before/after)
  5. Tell them at their booth

### 6. LiveKit (Real-Time Streaming — "The Senses")
- Real-time video/audio/data streaming between robot and cloud agents
- Vision Agent (sensory cortex) receives robot camera feed via LiveKit
- Conductor sends final commands back to robot via LiveKit
- Fallback: if UFB doesn't support real-time control, use LiveKit for video only and simulate robot commands

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
                    [Sensory Cortex — perceives scene]
                              │
                         Band Room
              ┌──────────────┼──────────────────┐
              │              │                  │
    Conductor Agent    Threat Agent       Safety Agent
   [Prefrontal Cortex] [Amygdala —      [Brainstem —
    high-level strategy] detects danger]  reflexes, veto]
              │
      ┌───────┴───────┐
      │               │
Upper Body Agent  Lower Body Agent
[Motor Cortex —   [Cerebellum —
 strikes, arms]    balance, footwork]
              │
    Conductor finalizes
              │
        LiveKit → Robot command (out)
```

### Two Decision Paths

**Cortical Path (deliberate, ~800ms):**
Vision → Conductor → Joint Agents → Safety → Conductor → Command
Used for: strategy, planned strikes, positional decisions

**Reflex Arc (fast, ~90ms):**
Threat Agent detects critical input → directly triggers Safety + Joint Agents, bypassing Conductor
Used for: blocking incoming strikes, emergency balance recovery, collision avoidance
Arize logs which path was taken for every decision.

### Agent Roles

| Agent | Brain Region | Job | Input | Output |
|-------|-------------|-----|-------|--------|
| **Vision Agent** | Sensory Cortex | Perceives the scene | LiveKit camera feed | Scene description broadcast to Band room |
| **Conductor Agent** | Prefrontal Cortex | Orchestrates strategy | Vision output + Arize traces (between rounds) | High-level task to all agents; final command to LiveKit |
| **Upper Body Agent** | Motor Cortex | Plans strikes and arm movement | Conductor task + scene | Shoulder / elbow / wrist action plan |
| **Lower Body Agent** | Cerebellum | Plans balance and footwork | Conductor task + scene | Hip / knee / ankle action plan |
| **Threat Agent** | Amygdala | Detects incoming danger | Scene description | Urgency signal; triggers reflex arc if critical |
| **Safety Agent** | Brainstem | Vetoes unsafe commands | All agent outputs | Approved or vetoed action + reason |

### Neuroplasticity Loop (between rounds)
```
Round ends
  → Arize has full trace of every agent decision + outcome
  → Conductor reads traces via Arize API
  → Identifies: which agent decisions correlated with damage taken / missed strikes
  → Rewrites underperforming agents' system prompts with corrected strategy
  → Next round begins with updated "brain"
  → Arize shows before/after prompt diff
```

### Data Flow (full cortical path)
```
1. Robot → LiveKit → Vision Agent (sees the world)
2. Vision Agent → Band Room (broadcasts scene description)
3. Threat Agent reads scene → if critical, fires Reflex Arc (skip to step 7)
4. Conductor reads scene → issues high-level task to Band room
5. Upper Body + Lower Body agents plan in parallel (via Band)
6. Safety Agent reviews all plans, vetoes if unsafe
7. Conductor synthesizes approved plans → final command
8. Conductor → LiveKit → Robot executes
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
- **Neuroplasticity diff** — before/after prompt changes between rounds, correlated with outcome improvement

Live Arize dashboard = the demo visual. Runs locally next to the robot feed. Judges watch the brain light up.

---

## Build Order

Follow strictly. Do not jump ahead.

1. **LiveKit room** — connect to robot video stream (or webcam/sim fallback). Verify frames are flowing.
2. **Vision Agent + Conductor** — two agents in a Band room passing scene descriptions and tasks. Minimum viable loop.
3. **Arize tracing** — instrument both agents. Verify traces appear in local dashboard.
4. **Upper Body + Lower Body agents** — add joint agents responding to Conductor tasks in parallel.
5. **Threat Agent + Safety Agent** — add amygdala (urgency detection) and brainstem (veto logic). Test a bad command getting blocked.
6. **Reflex Arc** — wire Threat Agent to bypass Conductor for fast-path decisions. Measure and log latency difference.
7. **Neuroplasticity loop** — Conductor reads Arize traces between rounds, rewrites joint agent prompts. Get one visible before/after.
8. **Frontend dashboard** — Arize traces + robot feed side by side for demo.

---

## Target Prizes

| Prize | Sponsor | Amount | How We Win It |
|-------|---------|--------|---------------|
| Physical AI Hack | UFB | $3,000 | End-to-end robot control, production-grade architecture, real robotics framing |
| Multi-agent collaboration | Band | $1,000 | 5+ agents communicating through Band, clear coordination story |
| Observability improves the app | Arize | $1,000 | fMRI demo + neuroplasticity before/after, evaluator prompt built |
| Science/Engineering track | Ddoski's Lab | $5,000 | Reflex Arc = novel engineering insight, bio-inspired architecture paper-worthy |

**Total potential: $10,000**

---

## Tech Stack

| Tool | Notes |
|------|-------|
| Python 3.11+ | Primary language |
| `anthropic` SDK | Claude API — `claude-sonnet-4-6` or latest |
| Band SDK | LangChain or CrewAI integration — pick one, stay consistent |
| Arize Phoenix | `pip install arize-phoenix` — local, no API key |
| LiveKit Python SDK | Robot video stream in, commands out |
| LangChain or CrewAI | Agent framework for all agents |
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

## Open Questions

- Which agent framework: LangChain vs CrewAI? (Band supports both — decide early)
- UFB hardware API and control interface at the event
- Band room message schema — how agents publish/subscribe
- Arize trace API — how Conductor reads traces programmatically for neuroplasticity loop

---

## Status

**Idea locked. No code written yet.**

Waiting on:
- [ ] Band docs / API
- [ ] Arize Phoenix integration docs
- [ ] UFB robot API / simulator details
- [ ] LiveKit setup
