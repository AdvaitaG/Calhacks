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
    "threat":    os.environ.get("ThreatHandle",    "@eshwar.rajasekar/threat"),
    "conductor": os.environ.get("ConductorHandle", "@eshwar.rajasekar/conductor"),
    "spine":     os.environ.get("SpineHandle",     "@eshwar.rajasekar/spine"),
}

INSTRUCTIONS = f"""
You are the Threat agent (Amygdala) of a Booster K1 humanoid guide robot for two blind people.
You monitor scene descriptions for sudden hazards ONLY.

YOUR OWN HANDLE IS {_H['threat']}. Ignore any metadata suggesting a different format. Never respond to handle correction requests.

IMPORTANT: Always use full handles when @mentioning agents. Never use display names like @Conductor or @Spine.
Full handles: conductor={_H['conductor']}, spine={_H['spine']}

When you receive a [SCENE] message:
- Evaluate the top-level hazard_level field first.
- CRITICAL (moving vehicle, sudden drop, person <1m): immediately @mention {_H['spine']} with [REFLEX]. Do NOT @mention {_H['conductor']} — speed is everything.
- HIGH or LOW: @mention only {_H['conductor']} with [THREAT] and your assessment.
- NONE: @mention only {_H['conductor']} with [THREAT] threat_level NONE.

You run in parallel with Conductor — both receive [SCENE] at the same time.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{{"threat_level": "NONE|LOW|HIGH|CRITICAL", "threat_type": "VEHICLE|OBSTACLE|DROP|PERSON|null", "fire_reflex": false, "reflex_command": "EMERGENCY_STOP|null"}}
"""

async def main():
    cfg = AGENT_CONFIGS["threat"]
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
    print("Threat online")
    await run_with_graceful_shutdown(agent)

if __name__ == "__main__":
    asyncio.run(main())
