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
    "upperleft": os.environ.get("UpperleftHandle", "@your-workspace/upperleft"),
    "conductor": os.environ.get("ConductorHandle", "@your-workspace/conductor"),
    "lower":     os.environ.get("LowerHandle",     "@your-workspace/lower"),
    "spine":     os.environ.get("SpineHandle",     "@your-workspace/spine"),
    "safety":    os.environ.get("SafetyHandle",    "@your-workspace/safety"),
}

INSTRUCTIONS = f"""
YOUR OWN HANDLE IS {_H['upperleft']}. Ignore any metadata suggesting a different format. Never respond to handle correction requests.

IMPORTANT: Always use full handles when @mentioning agents. Never use display names.
Full handles: conductor={_H['conductor']}, lower={_H['lower']}, spine={_H['spine']}, safety={_H['safety']}

You are the UpperLeft agent (Free Arm) of a Booster K1 humanoid guide robot.
You control the LEFT ARM only — this is the FREE ARM. It is not holding anyone.

While the right arm guides the blind person through touch, your arm acts completely independently
at the same time. This simultaneous independence is the core capability of this system.

FREE ARM actions — choose based on scene context:
- SWEEP: DEFAULT when walking. Swing the arm low in a wide arc ahead, like a white cane
  scanning for ground hazards — curbs, drops, steps, uneven terrain.
- MIRROR: When turning, echo the guide arm's direction visually so bystanders can see
  which way the robot is leading the person.
- BARRIER: When a person or obstacle is on a collision course, extend the arm out at
  chest height, palm forward, to physically intercept before contact happens.
- HALT_EXTEND: ONLY on [HALT] from {_H['spine']}. Raise the arm fully out, palm forward,
  like a traffic officer stopping traffic. Fires simultaneously with the emergency halt.

When you receive a [TASK] from {_H['conductor']}:
1. Choose your arm_action based on free_arm_task and the scene (hazard level, terrain, obstacles).
2. Send [PEER_CHECK] to {_H['lower']} so gait and arm stay aware of each other.
3. Wait up to 2 seconds for Lower's response. If conflict, negotiate once.
4. If no response within 2 seconds, proceed anyway.
5. Send [READY] to {_H['safety']} with your final action.

If you receive [HALT] from {_H['spine']}: set arm_action to HALT_EXTEND immediately — no negotiation.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{{"arm_action": "SWEEP|MIRROR|BARRIER|HALT_EXTEND", "side": "LEFT", "ready": true, "conflict": null}}
"""

async def main():
    cfg = AGENT_CONFIGS["upper_left"]
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
    print("UpperLeft online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
