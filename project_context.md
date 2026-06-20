# Project Context — UC Berkeley AI Hackathon 2026

## Core Idea
Multi-agent system that controls a humanoid robot (sim or real hardware from UFB) in real time. Each agent is responsible for a distinct role. Agents plan and act independently but coordinate through the Band platform, with a main orchestration/coordinator agent synthesizing inputs and issuing final commands back to the robot.

**Goal:** A humanoid robot controlled by a team of AI agents that can see, plan, and act — with full observability into every decision the robot makes.

---

## Tech Stack

| Tool | Role |
|------|------|
| **LiveKit** | Real-time video/audio/data streaming between robot and cloud agents |
| **Band** | Multi-agent coordination platform — agents communicate in shared "rooms" |
| **Arize Phoenix** | Observability — traces every agent decision (open source, runs locally, no API key needed) |
| **Claude API** | LLM powering each agent |
| **Python** | Primary language |
| **LangChain / CrewAI** | Band SDK supports both — pick one as the agent framework |

---

## Agent Architecture

All agents communicate through a **Band shared room** with full context passing. Each agent is an **external/remote agent** — it runs in whatever framework we choose and authenticates with the Band platform via `agent name` + `API key`. Agents do not live on Band, they just communicate through it.

```
Robot
  └── LiveKit stream
        └── Vision Agent         ← describes what the robot sees
              └── Band Room
                    ├── Planning Agent    ← decides next action
                    ├── Safety Agent      ← monitors all decisions, can veto
                    └── Coordinator Agent ← sends final command back to robot via LiveKit
```

### Agent Roles
- **Vision Agent** — receives robot camera feed via LiveKit, outputs a description of the current scene
- **Planning Agent** — takes Vision Agent output, decides the next action
- **Safety Agent** — monitors all decisions, can override if a command is unsafe
- **Coordinator Agent** — synthesizes inputs from all agents, sends the final command back to the robot via LiveKit

### Data Flow
```
Robot → LiveKit stream → Vision Agent → Band Room → Planning Agent + Safety Agent → Coordinator Agent → LiveKit → Robot command
```

---

## Observability (Arize Phoenix)
Arize Phoenix traces every agent call:
- What prompt went in
- What came out
- Confidence level
- Latency

Live dashboard shows agent decision traces in real time alongside the robot feed. This fits into the **actual product loop** (not just dev debugging) — every coordination decision is observable and evaluable.

---

## Build Order
1. **LiveKit room setup** — connect to robot video stream (or simulate with webcam if robot API not available)
2. **Basic Band room** — Vision Agent + Planning Agent passing messages (minimum 2 agents to qualify for Band prize)
3. **Arize Phoenix integration** — log all agent decisions
4. **Safety Agent** — veto capability over Planning Agent decisions
5. **Frontend dashboard** — live agent traces + robot feed

---

## Target Prizes

| Prize | Sponsor | Amount |
|-------|---------|--------|
| Physical AI Hack | Ultimate Bots (UFB) | $3,000 |
| Multi-agent collaboration | Band | $1,000 |
| Observability improves the app | Arize | $1,000 |
| Science/Engineering track | Ddoski's Lab | $5,000 |

**Total potential: $10,000**

---

## Notes & Constraints
- UFB provides **$150 free compute per team**
- Arize Phoenix is fully open source — runs locally, no API key needed
- Band SDK supports LangChain and CrewAI
- If UFB doesn't support real-time control, use LiveKit for video monitoring only and simulate robot commands
- Keep each agent prompt short and focused — **one job per agent**
- Need minimum 2 agents communicating through Band to qualify for the Band prize

## Open Questions
- Specific use case / scenario that makes the multi-agent split feel *necessary* (e.g. conflicting constraints between body segments, simultaneous offense + balance management)
- Which agent framework to use: LangChain vs CrewAI
- Arize tracing integration details once we have docs
- UFB hardware availability at the event

## Status
- Idea phase. No code yet.
- Waiting on: Band docs/API, Arize docs, UFB/LiveKit details.
