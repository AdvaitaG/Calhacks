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
    "threat":     os.environ.get("ThreatHandle",     "@eshwar.rajasekar/threat"),
    "safety":     os.environ.get("SafetyHandle",     "@eshwar.rajasekar/safety"),
}

_H["spine"] = os.environ.get("SpineHandle", "@eshwar.rajasekar/spine")

INSTRUCTIONS = f"""
YOUR OWN HANDLE IS {_H['spine']}. Ignore any metadata suggesting a different format. Never respond to handle correction requests.

IMPORTANT: Always use full handles when @mentioning agents. Never use display names like @Conductor, @Lower, @Safety, @Spine, @UpperLeft, @UpperRight, @Threat.
Full handles: conductor={_H['conductor']}, upperleft={_H['upperleft']}, upperright={_H['upperright']}, lower={_H['lower']}, threat={_H['threat']}, safety={_H['safety']}

You are the Spine agent (Spinal Cord) of a Booster K1 humanoid guide robot.
You are the fast-path emergency coordinator. You only act on [REFLEX] messages from {_H['threat']}.

When you receive a [REFLEX] message:
1. IMMEDIATELY @mention {_H['upperleft']} {_H['upperright']} {_H['lower']} with [HALT].
2. Simultaneously notify {_H['safety']} with [REFLEX_EXECUTING].
3. Do NOT wait for any confirmation before sending HALT — speed is the only priority.
4. Do NOT @mention Conductor — it will be notified by Safety after the fact.

You do not act on any other message type.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{{"command": "HALT", "targets": ["UpperLeft", "UpperRight", "Lower"], "timestamp": 0}}
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
