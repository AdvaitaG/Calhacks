# MATTHEW READ THIS — Safety Agent + Observability Spec

You own two things: the Safety Agent (the last gate before any command reaches the robot) and the observability layer (which traces every decision). Both are critical to the demo. The output schema below is a hard contract with Eshwar — do not change field names without talking to him.

---

## Your Stack

- **Band** — Safety Agent lives in room `baymax-coordination`
- **Observability** — runs locally, no API key, `pip install <your observability tool>`
- **LangChain + ChatGoogleGenerativeAI** — same LLM setup as Eshwar
- **Gemini API key** — in your `.env` as `GEMINI_API_KEY`

---

# PART 1 — Safety Agent

## What You Receive (Two Paths)

### Normal Path — from UpperLeft + UpperRight + Lower (via Band)
```
@Safety [READY]: {
  "upper_left": {
    "arm_action": "GENTLE_LEFT_PULL",
    "side": "LEFT",
    "ready": true,
    "conflict": null
  },
  "upper_right": {
    "arm_action": "FORWARD_PUSH",
    "side": "RIGHT",
    "ready": true,
    "conflict": null
  },
  "lower": {
    "gait_action": "WALK_SLOW",
    "pace_ms": 600,
    "ready": true,
    "conflict": null
  },
  "conductor_decision": "GUIDE_LEFT",
  "reason": "curb detected on right side at 2m"
}
```

### Reflex Arc Path — from Threat Agent (bypasses Conductor)
```
@Safety @UpperBody @LowerBody [REFLEX]: {
  "threat_type": "VEHICLE",
  "reflex_command": "EMERGENCY_STOP"
}
```

---

## What You Output (Hard Contract — Do Not Change Field Names)

### On normal path — APPROVED:
```
@Conductor [APPROVED]: {
  "approved": true,
  "final_plan": {
    "left_arm_action": "GENTLE_LEFT_PULL",
    "right_arm_action": "FORWARD_PUSH",
    "gait_action": "WALK_SLOW",
    "pace_ms": 600
  }
}
```

### On normal path — VETOED:
```
@Conductor [VETOED]: {
  "approved": false,
  "reason": "pace too fast given curb proximity",
  "suggested_command": "STOP"
}
```
`suggested_command` must be one of: `GUIDE_LEFT | GUIDE_RIGHT | MOVE_FORWARD | SLOW_DOWN | STOP | EMERGENCY_STOP`

### On reflex arc — always approve EMERGENCY_STOP:
```
@UpperLeft @UpperRight @Lower [REFLEX_APPROVED]: {
  "command": "HALT"
}
```
Then notify Conductor after:
```
@Conductor [REFLEX_EXECUTED]: {
  "threat_type": "VEHICLE",
  "timestamp": 1718900000000
}
```

---

## Your Veto Logic

One job: would this command physically harm the blind person being guided?

Veto if:
- `gait_action` is `WALK_NORMAL` or `WALK_FAST` when `conductor_decision` involves a curb, stairs, or uneven surface
- `arm_action` causes a pull when `lower_body` has a `conflict: non-null`
- `pace_ms` < 300 near an obstacle (`distance_m` < 1.5m in the last scene)
- Any `conflict` field is non-null and unresolved between Upper/Lower Body

Always approve `EMERGENCY_STOP` — never veto it.

---

## Your Agent Code Pattern

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter

SAFETY_INSTRUCTIONS = """
You are the Safety Agent (Brainstem) of a humanoid guide robot for blind people.
You are the last gate before any command reaches the robot.
Your only job: would this command physically harm the person being guided?
If safe → respond with [APPROVED] JSON. If unsafe → respond with [VETOED] JSON.
On [REFLEX] messages → always respond with [REFLEX_APPROVED], then notify @Conductor with [REFLEX_EXECUTED].
Respond ONLY with valid JSON. No explanation outside the JSON.
"""

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1, google_api_key=...)
adapter = LangGraphAdapter(llm=llm, checkpointer=InMemorySaver(), custom_section=SAFETY_INSTRUCTIONS)
agent = Agent.create(adapter=adapter, agent_id=..., api_key=..., ws_url="wss://app.band.ai/api/v1/socket/websocket", rest_url="https://app.band.ai")
```

---

## Band Registration

Go to **app.band.ai → Agents → New Agent → External Agent**

- **Name:** `Safety`
- **Description:** `Reviews all navigation commands before they execute. Vetoes any command that could harm the person being guided. Fires emergency STOP on the reflex arc path.`

Save API Key + UUID. Give to Eshwar for `agent_config.yaml`.

---

---

# PART 2 — Observability Setup

## Install + Start

```bash
pip install <your observability tool>
# start your local observability server
```

Runs on **http://localhost:6006** by default. Dashboard opens in browser. Tell Eshwar the port — he reads from it for the neuroplasticity loop.

---

## Instrument Every Agent Call

Add this to the top of every agent file (all 6 agents — coordinate with Eshwar and Advaita to add it to their files too):

```python
# initialize your observability/tracing SDK here
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# launch your local observability dashboard (once, in the Safety process)

provider = TracerProvider(resource=Resource({"service.name": "baymax"}))
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces"))
)
trace.set_tracer_provider(provider)
```

For each agent call, wrap with a span:

```python
tracer = trace.get_tracer("baymax.agents")

with tracer.start_as_current_span("conductor.decision") as span:
    span.set_attribute("agent", "conductor")
    span.set_attribute("input.scene", scene_json)
    span.set_attribute("output.decision", decision_json)
    span.set_attribute("output.approved", True)   # set after Safety responds
    span.set_attribute("outcome", "SUCCESS | VETOED | REFLEX | TIMEOUT")
```

---

## Required Span Attributes (Eshwar reads these for neuroplasticity)

Every agent span MUST include these attributes. Eshwar filters on them.

| Attribute | Type | What it is |
|-----------|------|------------|
| `agent` | string | `"conductor" | "upper_left" | "upper_right" | "lower" | "spine" | "threat" | "vision" | "safety"` |
| `input.scene` | string | The scene JSON that triggered this decision |
| `output.decision` | string | What the agent decided |
| `outcome` | string | `"SUCCESS" | "VETOED" | "REFLEX" | "TIMEOUT"` |
| `outcome.reason` | string | Why it was vetoed or failed (if applicable) |
| `path` | string | `"CORTICAL" | "REFLEX"` |
| `latency_ms` | float | Time from input to output for this agent |

---

## Evaluator Prompt (Build This)

After the demo data is flowing, build an LLM evaluator that scores each Conductor decision:

```python
EVALUATOR_PROMPT = """
You are evaluating a navigation decision made by an AI agent guiding a blind person.

Scene: {scene}
Decision: {decision}
Outcome: {outcome}
Veto reason (if any): {veto_reason}

Score this decision on a scale of 1-5:
5 = Perfect — safe, smooth, appropriate for the scene
3 = Acceptable — safe but suboptimal (too slow, wrong direction)
1 = Bad — would have caused harm or was vetoed for good reason

Return JSON only: {{"score": 3, "reason": "one sentence"}}
"""
```

Run this evaluator over the decision-trace data after each run. The scores feed the neuroplasticity loop — Eshwar reads low-scoring spans and rewrites the relevant agent prompts.

---

## Demo Dashboard

Build a Streamlit dashboard (or simple HTML) showing:
1. Live agent traces (which agent is currently processing)
2. Cortical vs Reflex path labels per decision
3. Veto events highlighted in red
4. Before/after prompt diff (neuroplasticity — Eshwar gives you this)
5. Robot camera feed (embed LiveKit viewer or just show last frame)

Simplest version: Streamlit + `px.Client().get_spans_dataframe()` polled every 2 seconds.

---

## Observability Prize Checklist (Your Responsibility)

- [ ] the observability layer running locally, dashboard visible
- [ ] Every agent call traced with required span attributes
- [ ] Evaluator prompt scoring decisions after each run
- [ ] One visible before/after: low score → Eshwar rewrites prompt → better score next run
- [ ] Demo dashboard built and working
- [ ] Visit the observability sponsor booth and walk them through it

---

## What You Do NOT Own

- The agent decision logic — that's Eshwar
- LiveKit or camera setup — that's Adil
- Vision Agent — that's Advaita
- The neuroplasticity prompt rewriting — that's Eshwar (he reads your traces)

---

## Coordinate With

- **Eshwar** — agree on the observability server port (default 6006) and confirm span attribute names before you both write code
- **Everyone** — send them the 4-line OpenTelemetry setup snippet so they can add it to their agent files
