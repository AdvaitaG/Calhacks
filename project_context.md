# Project Context — Autonomous Robot Multi-Agent System
### UC Berkeley AI Hackathon 2026 | June 20–21 | Deadline: 11:00 AM Sunday 6/21

> **This is the single source of truth for coding agents.** Read this before writing any code.

---

## What We Are Building

A multi-agent AI system that controls a humanoid robot (or fight simulator) in real time. Multiple specialized AI agents — each with a single focused job — perceive the environment, plan actions, and execute commands. They coordinate exclusively through Band (a multi-agent communication platform), receive visual/sensor data via LiveKit, and every decision is traced end-to-end through Arize Phoenix.

The core novelty: instead of one monolithic agent controlling the robot, control is decomposed across specialized agents with distinct responsibilities. This mirrors how real robotics teams are structured and makes the system more modular, debuggable, and extensible.

---

## Sponsor Technologies

### 1. UFB — Ultimate Bots (Physical AI / Robot Target)
- Humanoid sports league providing the robot or fight simulator we are controlling
- Prize track: **Physical AI Hack — $3,000**
- UFB provides **$150 free compute per team** (via their Slack channel)
- If real hardware is unavailable at the event, fall back to their simulator or a webcam-based sim
- Judging bar: "Would a real robotics team use it?" — frame everything around production-grade robotics thinking

### 2. Band (Multi-Agent Communication Platform)
- Prize track: **Multi-agent collaboration — $1,000**
- Band is the communication backbone. All agents talk to each other through a **Band shared room**
- Each agent is an **external/remote agent** — it runs in whatever framework we choose (LangChain, CrewAI, plain Python) and registers with Band using:
  - `agent name`
  - `API key`
- Agents do NOT live on Band — they just communicate through it
- Band SDK supports **LangChain** and **CrewAI** — pick one and be consistent
- Minimum **2 agents communicating through Band** to qualify for the Band prize
- Key design rule: **one job per agent**, keep prompts short and focused

### 3. Arize Phoenix (Observability & Eval)
- Prize track: **Observability improves the app — $1,000**
- Fully open source, runs locally, **no API key needed**
- Traces every agent call: prompt in, output, confidence, latency
- Fits into the **product loop** — not just dev debugging. Every coordination decision between agents is observable, evaluable, and improvable
- Live dashboard shows agent decision traces alongside the robot feed
- Arize checklist to win their prize:
  1. Turn on tracing
  2. Look at the traces
  3. Create an evaluator (LLM prompt that judges decision quality)
  4. Use feedback to visibly improve agent behavior
  5. Tell them at their booth

### 4. LiveKit (Real-Time Streaming)
- Real-time video/audio/data streaming between the robot and cloud agents
- Vision Agent receives the robot camera feed via LiveKit
- Coordinator Agent sends final commands back to the robot via LiveKit
- If UFB doesn't support real-time control, use LiveKit for video monitoring only and simulate robot commands

### 5. Claude API (LLM Backend)
- Powers every agent's reasoning
- Use the latest capable model (claude-sonnet-4-6 or better) for each agent
- Keep per-agent system prompts tight — one responsibility per prompt

---

## Agent Architecture

```
Robot (UFB hardware or sim)
  └── LiveKit stream (camera feed in)
        └── Vision Agent
              └── Band Room
                    ├── Planning Agent
                    ├── Safety Agent
                    └── Coordinator Agent → LiveKit → Robot command (out)
```

### Agent Roles

| Agent | Job | Input | Output |
|-------|-----|-------|--------|
| **Vision Agent** | Perceives the scene | LiveKit camera feed | Text description of current state (position, obstacles, opponent, etc.) |
| **Planning Agent** | Decides next action | Vision Agent output via Band | Proposed action / command |
| **Safety Agent** | Validates decisions | Planning Agent output via Band | Approved or vetoed action + reason |
| **Coordinator Agent** | Synthesizes and executes | All agent outputs via Band | Final command sent to robot via LiveKit |

### Data Flow (step by step)
```
1. Robot → LiveKit stream → Vision Agent (sees the world)
2. Vision Agent → Band Room → Planning Agent (decides what to do)
3. Planning Agent → Band Room → Safety Agent (checks if it's safe)
4. Safety Agent → Band Room → Coordinator Agent (synthesizes)
5. Coordinator Agent → LiveKit → Robot command (acts)
6. All steps → Arize Phoenix (every call traced)
```

---

## Observability Layer (Arize Phoenix)

Every agent call is instrumented:
- **What went in** — full prompt + context
- **What came out** — agent response
- **Confidence / reasoning** — surfaced in trace
- **Latency** — per agent, per round-trip
- **Coordination failures** — when Safety Agent vetoes, log why

The evaluator prompt should judge: did this decision lead to a good robot outcome? Use that signal to visibly improve agent prompts round over round — this is the demoable before/after Arize wants to see.

---

## Build Order

Follow this strictly. Do not jump ahead.

1. **LiveKit room** — connect to robot video stream (or webcam sim). Verify frames are flowing.
2. **Band room + 2 agents** — Vision Agent + Planning Agent passing messages through Band. Minimum viable multi-agent loop.
3. **Arize Phoenix** — instrument every agent call. Verify traces appear in dashboard.
4. **Safety Agent** — add veto logic. Test that a bad command gets blocked.
5. **Coordinator Agent** — synthesize all inputs, send final command back via LiveKit.
6. **Evaluator** — build the Arize evaluator prompt. Get one visible before/after improvement.
7. **Frontend dashboard** — live agent traces + robot feed side by side (for demo).

---

## Target Prizes

| Prize | Sponsor | Amount |
|-------|---------|--------|
| Physical AI Hack | UFB (Ultimate Bots) | $3,000 |
| Multi-agent collaboration | Band | $1,000 |
| Observability improves the app | Arize | $1,000 |
| Science/Engineering track | Ddoski's Lab | $5,000 |

**Total potential: $10,000**

To qualify for each:
- **UFB**: robot (or sim) must be controlled end-to-end by the system. Demo must feel like something a real robotics team would build.
- **Band**: minimum 2 external agents communicating through a Band room. More agents = stronger story.
- **Arize**: tracing on, evaluator built, demonstrable improvement from eval feedback. Tell them at their booth.
- **Ddoski's Lab**: science/engineering framing — emphasize the architecture, modularity, and real-world applicability.

---

## Tech Stack

| Tool | Version / Notes |
|------|----------------|
| Python | 3.11+ |
| Claude API | `claude-sonnet-4-6` (or latest) via `anthropic` SDK |
| Band SDK | LangChain or CrewAI integration — pick one |
| Arize Phoenix | Open source, run locally (`pip install arize-phoenix`) |
| LiveKit | Python SDK for robot video stream |
| LangChain or CrewAI | Agent framework — must be consistent across all agents |

---

## Key Constraints & Notes

- **Hackathon rule**: no pre-built code. Everything written during the hacking window (June 20–21).
- **One job per agent** — do not give any single agent multiple responsibilities. Short, focused prompts.
- **External agents only** on Band — register with name + API key, run in our own process.
- **Fallback plan**: if UFB hardware not available, use their sim or a webcam feed with simulated robot commands. Do not block on hardware.
- **Arize is local** — no API key, no account needed. Just `pip install` and run.
- **Band prize floor**: 2 agents minimum. Build Vision + Planning first, add Safety + Coordinator after.

---

## Open Questions (resolve as docs arrive)

- Which agent framework: LangChain vs CrewAI? (Band SDK supports both)
- UFB hardware availability and API/control interface at the event
- Band room API specifics — message schema, how agents subscribe/publish
- Specific fight scenario / use case that makes the multi-agent decomposition feel necessary (e.g. conflicting constraints: offense vs. balance, or simultaneous upper/lower body coordination)

---

## Status

**Idea phase. No code written yet.**

Waiting on:
- [ ] Band docs / API
- [ ] Arize Phoenix integration docs
- [ ] UFB robot API / simulator access
- [ ] LiveKit setup details
