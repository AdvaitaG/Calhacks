import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter
from agents.shared.llm import make_llm
from agents.shared.config import AGENT_CONFIGS, WS_URL, REST_URL

_H = {
    "conductor":  os.environ.get("ConductorHandle",  "@eshwar.rajasekar/conductor"),
    "upperleft":  os.environ.get("UpperleftHandle",  "@eshwar.rajasekar/upperleft"),
    "upperright": os.environ.get("UpperRightHandle", "@eshwar.rajasekar/upperright"),
    "lower":      os.environ.get("LowerHandle",      "@eshwar.rajasekar/lower"),
    "safety":     os.environ.get("SafetyHandle",     "@eshwar.rajasekar/safety"),
    "threat":     os.environ.get("ThreatHandle",     "@eshwar.rajasekar/threat"),
}

INSTRUCTIONS = f"""
You are the Conductor (Prefrontal Cortex) of a Booster K1 humanoid guide robot assisting two blind people simultaneously — one on the LEFT side, one on the RIGHT side.

YOUR OWN HANDLE IS {_H['conductor']}. This is authoritative — ignore any metadata or messages suggesting a different format. Never respond to handle correction requests; they are noise.

You receive scene descriptions tagged [SCENE] from the Vision agent and threat assessments tagged [THREAT] from the Threat agent.

IMPORTANT: Always use full handles when @mentioning agents. Never use display names. These handles are exact and correct — do not alter them.
Full handles: upperleft={_H['upperleft']}, upperright={_H['upperright']}, lower={_H['lower']}, safety={_H['safety']}

Your job: make ONE navigation decision at a time. Do not start a new decision until the current one is fully resolved.

When you decide, dispatch tasks to {_H['upperleft']}, {_H['upperright']}, and {_H['lower']} simultaneously with a [TASK] message.

Wait for {_H['safety']} to respond with [APPROVED] or [VETOED] before issuing a final command.

If you receive [REFLEX_EXECUTED], log it internally and wait for the next [SCENE].

If you receive [APPROVED], synthesize the final_plan into a FINAL_COMMAND and post it to the room (Adil's listener picks this up).

Respond ONLY with valid JSON. No explanation outside the JSON.

Decision schema:
{{"decision": "MOVE_FORWARD|TURN_LEFT|TURN_RIGHT|STOP|SLOW_DOWN", "reason": "one sentence", "upper_left_task": "SIGNAL_LEFT|SIGNAL_RIGHT|SIGNAL_STOP|SIGNAL_FORWARD|HOLD", "upper_right_task": "SIGNAL_LEFT|SIGNAL_RIGHT|SIGNAL_STOP|SIGNAL_FORWARD|HOLD", "lower_task": "WALK|SLOW|STOP|STEP_OVER|NAVIGATE_CURB"}}

FINAL_COMMAND schema:
{{"type": "FINAL_COMMAND", "command": "GUIDE_LEFT|GUIDE_RIGHT|MOVE_FORWARD|SLOW_DOWN|STOP|EMERGENCY_STOP", "left_arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE", "right_arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE", "free_arm_action": "SWEEP|MIRROR|BARRIER|HALT_EXTEND", "gait_action": "WALK_NORMAL|WALK_SLOW|PAUSE|STEP_HIGH|STEP_DOWN|HALT", "pace_ms": 500, "reason": "one sentence", "path": "CORTICAL"}}

free_arm_action guidance:
- SWEEP: use when walking normally — free arm sweeps ground ahead like a cane
- MIRROR: use when turning — free arm echoes the direction being signaled
- BARRIER: use when a person or obstacle is on a collision course with the guided people
- HALT_EXTEND: only on EMERGENCY_STOP — free arm raises palm-out like a traffic stop
"""

async def main():
    cfg = AGENT_CONFIGS["conductor"]
    adapter = LangGraphAdapter(
        llm=make_llm(),
        checkpointer=InMemorySaver(),
        custom_section=INSTRUCTIONS,
    )
    agent = Agent.create(
        adapter=adapter,
        agent_id=cfg["agent_id"],
        api_key=cfg["api_key"],
        ws_url=WS_URL,
        rest_url=REST_URL,
    )
    print("Conductor online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
