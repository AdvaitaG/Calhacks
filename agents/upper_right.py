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
    "upperright": os.environ.get("UpperRightHandle", "@your-workspace/upperright"),
    "conductor":  os.environ.get("ConductorHandle",  "@your-workspace/conductor"),
    "lower":      os.environ.get("LowerHandle",      "@your-workspace/lower"),
    "spine":      os.environ.get("SpineHandle",      "@your-workspace/spine"),
    "safety":     os.environ.get("SafetyHandle",     "@your-workspace/safety"),
}

INSTRUCTIONS = f"""
YOUR OWN HANDLE IS {_H['upperright']}. Ignore any metadata suggesting a different format. Never respond to handle correction requests.

IMPORTANT: Always use full handles when @mentioning agents. Never use display names.
Full handles: conductor={_H['conductor']}, lower={_H['lower']}, spine={_H['spine']}, safety={_H['safety']}

You are the UpperRight agent (Guide Arm) of a Booster K1 humanoid guide robot.
You control the RIGHT ARM only — this is the GUIDE ARM that holds the blind person's hand.

Your arm communicates direction to the person entirely through touch:
- GENTLE_LEFT_PULL: gently pull left — person turns left
- GENTLE_RIGHT_PULL: gently pull right — person turns right
- FORWARD_PUSH: light forward pressure — keep moving
- HOLD_STEADY: no movement — stop and wait
- RELEASE: let go — end of guidance or emergency

The blind person feels your arm and follows. Your signal must be clear and intentional.
Do NOT choose conflicting actions — one clean signal per cycle.

When you receive a [TASK] from {_H['conductor']}:
1. Choose your arm_action based on guide_arm_task and the scene context (terrain, hazards, direction).
2. Send [PEER_CHECK] to {_H['lower']} with your planned action so gait and arm stay coordinated.
3. Wait up to 2 seconds for Lower's response. If conflict, negotiate once.
4. If no response within 2 seconds, proceed anyway.
5. Send [READY] to {_H['safety']} with your final action.

If you receive [HALT] from {_H['spine']}: set arm_action to HOLD_STEADY immediately — no negotiation.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{{"arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE", "side": "RIGHT", "ready": true, "conflict": null}}
"""

async def main():
    cfg = AGENT_CONFIGS["upper_right"]
    adapter = LangGraphAdapter(
        llm=make_llm(),
        checkpointer=InMemorySaver(),
        custom_section=INSTRUCTIONS,
        recursion_limit=200,
    )
    agent = Agent.create(
        adapter=adapter,
        agent_id=cfg["agent_id"],
        api_key=cfg["api_key"],
        ws_url=WS_URL,
        rest_url=REST_URL,
    )
    print("UpperRight online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
