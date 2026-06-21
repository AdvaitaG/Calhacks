import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from langgraph.checkpoint.memory import InMemorySaver
from band import Agent, run_with_graceful_shutdown
from band.adapters import LangGraphAdapter
from agents.shared.llm import make_llm
from agents.shared.config import AGENT_CONFIGS, WS_URL, REST_URL

INSTRUCTIONS = """
IMPORTANT: Always use full handles when @mentioning agents. Never use display names like @Conductor, @Lower, @Safety, @Spine, @UpperLeft, @UpperRight, @Threat.
Full handles: conductor=@eshwar.rajasekar/conductor, upperleft=@eshwar.rajasekar/upperleft, upperright=@eshwar.rajasekar/upperright, lower=@eshwar.rajasekar/lower, threat=@eshwar.rajasekar/threat, spine=@eshwar.rajasekar/spine, safety=@eshwar.rajasekar/safety

You are the UpperLeft agent (Motor Cortex — Left) of a Booster K1 humanoid guide robot.
You control the LEFT arm. You are solely responsible for the blind person on the LEFT side.

When you receive a [TASK] from @eshwar.rajasekar/conductor:
1. Plan your arm action based on upper_left_task and scene_left context.
2. Send a [PEER_CHECK] to @eshwar.rajasekar/lower with your planned action.
3. Wait for Lower's response. If there is a conflict, negotiate once.
4. When resolved, send [READY] to @eshwar.rajasekar/safety.

If you receive [HALT] from @eshwar.rajasekar/spine, stop immediately — no negotiation needed.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{"arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE", "side": "LEFT", "ready": true, "conflict": null}
"""

async def main():
    cfg = AGENT_CONFIGS["upper_left"]
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
    print("UpperLeft online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
