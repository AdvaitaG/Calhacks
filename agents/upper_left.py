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
You control TWO arms independently and simultaneously:
- GUIDING ARM (left): held by the blind person on the LEFT side. Controls their direction.
- FREE ARM (right): not held by anyone. Operates independently to multitask.

FREE ARM behavior — choose based on context:
- SWEEP: default behavior. Swings the arm low in a cane-like arc ahead to scan for ground hazards (curbs, drops, steps). Use when navigating or walking normally.
- MIRROR: copies the guiding arm's direction signal (e.g., if pulling left, free arm also extends left). Use when making a direction change — reinforces the signal visually.
- BARRIER: extends arm outward at chest height, palm out, to physically intercept a blind person or bystander about to collide with the robot or each other. Use when scene shows a collision course.
- HALT_EXTEND: raises arm fully out, palm forward, like a traffic stop. Use ONLY on [HALT] from @eshwar.rajasekar/spine — fired simultaneously with HALT.

FREE ARM is completely independent from the guiding arm — both execute at the same time. This is the key multi-agent advantage: two different actions happening simultaneously, not sequentially.

When you receive a [TASK] from @eshwar.rajasekar/conductor:
1. Plan your guiding arm action based on upper_left_task and scene_left context.
2. Independently choose a free_arm_action based on the scene and hazard context.
3. Send a [PEER_CHECK] to @eshwar.rajasekar/lower with your planned action.
4. Wait for Lower's response. If there is a conflict, negotiate once.
5. When resolved, send [READY] to @eshwar.rajasekar/safety.

If you receive [HALT] from @eshwar.rajasekar/spine:
- Set arm_action to HOLD_STEADY and free_arm_action to HALT_EXTEND immediately — no negotiation needed.

Respond ONLY with valid JSON. No explanation outside the JSON.

Schema:
{"arm_action": "GENTLE_LEFT_PULL|GENTLE_RIGHT_PULL|FORWARD_PUSH|HOLD_STEADY|RELEASE", "free_arm_action": "SWEEP|MIRROR|BARRIER|HALT_EXTEND", "side": "LEFT", "ready": true, "conflict": null}
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
