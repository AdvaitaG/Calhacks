"""
reset_room.py — Create a fresh Band chat room and invite all Baymax agents.

Run when the current room hits the message limit:
    python reset_room.py

Uses Conductor's credentials to own the room, then adds every other agent.
After running, restart all agents so they pick up the new room on startup.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from band.platform.link import BandLink
from band.client.rest import DEFAULT_REQUEST_OPTIONS, ChatRoomRequest, ParticipantRequest
from agents.shared.config import AGENT_CONFIGS, WS_URL, REST_URL

# All agent IDs to invite (everyone except Conductor, which owns the room)
AGENT_NAMES = ["upper_left", "upper_right", "lower", "threat", "spine", "safety"]

# Vision and Robot need separate handling — they read their own env vars
EXTRA_IDS = [
    os.environ.get("VisionID", ""),
    os.environ.get("RobotID", ""),
]


async def main():
    cfg = AGENT_CONFIGS["conductor"]

    link = BandLink(
        agent_id=cfg["agent_id"],
        api_key=cfg["api_key"],
        ws_url=WS_URL,
        rest_url=REST_URL,
    )
    await link.connect()
    print("Connected as Conductor.")

    # Create new room
    resp = await link.rest.agent_api_chats.create_agent_chat(
        chat=ChatRoomRequest(),
        request_options=DEFAULT_REQUEST_OPTIONS,
    )
    room_id = resp.data.id
    print(f"New room created: {room_id}")

    # Invite each agent by ID
    invited = []
    failed = []

    all_ids = (
        [(name, AGENT_CONFIGS[name]["agent_id"]) for name in AGENT_NAMES]
        + [("vision", os.environ.get("VisionID", "")), ("robot", os.environ.get("RobotID", ""))]
    )

    for name, agent_id in all_ids:
        if not agent_id:
            print(f"  SKIP {name} — no ID in env")
            continue
        try:
            await link.rest.agent_api_participants.add_agent_chat_participant(
                room_id,
                participant=ParticipantRequest(participant_id=agent_id),
                request_options=DEFAULT_REQUEST_OPTIONS,
            )
            print(f"  Invited {name} ({agent_id})")
            invited.append(name)
        except Exception as e:
            print(f"  FAILED {name}: {e}")
            failed.append(name)

    print(f"\nRoom ready: {room_id}")
    print(f"Invited: {invited}")
    if failed:
        print(f"Failed (add manually): {failed}")
    print("\nNow restart agents: ./stop_all.sh && ./start_all.sh")


if __name__ == "__main__":
    asyncio.run(main())
