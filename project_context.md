# Project Context — UC Berkeley AI Hackathon 2026

## Core Idea
Multi-agent system that controls a humanoid robot (sim or real hardware from UFB) where each agent is responsible for a distinct segment of the robot. Agents plan independently but coordinate through the Band platform, with a main orchestration agent that issues high-level tasks.

## Architecture (rough)
- **Orchestrator agent** — receives the high-level task (e.g. "knock opponent off balance"), breaks it down, dispatches to sub-agents
- **Sub-agents** (one per body segment, e.g. upper body, lower body) — each plans and executes their part independently, communicating with each other through Band
- Agents negotiate and coordinate timing/strategy through Band before executing

## Sponsor Technologies
- **UFB** — the robot / fight simulator target. Hopefully real hardware provided at the event, otherwise sim.
- **Band** — the inter-agent communication layer. All agents talk to each other through Band. This is the architectural centerpiece. Each agent is an **external/remote agent** — it runs in whatever framework we choose, and authenticates with the Band platform via `agent name` + `API key`. Agents do not live on Band, they just communicate through it.
- **Arize** — observability. Currently scoped for dev debugging / error checking. May fit into the product loop (e.g. tracing agent coordination failures, evaluating decision quality) — TBD once we have more clarity on the use case.

## What Makes It Novel
Most teams will build a single monolithic agent or a simple chain. This approach splits control across specialized agents that communicate through a real platform (Band), mirroring how real robotics teams decompose control (e.g. separate controllers for upper/lower body with conflicting constraints that need negotiation).

## Open Questions
- Need a more specific use case / scenario that makes the multi-agent split feel necessary, not just architectural (e.g. simultaneous offense + balance management with genuinely conflicting constraints)
- Need Band and Arize docs/APIs before designing the integration
- Arize role in the actual product loop (vs. just dev tooling) — revisit once use case is sharper

## Status
- Idea phase. No code yet.
- Waiting on: Band docs/API, Arize docs, UFB sim/hardware details.
