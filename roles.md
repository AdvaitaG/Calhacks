# Team Roles — NeuralPilot
### UC Berkeley AI Hackathon 2026 | June 20–21

---

## Eshwar — Agent Architecture & Band (The Brain)

**Own the intelligence layer. Everything that happens inside the Band room.**

### Agents
- **Conductor Agent** (Prefrontal Cortex) — orchestrates strategy, issues tasks to joint agents, synthesizes final command, reads Arize traces between rounds for neuroplasticity
- **Upper Body Agent** (Motor Cortex) — plans strikes, arm movement; outputs shoulder/elbow/wrist action plan
- **Lower Body Agent** (Cerebellum) — plans balance and footwork; outputs hip/knee/ankle action plan
- **Threat Agent** (Amygdala) — reads scene description, detects incoming danger, fires reflex arc when critical

### Responsibilities
- Set up the Band shared room and register all agents
- Pick the agent framework (LangChain or CrewAI) — decide early, stays consistent across the whole project
- Wire Upper Body + Lower Body to run in parallel (they don't wait on each other)
- Implement the **Reflex Arc**: Threat Agent bypasses Conductor for fast-path decisions (~90ms path)
- Implement the **Neuroplasticity loop**: Conductor reads Arize traces after each round, rewrites underperforming agent prompts, produces visible before/after diff

### Deliverables
- [ ] Band room running with Vision + Conductor passing messages (unblocks everyone)
- [ ] Upper Body + Lower Body agents responding in parallel to Conductor tasks
- [ ] Threat Agent firing urgency signals into Band room
- [ ] Reflex Arc wired and latency difference measurable vs cortical path
- [ ] Neuroplasticity loop: one visible prompt rewrite driven by Arize traces

### Stack
- Band SDK
- LangChain or CrewAI (your call — own this decision)
- Claude API (`claude-sonnet-4-6`) for all agent prompts
- Arize trace API (read side — for neuroplasticity loop)

---

## Advaita — Robot I/O & LiveKit (The Senses & Body)

**Own everything between the robot and the agents. The nervous system's connection to the physical world.**

### Agents
- **Vision Agent** (Sensory Cortex) — receives robot camera feed via LiveKit, describes the scene, broadcasts to Band room
- **Conductor → Robot command** — wire the Conductor's final output back to the robot via LiveKit

### Responsibilities
- Set up LiveKit room and connect to UFB robot camera feed (or webcam sim if hardware isn't available yet)
- Write the Vision Agent: frame in → Claude → scene description out → Band room
- Wire the return path: Conductor final command → LiveKit → robot/sim executes
- Own the **fallback plan**: if UFB hardware isn't at the event, spin up a webcam sim so the team isn't blocked
- Claim the UFB $150 compute credit via their Slack channel
- Frame the robot demo for UFB judges: *"production-grade robotics team architecture"*

### Deliverables
- [ ] LiveKit room running with frames flowing — this unblocks Eshwar and Matthew
- [ ] Vision Agent posting scene descriptions to Band room
- [ ] Return path: Conductor command → LiveKit → robot or sim executes
- [ ] Webcam fallback sim ready if UFB hardware unavailable
- [ ] UFB compute credit claimed

### Stack
- LiveKit Python SDK
- UFB hardware or simulator API
- Claude API (Vision Agent prompt — keep it tight: describe what you see, nothing more)
- Band SDK (Vision Agent publish, Conductor subscribe for outbound command)

---

## Matthew — Observability, Safety & Demo (The Reflexes & fMRI)

**Own the layer that makes the system trustworthy and demoable. The brainstem and the fMRI.**

### Agents
- **Safety Agent** (Brainstem) — monitors all agent outputs via Band, vetoes any unsafe command instantly, logs every veto to Arize with reason

### Responsibilities
- Set up **Arize Phoenix** locally and instrument every agent call (prompt in, output, latency, decision path — cortical vs reflex)
- Write the Safety Agent: subscribes to all Band room outputs, vetoes bad commands, short-circuits the loop
- Build the **Arize evaluator prompt**: LLM judge that scores whether each agent decision led to a good robot outcome
- Drive the Arize prize checklist end to end: tracing on → traces reviewed → evaluator built → improvement visible → tell them at their booth
- Build the **frontend demo dashboard**: Arize traces + robot feed side by side, shows cortical vs reflex path in real time — this is what judges watch
- Own the Arize booth visit

### Deliverables
- [ ] Arize Phoenix running locally with all agent calls traced
- [ ] Safety Agent with veto logic live in Band room
- [ ] Evaluator prompt producing scores per agent decision
- [ ] One visible before/after: eval feedback → prompt improvement → better outcome
- [ ] Demo dashboard: live agent traces + robot feed, cortical vs reflex path labeled
- [ ] Arize booth demo ready

### Stack
- Arize Phoenix (`pip install arize-phoenix`) — local, no API key
- Band SDK (Safety Agent subscribes to all outputs)
- Claude API (Safety Agent prompt + evaluator prompt)
- Frontend: Streamlit or simple HTML/JS for dashboard

---

## Shared

| Task | Owner |
|------|-------|
| Repo & branching | Everyone |
| Agent framework choice (LangChain vs CrewAI) | Eshwar decides, everyone follows |
| Claude API key / env vars | Everyone sets up their own |
| End-to-end integration test | All three together |
| UFB booth | Advaita leads |
| Band booth | Eshwar leads |
| Arize booth | Matthew leads |
| Ddoski's Lab pitch | All three — emphasize architecture + reflex arc as novel engineering |

---

## Hour-by-Hour Build Order

```
Hour 1–2
  Advaita  → LiveKit room up, webcam sim running, frames flowing
  Eshwar   → Band room up, framework chosen, Vision + Conductor loop
  Matthew  → Arize Phoenix running locally, first agent instrumented

Hour 3–4
  Advaita  → Vision Agent posting scene descriptions to Band
  Eshwar   → Upper + Lower Body agents responding in parallel
  Matthew  → All agent calls traced in Arize dashboard

Hour 5–6
  Advaita  → Return path: Conductor → LiveKit → robot/sim executing
  Eshwar   → Threat Agent + Reflex Arc wired, latency measured
  Matthew  → Safety Agent with veto logic live in Band room

Hour 7–8
  Eshwar   → Neuroplasticity loop: Conductor reads traces, rewrites prompts
  Matthew  → Evaluator prompt built, before/after improvement visible
  All      → End-to-end integration test (full cortical + reflex paths)

Hour 9+
  Matthew  → Demo dashboard polished
  All      → Edge cases, demo prep, booth talking points
```
