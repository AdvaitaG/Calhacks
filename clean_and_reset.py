"""Clean slate for the Band workspace: create ONE fresh room with all agents,
then evict every agent from all other rooms so stale backlogs (e.g. the full
1000-message room) stop flooding the agents on startup.

    python clean_and_reset.py

Run this, then restart the agents — they'll each be in exactly one room.
"""
import asyncio
import os
import sys

sys.path.insert(0, "robot")
from _common import load_env  # noqa: E402

load_env()
sys.path.insert(0, ".")
from band.platform.link import BandLink  # noqa: E402
from band.client.rest import (  # noqa: E402
    DEFAULT_REQUEST_OPTIONS, ChatRoomRequest, ParticipantRequest,
)

WS = "wss://app.band.ai/api/v1/socket/websocket"
REST = "https://app.band.ai"

# name, id env var, api-key env var, handle suffix
AGENTS = [
    ("conductor",  "ConductorID",  "ConductorBandAPI",  "conductor"),
    ("upper_left", "UpperleftID",  "UpperleftBandAPI",  "upperleft"),
    ("upper_right","UpperRightID", "UpperRightBandAPI", "upperright"),
    ("lower",      "LowerID",      "LowerBandAPI",      "lower"),
    ("threat",     "ThreatID",     "ThreatBandAPI",     "threat"),
    ("spine",      "SpineID",      "SpineBandAPI",      "spine"),
    ("safety",     "SafetyID",     "SafetyBandAPI",     "safety"),
    ("vision",     "VisionID",     "VisionBandAPI",     "vision"),
    ("robot",      "RobotID",      "RobotBandAPI",      "robot"),
]


async def main() -> None:
    # 1. Conductor creates a fresh room and invites everyone else.
    clink = BandLink(agent_id=os.environ["ConductorID"],
                     api_key=os.environ["ConductorBandAPI"], ws_url=WS, rest_url=REST)
    await clink.connect()
    resp = await clink.rest.agent_api_chats.create_agent_chat(
        chat=ChatRoomRequest(), request_options=DEFAULT_REQUEST_OPTIONS)
    target = resp.data.id
    print(f"fresh target room: {target}")
    for name, idv, _key, _h in AGENTS:
        if name == "conductor":
            continue
        try:
            await clink.rest.agent_api_participants.add_agent_chat_participant(
                chat_id=target,
                participant=ParticipantRequest(participant_id=os.environ[idv]),
                request_options=DEFAULT_REQUEST_OPTIONS)
            print(f"  added {name}")
        except Exception as e:  # noqa: BLE001
            print(f"  add {name} failed: {str(e).splitlines()[0][:60]}")
    await clink.disconnect()

    # 2. Each agent leaves every OTHER room.
    for name, idv, keyv, hsuffix in AGENTS:
        aid = os.environ.get(idv)
        link = BandLink(agent_id=aid, api_key=os.environ.get(keyv), ws_url=WS, rest_url=REST)
        try:
            await link.connect()
            rooms = (await link.rest.agent_api_chats.list_agent_chats(
                request_options=DEFAULT_REQUEST_OPTIONS)).data or []
            for room in rooms:
                if room.id == target:
                    continue
                pr = (await link.rest.agent_api_participants.list_agent_chat_participants(
                    chat_id=room.id, request_options=DEFAULT_REQUEST_OPTIONS)).data or []
                mypid = None
                for p in pr:
                    pd = p.model_dump(exclude_none=True)
                    if pd.get("agent_id") == aid or str(pd.get("handle", "")).endswith(hsuffix):
                        mypid = pd.get("id")
                        break
                if not mypid:
                    continue
                try:
                    await link.rest.agent_api_participants.remove_agent_chat_participant(
                        chat_id=room.id, id=mypid, request_options=DEFAULT_REQUEST_OPTIONS)
                    print(f"  {name} left {room.id[:8]}")
                except Exception as e:  # noqa: BLE001
                    print(f"  {name} leave {room.id[:8]} failed: {str(e).splitlines()[0][:40]}")
            await link.disconnect()
        except Exception as e:  # noqa: BLE001
            print(f"{name} connect error: {str(e).splitlines()[0][:50]}")

    # Pin the room so every process agrees on it (list order is non-deterministic).
    _write_env_var("BAYMAX_ROOM", target)
    print(f"\nDONE. All agents in room {target}")
    print(f"Wrote BAYMAX_ROOM={target} to .env — bridge + demo will use it.")


def _write_env_var(key: str, value: str) -> None:
    """Add or replace KEY=value in the repo .env."""
    path = ".env"
    lines = []
    try:
        with open(path) as f:
            lines = [ln for ln in f.read().splitlines() if not ln.startswith(key + "=")]
    except FileNotFoundError:
        pass
    lines.append(f"{key}={value}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
