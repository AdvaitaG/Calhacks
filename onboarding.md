# Welcome to Baymax
### UC Berkeley AI Hackathon 2026

Hey, welcome to the team. This doc gets you up to speed fast. Read this first, then `project_context.md` for the deep technical detail, and `roles.md` to see who owns what.

---

## The Idea in 30 Seconds

We're building an AI system that controls a **Booster K1** humanoid guide robot — but instead of one big AI doing everything, we split control across multiple specialized agents, each mapped to a region of the human brain. The robot has a nervous system. Think Big Hero 6's Baymax: a personal healthcare companion that safely guides people through the world.

**What makes us unique:** Baymax guides **two blind people simultaneously** — one person on each side. The UpperLeft arm agent focuses entirely on the person to its left. The UpperRight arm agent focuses entirely on the person to its right. They operate independently and can send different signals at the same time. That's only possible with a multi-agent nervous system.

- **Sensory Cortex** → Vision Agent (perceives the scene: obstacles, people, vehicles, terrain — with LEFT/RIGHT breakdown for each person)
- **Prefrontal Cortex** → Conductor Agent (plans the safe route, orchestrates all agents)
- **Motor Cortex (Left)** → UpperLeft Agent (left guiding arm — focused on the person on the left)
- **Motor Cortex (Right)** → UpperRight Agent (right guiding arm — focused on the person on the right)
- **Cerebellum** → Lower Agent (walking pace, stops at curbs/stairs, terrain)
- **Spinal Cord** → Spine Agent (fast-path reflex coordinator — HALTs all joint agents in ~90ms)
- **Amygdala** → Threat Agent (detects vehicles/obstacles/sudden danger, triggers fast reactions)
- **Brainstem** → Safety Agent (reflexes, vetoes unsafe navigation commands)

They all talk through **Band** (multi-agent communication platform), receive video from the robot via **LiveKit**, and every decision gets traced in real time by **Arize Phoenix** — the fMRI of the robot's brain.

> **One sentence:** We built a nervous system for a humanoid robot that simultaneously guides two blind people — each arm is an independent agent focused on its person, they communicate through Band the way neurons fire signals, and Arize makes every decision visible like an fMRI.

---

## Why This Is Novel

Most teams will wire one agent directly to a robot and call it done. We're doing something fundamentally different:

1. **Dual-person guidance** — two blind people, one robot, independent arm agents. The left arm can signal STOP while the right arm signals FORWARD. That's genuinely new.

2. **Parallel agents with conflicting constraints** — UpperLeft wants to signal a turn, Lower is managing terrain, UpperRight has its own task. They negotiate. Just like your body does.

3. **Two decision speeds** — slow deliberate decisions go through the Conductor (cortical path, ~800ms). Time-critical reactions bypass the Conductor entirely via a **Reflex Arc** (~90ms) through the Spine agent — for example, emergency STOP when a vehicle appears.

4. **The robot gets smarter between runs** — after each run, the Conductor reads the Arize traces, identifies which agent decisions failed, and rewrites those agents' prompts. Navigation gets visibly smoother and safer. We call this **Neuroplasticity**.

---

## The Tech We're Using

| Tool | What It Does in Our Project |
|------|-----------------------------|
| **UFB (Ultimate Bots)** | The Booster K1 humanoid guide robot (on-site at event) |
| **Nebius Physical Workbench** | UFB's required compute platform — how we access the physical AI environment |
| **Band** | The communication layer between all agents (like neural pathways) |
| **LiveKit** | Streams robot camera feed to agents; sends commands back to the robot |
| **Arize Phoenix** | Traces every agent decision in real time — the fMRI dashboard |
| **Gemini** | `gemini-1.5-flash` via `langchain-google-genai` — powers every agent |
| **LangGraph + LangChain** | Agent framework — `LangGraphAdapter` for Band. Eshwar decided, everyone follows. |
| **Python** | Primary language (3.11+) |

---

## How It All Connects

```
Booster K1 → LiveKit (camera in) → Vision Agent → Band Room (baymax-coordination)
                                                          ├── Conductor (route planning)
                                                          ├── UpperLeft Agent (left arm / left person)
                                                          ├── UpperRight Agent (right arm / right person)
                                                          ├── Lower Agent (walking pace)
                                                          ├── Spine Agent (fast reflex coordinator)
                                                          ├── Threat Agent (hazard detection)
                                                          └── Safety Agent (veto)
                                                                ↓
                                                    Conductor → LiveKit → Robot command
                                                                ↓
                                                          Arize Phoenix
                                                      (traces everything)
```

**Fast path (Reflex Arc):** Threat detects CRITICAL → Spine immediately HALTs UpperLeft + UpperRight + Lower (~90ms, bypasses Conductor).

**Between runs (Neuroplasticity):** Conductor reads Arize traces → rewrites underperforming agent prompts → next run the robot guides more smoothly.

---

## The Demo Story

This is the arc we're presenting to judges:

1. **Run 1:** Baymax guides two blindfolded people along a route with baseline prompts — hesitant, jerky, over-cautious. Arize dashboard live next to the walk — judges watch agent decisions light up like brain regions firing.
2. **Between runs:** The Conductor reads the traces. Identifies a failure (e.g. the Lower Agent stopped too abruptly). Rewrites its prompt live.
3. **Run 2:** Baymax guides more smoothly and safely. Arize shows the before/after prompt diff.
4. **Reflex demo:** A sudden hazard (someone steps in) → Baymax STOPS in ~90ms via the Spine reflex path.
5. **Punchline:** *"This is what it looks like when a robot has a nervous system — not a script."*

---

## Prizes We're Going After

| Prize | Who | Amount | Why We Win |
|-------|-----|--------|------------|
| Physical AI Hack | UFB | $3,000 | End-to-end Booster K1 control, dual-person use case, production-grade architecture |
| Multi-agent collaboration | Band | $1,000 | 6+ agents coordinating through Band, two distinct comms patterns |
| Observability improves the app | Arize | $1,000 | fMRI demo + neuroplasticity before/after, evaluator prompt |
| Science/Engineering | Ddoski's Lab | $5,000 | Reflex Arc + dual-person guidance = novel engineering + social impact |

**Total we're targeting: $10,000**

---

## Team & Ownership

See `roles.md` for the full breakdown. Short version:

- **Eshwar** — Agent Architecture & Band: Conductor, UpperLeft, UpperRight, Lower, Threat, Spine agents; Reflex Arc; Neuroplasticity loop
- **Advaita** — Nebius & Vision Agent: Nebius compute platform + Vision Agent (with LEFT/RIGHT scene split)
- **Adil** — LiveKit & Robot I/O: LiveKit room/streaming, the return path (Conductor command → LiveKit → robot), webcam fallback sim; leads the UFB booth
- **Matthew** — Observability, Safety & Demo: Arize Phoenix, Safety Agent, evaluator prompt, demo dashboard

---

## Where to Start

1. Read `project_context.md` — full technical detail on every agent, every decision path, the full build order
2. Read `roles.md` — find your deliverables and the hour-by-hour schedule
3. Read your `*_READ_THIS.md` file if one exists for you
4. Set up your environment: Python 3.11+, `langchain-google-genai`, `langgraph`, `band`, `arize-phoenix`, LiveKit Python SDK
5. **Set up Nebius first** — required compute platform for UFB ($150 free compute/team via UFB Slack). Nothing else runs without it.
6. Don't start coding until you've talked to the team — the Band room and LiveKit stream need to be up first or everyone is blocked

---

## Key Rules

- **One job per agent.** Do not combine responsibilities. Short, focused system prompts.
- **External agents on Band** — agents run in our code, register with Band via `agent name` + `API key`. They don't live on Band.
- **Framework: LangGraph + Gemini** — `LangGraphAdapter` + `ChatGoogleGenerativeAI`. Eshwar decided, everyone follows.
- **Arize is local, no API key** — `pip install arize-phoenix` and run it locally.
- **Band room: `baymax-coordination`** — all agents join this one room.
- **Hardware fallback:** if the Booster K1 isn't available, we use a webcam sim worn by a teammate. Do not block on hardware.
- **No pre-built code** — hackathon rule, everything written June 20–21.
