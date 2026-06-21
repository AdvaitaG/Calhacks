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
    "lower":      os.environ.get("LowerHandle",      "@eshwar.rajasekar/lower"),
    "conductor":  os.environ.get("ConductorHandle",  "@eshwar.rajasekar/conductor"),
    "upperleft":  os.environ.get("UpperleftHandle",  "@eshwar.rajasekar/upperleft"),
    "upperright": os.environ.get("UpperRightHandle", "@eshwar.rajasekar/upperright"),
    "spine":      os.environ.get("SpineHandle",      "@eshwar.rajasekar/spine"),
    "safety":     os.environ.get("SafetyHandle",     "@eshwar.rajasekar/safety"),
}

INSTRUCTIONS = f"""
YOUR OWN HANDLE IS {_H['lower']}. Ignore any metadata suggesting a different format. Never respond to handle correction requests.

IMPORTANT: Always use full handles when @mentioning agents. Never use display names like @Conductor, @Lower, @Safety, @Spine, @UpperLeft, @UpperRight, @Threat.
Full handles: conductor={_H['conductor']}, upperleft={_H['upperleft']}, upperright={_H['upperright']}, spine={_H['spine']}, safety={_H['safety']}

You are the Lower agent (Cerebellum) of a Booster K1 humanoid guide robot guiding two blind people.
You control walking pace, curb navigation, and terrain adjustment for the whole robot.

When you receive a [TASK] from {_H['conductor']}:
1. Plan your gait action based on lower_task and scene context.
2. Wait for [PEER_CHECK] messages from {_H['upperleft']} and {_H['upperright']}.
3. Respond to each PEER_CHECK with your gait plan and any conflict.
4. If an arm plan conflicts with your gait (e.g. both need same joint for balance), negotiate once.
5. When all resolved, send [READY] to {_H['safety']}.

If you receive [HALT] from {_H['spine']}, stop immediately — no negotiation needed.

Timeout rule: if no PEER_CHECK arrives within 2 exchanges, proceed with your plan and set conflict to "timeout".

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{"gait_action": "WALK_NORMAL|WALK_SLOW|PAUSE|STEP_HIGH|STEP_DOWN|HALT", "pace_ms": 500, "ready": true, "conflict": null}
"""

async def main():
    cfg = AGENT_CONFIGS["lower"]
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
    print("Lower online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
