# Welcome to Baymax 🤖
### UC Berkeley AI Hackathon 2026

Hey, welcome to the team. This doc gets you up to speed fast. Read this first, then `project_context.md` for the deep technical detail, and `roles.md` to see who owns what.

---

## The Idea in 30 Seconds

We're building an AI system that controls a humanoid GUIDE robot — but instead of one big AI doing everything, we split control across multiple specialized agents, each mapped to a region of the human brain. The robot has a nervous system. Think Big Hero 6's Baymax: a personal healthcare companion that safely guides a person through the world. Our flagship demo guides a **blindfolded** person along a route, detecting hazards and steering them with gentle physical guidance.

- **Sensory Cortex** → Vision Agent (perceives the scene: obstacles, people, vehicles, terrain, crosswalks)
- **Prefrontal Cortex** → Conductor Agent (plans the safe route, orchestrates the agents)
- **Motor Cortex** → Upper Body Agent (guiding arm + hand signals: left, right, stop, forward)
- **Cerebellum** → Lower Body Agent (walking pace, stops at curbs/stairs, adjusts for terrain)
- **Amygdala** → Threat Agent (detects vehicles/obstacles/sudden danger, triggers fast reactions)
- **Brainstem** → Safety Agent (reflexes, vetoes unsafe navigation commands)

They all talk to each other through **Band** (a multi-agent communication platform), receive video from the robot via **LiveKit**, and every single decision gets traced in real time by **Arize Phoenix** — which we're calling the fMRI of the robot's brain.

> **One sentence:** We built a nervous system for a humanoid robot — each AI agent maps to a region of the human brain, they communicate through Band the way neurons fire signals, and Arize makes every decision visible like an fMRI of the robot's mind — all to safely guide a person through the world.

---

## Why This Is Novel

Most teams will wire one agent directly to a robot and call it done. We're doing something fundamentally different:

1. **Parallel agents with conflicting constraints** — the upper body wants to signal a turn, the lower body is managing walking pace and terrain. They negotiate. Just like your body does.

2. **Two decision speeds** — slow deliberate decisions go through the Conductor (cortical path, ~800ms). Time-critical reactions bypass the Conductor entirely via a **Reflex Arc** (~90ms), just like spinal cord reflexes bypass your brain — for example, an emergency STOP when a vehicle or obstacle suddenly appears.

3. **The robot gets smarter between runs** — after each run, the Conductor reads the Arize traces, identifies which agent decisions failed, and rewrites those agents' prompts. Navigation gets visibly smoother and safer. We call this **Neuroplasticity**.

---

## The Tech We're Using

| Tool | What It Does in Our Project |
|------|-----------------------------|
| **UFB (Ultimate Bots)** | The humanoid guide robot (or simulator) we're controlling |
| **Nebius Physical Workbench** | UFB's required compute platform — how we access the physical AI environment |
| **Band** | The communication layer between all agents (like neural pathways) |
| **LiveKit** | Streams robot camera feed to agents; sends commands back to the robot |
| **Arize Phoenix** | Traces every agent decision in real time — the fMRI dashboard |
| **Claude API** | The LLM (`claude-sonnet-4-6`) powering every agent's reasoning |
| **Python** | Primary language (3.11+) |
| **LangChain or CrewAI** | Agent framework — Eshwar is deciding, everyone follows his call |

---

## How It All Connects

```
Robot → LiveKit (camera in) → Vision Agent → Band Room
                                                  ├── Conductor (route planning)
                                                  ├── Upper Body Agent (hand signals)
                                                  ├── Lower Body Agent (walking pace)
                                                  ├── Threat Agent (hazard detection)
                                                  └── Safety Agent (veto)
                                                        ↓
                                              Conductor → LiveKit → Robot command
                                                        ↓
                                                  Arize Phoenix
                                              (traces everything)
```

**Fast path (Reflex Arc):** Threat Agent detects a critical hazard → directly triggers Safety STOP + Joint Agents → command fires in ~90ms, bypassing the Conductor entirely.

**Between runs (Neuroplasticity):** Conductor reads Arize traces → rewrites underperforming agent prompts → next run the robot guides more smoothly and safely.

---

## The Demo Story

This is the arc we're presenting to judges:

1. **Run 1:** Baymax guides a blindfolded person along a route with baseline prompts — hesitant, jerky, over-cautious. Arize dashboard is live next to the walk — judges watch agent decisions light up like brain regions firing.
2. **Between runs:** The Conductor reads the traces. Identifies a failure (e.g. the Lower Body Agent stopped too abruptly). Rewrites its prompt live.
3. **Run 2:** Baymax guides more smoothly and safely. Arize shows the before/after prompt diff.
4. **Reflex demo:** A sudden hazard (someone steps in, an obstacle appears) → Baymax STOPS in ~90ms via the reflex path.
5. **Punchline:** *"This is what it looks like when a robot has a nervous system — not a script."*

---

## Prizes We're Going After

| Prize | Who | Amount | Why We Win |
|-------|-----|--------|------------|
| Physical AI Hack | UFB | $3,000 | End-to-end robot control, production-grade robotics architecture |
| Multi-agent collaboration | Band | $1,000 | 5+ agents coordinating through Band |
| Observability improves the app | Arize | $1,000 | fMRI demo + neuroplasticity before/after, evaluator prompt |
| Science/Engineering | Ddoski's Lab | $5,000 | Reflex Arc = novel engineering + social impact (assistive guide robot) + bio-inspired architecture |

**Total we're targeting: $10,000**

---

## Team & Ownership

See `roles.md` for the full breakdown. Short version:

- **Eshwar** — Agent Architecture & Band (The Brain): Conductor, Upper Body, Lower Body, Threat agents; Reflex Arc; Neuroplasticity loop
- **Advaita** — Nebius & Vision Agent (The Eyes): Nebius compute platform + Vision Agent perception
- **Adil** — LiveKit & Robot I/O (The Body): LiveKit room/streaming, the return path (Conductor command → LiveKit → robot), webcam fallback sim, frame/command format docs; leads the UFB booth
- **Matthew** — Observability, Safety & Demo (The Reflexes & fMRI): Arize Phoenix, Safety Agent, evaluator prompt, demo dashboard

---

## Where to Start

1. Read `project_context.md` — full technical detail on every agent, every decision path, the full build order
2. Read `roles.md` — find your deliverables and the hour-by-hour schedule
3. Set up your environment: Python 3.11+, `anthropic` SDK, Band SDK, Arize Phoenix (`pip install arize-phoenix`), LiveKit Python SDK
4. **Set up Nebius first** — it's the required compute platform for UFB ($150 free compute/team via UFB Slack). Nothing else runs without it.
5. Don't start coding until you've talked to the team — the Band room and LiveKit stream need to be up first or everyone is blocked

---

## Key Rules

- **One job per agent.** Do not combine responsibilities. Short, focused system prompts.
- **External agents on Band** — agents run in our code, register with Band via `agent name` + `API key`. They don't live on Band.
- **Arize is local, no API key** — `pip install arize-phoenix` and run it locally.
- **Band prize floor is 2 agents** — but we're targeting 5+ to win it cleanly.
- **Hardware fallback:** if the UFB robot isn't available, we use a webcam sim worn by a teammate as the robot's eyes. Do not block on hardware.
- **No pre-built code** — hackathon rule, everything written June 20–21.
