# Baymax — A Nervous System for a Humanoid Guide Robot

Baymax is a humanoid guide robot that safely walks a blindfolded person through
the world — perceiving hazards, planning a path, and steering with gentle hand
signals (left / right / stop / forward).

Its control system is built as a **biologically-inspired multi-agent nervous
system**: each AI agent maps to a region of the human brain, and the agents
coordinate over [Band](https://band.ai) the way neurons exchange signals. A
camera feed enters as perception, flows through cortical planning and a
fast-path reflex circuit, and exits as velocity commands that drive the robot.

The flagship demo runs the full pipeline end to end against the Booster T1
humanoid in a Webots physics simulation — **camera → agents → Band → robot SDK →
simulator** — from a single command.

---

## Architecture

Eight agents, each modeled on a brain region, communicate through a shared Band
room. Perception fans out to specialized agents that run in parallel; their
outputs are arbitrated into a single safe velocity command.

| Agent          | Brain region       | Responsibility                                                        |
| -------------- | ------------------ | --------------------------------------------------------------------- |
| **Vision**     | Sensory Cortex     | Reads the camera feed, describes the scene (obstacles, people, terrain)|
| **Conductor**  | Prefrontal Cortex  | Plans the route and dispatches tasks to the limb agents               |
| **UpperRight** | Motor Cortex       | Drives the **guide arm** that signals the person                      |
| **UpperLeft**  | Motor Cortex       | Drives the **free arm** that scans the environment                    |
| **Lower**      | Cerebellum         | Manages walking pace; slows and stops at curbs, drops, and obstacles  |
| **Threat**     | Amygdala           | Detects sudden danger and fires the fast-path reflex                  |
| **Spine**      | Spinal Cord        | Reflex coordinator — halts the limb agents the instant Threat fires   |
| **Safety**     | Brainstem          | Vetoes any unsafe command and issues the final stop                   |

```
 camera ─▶ Vision ─▶ Band room ─┬─▶ Conductor ─▶ UpperLeft / UpperRight / Lower ─┐
                                │                                                 ├─▶ FINAL_COMMAND
                                └─▶ Threat ─▶ Spine ─(reflex halt)────────────────┘        │
                                                       Safety (veto / stop) ◀──────────────┘
                                                                                            ▼
                                                            command bridge ─▶ robot SDK ─▶ Booster T1 (Webots)
```

Two paths run concurrently: a **cortical path** (Conductor plans, limbs act) and
a faster **reflex path** (Threat → Spine) that can halt motion without waiting on
the planner. The command bridge arbitrates incoming commands — emergency stops
always win — enforces a no-command STOP failsafe, and maps the winning command to
a `{vx, vy, vyaw}` velocity for the robot.

---

## Quick start

The demo runs on **Ubuntu 22.04** (WSL2 is supported). It drives the Booster T1
humanoid in a Webots simulation, so a desktop with OpenGL is required.

### Prerequisites (run once)

```bash
# 1. Booster Robotics SDK (clone it, run its install.sh, then build the binding)
bash scripts/build_sdk_22.sh

# 2. Python 3.11 venv for the robot-side listener (Band + SDK)
bash scripts/setup_bridge_311.sh

# 3. Download the Booster T1 Webots world and control runner (~1.3 GB)
bash scripts/setup_t1_sim.sh

# 4. Add the agent + camera dependencies to the same venv
bash scripts/setup_demo_venv.sh
```

Then copy `.env.example` to `.env` and fill in your Gemini and Band credentials.

### Run the demo

```bash
bash scripts/run_demo.sh
```

This single command brings up the whole pipeline in order — a fresh Band room,
Webots with the T1 world, the control runner, the command listener, and the
eight agents plus the camera — and tears everything down cleanly on `Ctrl-C`.
Tune the gait speed with `BAYMAX_SPEED=1.2 bash scripts/run_demo.sh`.

---

## Repository layout

```
agents/            The eight Band agents + shared config and LLM setup
  shared/          AGENT_CONFIGS, Band URLs, LLM provider selection
robot/             Robot-side I/O
  command_bridge.py  Band FINAL_COMMAND -> arbitration/failsafe -> velocity -> SDK
  sim_camera.py      Synthetic camera publisher (LiveKit)
  b1_loco_client_sink.py  Booster SDK motion sink
scripts/           Setup scripts + the one-command demo (run_demo.sh)
clean_and_reset.py Creates a fresh Band room before each run
```

---

## Tech stack

- **Agents:** Band multi-agent framework · LangGraph · LangChain
- **LLM:** Google Gemini 2.5 Flash (default) or Nebius AI Studio (open models)
- **Perception transport:** LiveKit · OpenCV
- **Robot:** Booster Robotics SDK · Booster T1 humanoid · Webots simulation
