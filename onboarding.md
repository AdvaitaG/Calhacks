# Welcome to NeuralPilot 🤖
### UC Berkeley AI Hackathon 2026

Hey, welcome to the team. This doc gets you up to speed fast. Read this first, then `project_context.md` for the deep technical detail, and `roles.md` to see who owns what.

---

## The Idea in 30 Seconds

We're building an AI system that controls a humanoid robot — but instead of one big AI doing everything, we split control across multiple specialized agents, each mapped to a region of the human brain. The robot has a nervous system.

- **Prefrontal Cortex** → Conductor Agent (strategy, orchestration)
- **Motor Cortex** → Upper Body Agent (arms, strikes)
- **Cerebellum** → Lower Body Agent (balance, footwork)
- **Amygdala** → Threat Agent (detects danger, triggers fast reactions)
- **Brainstem** → Safety Agent (reflexes, vetoes unsafe commands)
- **Sensory Cortex** → Vision Agent (sees the world via camera)

They all talk to each other through **Band** (a multi-agent communication platform), receive video from the robot via **LiveKit**, and every single decision gets traced in real time by **Arize Phoenix** — which we're calling the fMRI of the robot's brain.

---

## Why This Is Novel

Most teams will wire one agent directly to a robot and call it done. We're doing something fundamentally different:

1. **Parallel agents with conflicting constraints** — the upper body wants to throw a strike, the lower body is managing balance. They negotiate. Just like your body does.

2. **Two decision speeds** — slow deliberate decisions go through the Conductor (cortical path, ~800ms). Time-critical reactions bypass the Conductor entirely via a **Reflex Arc** (~90ms), just like spinal cord reflexes bypass your brain.

3. **The robot gets smarter between rounds** — after each round, the Conductor reads the Arize traces, identifies which agent decisions failed, and rewrites those agents' prompts. The robot visibly improves. We call this **Neuroplasticity**.

---

## The Tech We're Using

| Tool | What It Does in Our Project |
|------|-----------------------------|
| **UFB (Ultimate Bots)** | The humanoid robot or fight simulator we're controlling |
| **Nebius Physical Workbench** | UFB's partner platform — how we access the physical AI environment |
| **Band** | The communication layer between all agents (like neural pathways) |
| **LiveKit** | Streams robot camera feed to agents; sends commands back to the robot |
| **Arize Phoenix** | Traces every agent decision in real time — the fMRI dashboard |
| **Claude API** | The LLM powering every agent's reasoning |
| **Python** | Primary language |
| **LangChain or CrewAI** | Agent framework — Eshwar is deciding, everyone follows his call |

---

## How It All Connects

```
Robot → LiveKit (camera in) → Vision Agent → Band Room
                                                  ├── Conductor (strategy)
                                                  ├── Upper Body Agent (arms)
                                                  ├── Lower Body Agent (balance)
                                                  ├── Threat Agent (danger detection)
                                                  └── Safety Agent (veto)
                                                        ↓
                                              Conductor → LiveKit → Robot command
                                                        ↓
                                                  Arize Phoenix
                                              (traces everything)
```

**Fast path (Reflex Arc):** Threat Agent detects incoming strike → directly triggers Safety + Joint Agents → command fires in ~90ms, bypassing the Conductor entirely.

**Between rounds (Neuroplasticity):** Conductor reads Arize traces → rewrites underperforming agent prompts → next round the robot fights better.

---

## The Demo Story

This is the arc we're presenting to judges:

1. **Round 1:** Robot fights with baseline prompts. Arize dashboard is live next to the fight — judges watch agent decisions light up like brain regions firing.
2. **Between rounds:** Conductor reads the traces. Identifies that the Upper Body Agent overcommitted on strikes. Rewrites its prompt live.
3. **Round 2:** Robot adapts. Fights smarter. Arize shows the before/after prompt diff.
4. **Punchline:** *"This is what it looks like when a robot has a nervous system — not a script."*

---

## Prizes We're Going After

| Prize | Who | Amount | Why We Win |
|-------|-----|--------|------------|
| Physical AI Hack | UFB | $3,000 | End-to-end robot control, real robotics architecture |
| Multi-agent collaboration | Band | $1,000 | 5+ agents coordinating through Band |
| Observability improves the app | Arize | $1,000 | fMRI demo + neuroplasticity before/after |
| Science/Engineering | Ddoski's Lab | $5,000 | Reflex Arc is a novel engineering contribution |

**Total we're targeting: $10,000**

---

## Team & Ownership

See `roles.md` for the full breakdown. Short version:

- **Eshwar** — Band room, all agents (Conductor, Upper Body, Lower Body, Threat), Reflex Arc, Neuroplasticity loop
- **Advaita** — LiveKit, Vision Agent, robot I/O, webcam fallback sim
- **Matthew** — Arize Phoenix, Safety Agent, evaluator prompt, demo dashboard

---

## Where to Start

1. Read `project_context.md` — full technical detail on every agent, every decision path, the full build order
2. Read `roles.md` — find your deliverables and the hour-by-hour schedule
3. Set up your environment: Python 3.11+, `anthropic` SDK, Band SDK, Arize Phoenix (`pip install arize-phoenix`), LiveKit Python SDK
4. Don't start coding until you've talked to the team — the Band room and LiveKit stream need to be up first or everyone is blocked

---

## Key Rules

- **One job per agent.** Do not combine responsibilities. Short, focused system prompts.
- **External agents on Band** — agents run in our code, register with Band via `agent name` + `API key`. They don't live on Band.
- **Follow the build order in `project_context.md`** — don't jump ahead or everyone steps on each other.
- **Hardware fallback:** if UFB robot isn't available, we use Nebius Physical Workbench or a webcam sim. Do not block on hardware.
- **No pre-built code** — hackathon rule, everything written June 20–21.
