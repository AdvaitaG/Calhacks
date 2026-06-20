# Team Roles — Baymax
### UC Berkeley AI Hackathon 2026 | June 20–21

---

## Eshwar — Agent Architecture & Band (The Brain)

**Own the intelligence layer. Everything that happens inside the Band room.**

### Agents
- **Conductor Agent** (Prefrontal Cortex) — plans the safe navigation route, issues tasks to joint agents, synthesizes final command, reads Arize traces between sessions for neuroplasticity
- **Upper Body Agent** (Motor Cortex) — controls the guiding arm and hand signals: gentle left, right, stop, forward
- **Lower Body Agent** (Cerebellum) — manages walking pace, stops at curbs/stairs, adjusts for terrain
- **Threat Agent** (Amygdala) — reads scene description, detects vehicles/obstacles/sudden danger, fires reflex arc when critical

### Responsibilities
- Set up the Band shared room and register all agents
- Pick the agent framework (LangChain or CrewAI) — decide early, everyone follows
- Wire Upper Body + Lower Body to run in parallel (they don't wait on each other)
- Implement the **Reflex Arc**: Threat Agent bypasses Conductor for fast-path stop (~90ms)
- Implement the **Neuroplasticity loop**: Conductor reads Arize traces after each session, rewrites underperforming agent prompts, produces visible before/after diff

### Deliverables
- [ ] Band room running with Vision + Conductor passing messages (unblocks everyone)
- [ ] Upper Body + Lower Body agents responding in parallel to Conductor navigation tasks
- [ ] Threat Agent firing urgency signals into Band room
- [ ] Reflex Arc wired — latency measurably faster than cortical path
- [ ] Neuroplasticity loop: one visible prompt rewrite driven by Arize traces

### Stack
- Band SDK
- LangChain or CrewAI (your call — own this decision)
- Claude API (`claude-sonnet-4-6`) for all agent prompts
- Arize trace API (read side — for neuroplasticity loop)

---

## Advaita — Nebius & Vision Agent (The Eyes)

**Own the compute platform and the robot's perception layer. Nebius is your first task — nothing else works without it.**

### Agents
- **Vision Agent** (Sensory Cortex) — receives the robot's camera feed, describes the scene (obstacles, people, vehicles, terrain, crosswalks), broadcasts to Band room

### Responsibilities
- **First**: Set up Nebius Physical Workbench — required compute platform for UFB. Do this before everything else.
- Claim the UFB $150 compute credit via UFB Slack (provisioned through Nebius)
- Write the Vision Agent: camera frame in → Claude → scene description out → Band room
- Keep the Vision Agent prompt tight — one job: describe what you see accurately and concisely
- Coordinate with Adil on the LiveKit feed format so Vision Agent can consume frames correctly

### Deliverables
- [ ] Nebius Physical Workbench set up and running
- [ ] UFB compute credit claimed via UFB Slack
- [ ] Vision Agent consuming LiveKit frames and posting scene descriptions to Band room

### Stack
- **Nebius Physical Workbench** (start here)
- Claude API (Vision Agent prompt)
- Band SDK (Vision Agent publish)
- LiveKit Python SDK (receive side only — consuming frames from Adil's stream)

---

## Adil — LiveKit & Robot I/O (The Body)

**Own the real-time streaming layer and the physical connection to the robot.**

### Responsibilities
- Set up the LiveKit room and connect to the UFB robot camera feed (or webcam sim if hardware unavailable)
- Own the **return path**: receive the Conductor's final navigation command from Band and send it back to the robot via LiveKit
- Own the **fallback**: if UFB hardware isn't at the event, set up a webcam worn by a team member as the robot's eyes + simulate arm/body commands through LiveKit
- Coordinate with Advaita on frame format so Vision Agent can consume the stream
- Coordinate with Eshwar on command format so the Conductor's output maps to robot actions

### Deliverables
- [ ] LiveKit room running with camera frames flowing — this unblocks Advaita and the whole team
- [ ] Return path: Conductor command → LiveKit → robot or sim executes (guides the person)
- [ ] Webcam fallback sim ready if UFB hardware unavailable
- [ ] Frame format and command format documented for the team

### Stack
- LiveKit Python SDK
- UFB hardware or simulator API
- Band SDK (subscribe to Conductor's outbound command)
- Nebius (coordinate with Advaita — compute runs there)

---

## Matthew — Observability, Safety & Demo (The Reflexes & fMRI)

**Own the layer that makes Baymax trustworthy and demoable.**

### Agents
- **Safety Agent** (Brainstem) — monitors all agent outputs via Band, vetoes any unsafe navigation command instantly, fires the stop signal on the reflex arc, logs every veto to Arize with reason

### Responsibilities
- Set up **Arize Phoenix** locally and instrument every agent call (prompt in, output, latency, decision path — cortical vs reflex)
- Write the Safety Agent: subscribes to all Band room outputs, vetoes bad commands, stops the person if danger confirmed
- Build the **Arize evaluator prompt**: LLM judge that scores whether each navigation decision kept the person safe and moving
- Drive the Arize prize checklist: tracing on → traces reviewed → evaluator built → improvement visible → tell them at their booth
- Build the **frontend demo dashboard**: Arize traces + robot camera feed side by side, cortical vs reflex path labeled in real time
- Own the Arize booth visit

### Deliverables
- [ ] Arize Phoenix running locally with all agent calls traced
- [ ] Safety Agent with veto and stop logic live in Band room
- [ ] Evaluator prompt producing scores per navigation decision
- [ ] One visible before/after: eval feedback → prompt improvement → smoother navigation
- [ ] Demo dashboard: live agent traces + robot camera feed, paths labeled
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
| Frame format + command format interface | Adil documents, Advaita + Eshwar consume |
| End-to-end integration test | All four together |
| UFB booth | Adil leads |
| Band booth | Eshwar leads |
| Arize booth | Matthew leads |
| Ddoski's Lab pitch | All four — emphasize reflex arc, social impact, novel architecture |

---

## Hour-by-Hour Build Order

```
Hour 1–2
  Advaita  → Nebius up, UFB compute claimed
  Adil     → LiveKit room up, webcam sim running, frames flowing
  Eshwar   → Band room up, framework chosen, Vision + Conductor loop
  Matthew  → Arize Phoenix running locally, first agent instrumented

Hour 3–4
  Advaita  → Vision Agent consuming LiveKit frames, posting to Band room
  Adil     → Return path scaffolded: Conductor command → LiveKit → sim
  Eshwar   → Upper + Lower Body agents responding in parallel
  Matthew  → All agent calls traced in Arize dashboard

Hour 5–6
  Adil     → Return path fully working: robot/sim guiding person
  Eshwar   → Threat Agent + Reflex Arc wired, latency measured
  Matthew  → Safety Agent with veto and stop logic live in Band room

Hour 7–8
  Eshwar   → Neuroplasticity loop: Conductor reads traces, rewrites prompts
  Matthew  → Evaluator prompt built, before/after navigation improvement visible
  All      → End-to-end integration test: blindfolded walk demo, reflex arc demo

Hour 9+
  Matthew  → Demo dashboard polished
  All      → Edge cases, demo prep, booth talking points
```
