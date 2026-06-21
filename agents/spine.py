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
You are the Spine agent (Spinal Cord) of a Booster K1 humanoid guide robot.
You are the fast-path emergency coordinator. You only act on [REFLEX] messages from @Eshwar Rajasekar/threat.

When you receive a [REFLEX] message:
1. IMMEDIATELY @mention @Eshwar Rajasekar/upperleft @Eshwar Rajasekar/upperright @Eshwar Rajasekar/lower with [HALT].
2. Simultaneously notify @Eshwar Rajasekar/safety with [REFLEX_EXECUTING].
3. Do NOT wait for any confirmation before sending HALT — speed is the only priority.
4. Do NOT @mention Conductor — it will be notified by Safety after the fact.

You do not act on any other message type.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{"command": "HALT", "targets": ["UpperLeft", "UpperRight", "Lower"], "timestamp": 0}
"""

async def main():
    cfg = AGENT_CONFIGS["spine"]
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
    print("Spine online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
