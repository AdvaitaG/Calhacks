# UC Berkeley AI Hackathon 2026 — Robot Multi-Agent System

## Project Overview

A multi-agent AI system that controls a humanoid robot (Ultimate Bots) in real time. Multiple specialized AI agents coordinate via Band, communicate with the robot via LiveKit, and every agent decision is logged and monitored via Arize Phoenix.

**Goal:** A humanoid robot controlled by a team of AI agents that can see, plan, and act — with full observability into every decision the robot makes.

---

## Tech Stack

| Tool | Role |
|------|------|
| **LiveKit** | Real-time video/audio/data streaming between robot and cloud agents |
| **Band** | Multi-agent coordination platform (agents communicate in shared "rooms") |
| **Arize Phoenix** | Observability — traces every agent decision (open source, runs locally) |
| **Claude API** | LLM powering each agent |
| **Python** | Primary language |

---

## Agent Architecture

All agents communicate through a **Band shared room** with full context passing.

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

---

## Data Flow

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

Live dashboard shows agent decision traces in real time alongside the robot feed.

---

## Build Order

1. **LiveKit room setup** — connect to robot video stream (or simulate with webcam if robot API not available)
2. **Basic Band room** — Vision Agent + Planning Agent passing messages
3. **Arize Phoenix integration** — log all agent decisions
4. **Safety Agent** — veto capability over Planning Agent decisions
5. **Frontend dashboard** — live agent traces + robot feed

---

## Target Prizes

| Prize | Sponsor | Amount |
|-------|---------|--------|
| Physical AI Hack | Ultimate Bots | $3,000 |
| Multi-agent collaboration | Band | $1,000 |
| Observability improves the app | Arize | $1,000 |
| Science/Engineering track | Ddoski's Lab | $5,000 |

**Total potential:** $10,000

---

## Notes

- Ultimate Bots provides **$150 free compute per team**
- Arize Phoenix is fully open source — no API key needed, runs locally
- Band SDK supports LangChain and CrewAI
- If Ultimate Bots doesn't support real-time control, use LiveKit for video monitoring only and simulate robot commands
- Keep each agent prompt short and focused — **one job per agent**
- Start with 2 agents minimum to qualify for Band prize, then expand
