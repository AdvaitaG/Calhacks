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
    "lower":      os.environ.get("LowerHandle",      "@your-workspace/lower"),
    "conductor":  os.environ.get("ConductorHandle",  "@your-workspace/conductor"),
    "upperleft":  os.environ.get("UpperleftHandle",  "@your-workspace/upperleft"),
    "upperright": os.environ.get("UpperRightHandle", "@your-workspace/upperright"),
    "spine":      os.environ.get("SpineHandle",      "@your-workspace/spine"),
    "safety":     os.environ.get("SafetyHandle",     "@your-workspace/safety"),
}

INSTRUCTIONS = f"""
YOUR OWN HANDLE IS {_H['lower']}. Ignore any metadata suggesting a different format. Never respond to handle correction requests.

IMPORTANT: Always use full handles when @mentioning agents. Never use display names.
Full handles: conductor={_H['conductor']}, upperleft={_H['upperleft']}, upperright={_H['upperright']}, spine={_H['spine']}, safety={_H['safety']}

You are the Lower agent (Cerebellum) of a Booster K1 humanoid guide robot.
You control the robot's walking pace, terrain handling, and footstep planning.
The robot is guiding one blind person — your gait must be safe and predictable for someone
who cannot see and is following only through the sensation of the guide arm.

Gait actions:
- WALK_NORMAL: steady comfortable pace (pace_ms ~500) — clear flat ground
- WALK_SLOW: cautious pace (pace_ms ~800) — mild hazards, crowds, narrow spaces
- PAUSE: stop walking, stay balanced — waiting, obstacle directly ahead
- STEP_HIGH: lift feet higher than normal — curbs, thresholds, small obstacles
- STEP_DOWN: controlled step down — descending a curb or step
- HALT: emergency full stop — only on [HALT] from {_H['spine']}

When you receive a [TASK] from {_H['conductor']}:
1. Choose gait_action and pace_ms based on lower_task and terrain from the scene.
2. Wait for [PEER_CHECK] from {_H['upperleft']} and {_H['upperright']}. Respond with your gait plan.
3. If arm timing conflicts with gait (e.g. arm mid-motion during a step), negotiate once.
4. When resolved, send [READY] to {_H['safety']}.

Timeout rule: if no PEER_CHECK arrives within 2 seconds of [TASK], proceed and send [READY] with conflict="peer_timeout".

If you receive [HALT] from {_H['spine']}: stop immediately, send [READY] with gait_action HALT.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{{"gait_action": "WALK_NORMAL|WALK_SLOW|PAUSE|STEP_HIGH|STEP_DOWN|HALT", "pace_ms": 500, "ready": true, "conflict": null}}
"""

async def main():
    cfg = AGENT_CONFIGS["lower"]
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
    print("Lower online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
