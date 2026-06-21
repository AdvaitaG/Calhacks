"""
Vision Agent — Sensory Cortex
Consumes LiveKit camera frames, describes the scene via Gemini 2.5 Flash,
publishes structured [SCENE] JSON to Band room (Conductor + Threat).
"""

import asyncio
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from band.platform.link import BandLink
from band.platform.event import RoomAddedEvent, MessageEvent
from band.runtime.tools import AgentTools
from band.client.rest import DEFAULT_REQUEST_OPTIONS
from agents.shared.config import WS_URL, REST_URL

# --- Config --------------------------------------------------------------- #

GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
VISION_AGENT_ID  = os.environ["VisionID"]
VISION_API_KEY   = os.environ["VisionBandAPI"]
VISION_HANDLE    = os.environ.get("VisionHandle", "@eshwar.rajasekar/vision")

LIVEKIT_URL        = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_TOKEN      = os.environ.get("LIVEKIT_TOKEN", "")
LIVEKIT_API_KEY    = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")
LIVEKIT_ROOM       = os.environ.get("LIVEKIT_ROOM", "baymax-robot")

FRAME_INTERVAL_SECONDS = 1.0

CONDUCTOR_HANDLE = "@eshwar.rajasekar/conductor"
THREAT_HANDLE    = "@eshwar.rajasekar/threat"

# --- Gemini vision -------------------------------------------------------- #

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,
    google_api_key=GEMINI_API_KEY,
)

SYSTEM_PROMPT = """\
You are the sensory cortex of Baymax, a humanoid guide robot for visually impaired people.
Your single job: describe exactly what you see in the camera frame so the navigation agents can make decisions.

Output ONLY a valid JSON object with these fields:
{
  "obstacles": ["list of obstacles within 3 meters — people, cars, poles, furniture, steps, etc."],
  "terrain": "flat / curb / stairs / ramp / crosswalk / uneven",
  "crosswalk": true or false,
  "immediate_threat": true or false,
  "hazard_level": "NONE / LOW / HIGH / CRITICAL",
  "threat_description": "describe the threat if immediate_threat is true, else null",
  "scene_summary": "one sentence, plain English, what the person guided by the robot is about to encounter"
}

Rules:
- Be concise. One word or short phrase per obstacle.
- hazard_level: CRITICAL = moving vehicle/sudden drop/person <1m. HIGH = obstacle blocking path. LOW = minor hazard. NONE = clear.
- Do not speculate beyond what is visible.
- Do not give navigation advice — that is the Conductor's job.
- Output ONLY the JSON object, no other text.
"""


def describe_frame(jpeg_bytes: bytes) -> dict:
    b64 = base64.standard_b64encode(jpeg_bytes).decode()
    msg = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        },
        {"type": "text", "text": SYSTEM_PROMPT},
    ])
    response = _llm.invoke([msg])
    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


# --- LiveKit camera source ------------------------------------------------ #

def _resolve_livekit_token() -> str:
    if LIVEKIT_TOKEN:
        return LIVEKIT_TOKEN
    if LIVEKIT_API_KEY and LIVEKIT_API_SECRET:
        from datetime import timedelta
        from livekit import api
        return (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity("vision")
            .with_name("vision")
            .with_grants(
                api.VideoGrants(room_join=True, room=LIVEKIT_ROOM, can_subscribe=True)
            )
            .with_ttl(timedelta(hours=6))
            .to_jwt()
        )
    return ""


def _frame_to_jpeg(frame) -> bytes | None:
    try:
        from PIL import Image
        import io
        img = Image.frombytes(
            "RGBA", (frame.width, frame.height), bytes(frame.data)
        ).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"[Vision] Frame error: {e}")
        return None


# --- Webcam fallback ------------------------------------------------------ #

def _webcam_jpeg() -> bytes | None:
    try:
        import cv2, io
        from PIL import Image
        cap = cv2.VideoCapture(int(os.environ.get("WEBCAM_INDEX", "0")))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return None
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"[Vision] Webcam error: {e}")
        return None


# --- Vision loop ---------------------------------------------------------- #

async def _vision_loop(tools: AgentTools) -> None:
    """Continuously grab frames, describe them, publish [SCENE] to Band."""
    use_livekit = bool(LIVEKIT_URL and _resolve_livekit_token())

    if use_livekit:
        await _livekit_loop(tools)
    else:
        print("[Vision] No LiveKit config — falling back to webcam")
        await _webcam_loop(tools)


async def _publish_scene(tools: AgentTools, jpeg_bytes: bytes) -> None:
    loop = asyncio.get_event_loop()
    try:
        t0 = time.monotonic()
        scene = await loop.run_in_executor(None, describe_frame, jpeg_bytes)
        scene["latency_ms"] = round((time.monotonic() - t0) * 1000)
        scene["agent"] = VISION_HANDLE

        content = f"[SCENE] {json.dumps(scene)}"
        print(f"[Vision] {scene.get('scene_summary', '?')} | "
              f"hazard={scene.get('hazard_level')} | "
              f"{scene['latency_ms']}ms")

        # Publish to Conductor and Threat simultaneously (they process in parallel)
        await tools.send_message(
            content,
            mentions=[CONDUCTOR_HANDLE, THREAT_HANDLE],
        )
        print("[Vision] Scene posted to Band")
    except Exception as e:
        import traceback
        print(f"[Vision] Publish error: {e}")
        traceback.print_exc()


async def _webcam_loop(tools: AgentTools) -> None:
    while True:
        jpeg = await asyncio.get_event_loop().run_in_executor(None, _webcam_jpeg)
        if jpeg:
            await _publish_scene(tools, jpeg)
        await asyncio.sleep(FRAME_INTERVAL_SECONDS)


async def _livekit_loop(tools: AgentTools) -> None:
    from livekit import rtc

    token = _resolve_livekit_token()
    room = rtc.Room()
    last_sent = 0.0

    async def consume_video(track: rtc.VideoTrack) -> None:
        nonlocal last_sent
        video_stream = rtc.VideoStream(track)
        async for frame_event in video_stream:
            now = time.monotonic()
            if now - last_sent < FRAME_INTERVAL_SECONDS:
                continue
            last_sent = now
            jpeg = _frame_to_jpeg(frame_event.frame)
            if jpeg:
                await _publish_scene(tools, jpeg)

    @room.on("track_subscribed")
    def on_track(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            asyncio.ensure_future(consume_video(track))

    await room.connect(LIVEKIT_URL, token)
    print(f"[Vision] Connected to LiveKit room: {room.name}")

    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        await room.disconnect()


# --- Band connection ------------------------------------------------------ #

async def main() -> None:
    link = BandLink(
        agent_id=VISION_AGENT_ID,
        api_key=VISION_API_KEY,
        ws_url=WS_URL,
        rest_url=REST_URL,
    )

    await link.connect()
    await link.subscribe_agent_rooms(VISION_AGENT_ID)
    print(f"[Vision] Online as {VISION_HANDLE} — waiting for room...")

    tools: AgentTools | None = None
    vision_task: asyncio.Task | None = None

    async for event in link:
        if isinstance(event, RoomAddedEvent):
            room_id = event.room_id
            print(f"[Vision] Joined room {room_id} — fetching participants...")
            try:
                resp = await link.rest.agent_api_participants.list_agent_participants(
                    chat_id=room_id,
                    request_options=DEFAULT_REQUEST_OPTIONS,
                )
                participants = [p.model_dump(exclude_none=True) for p in (resp.data or [])]
                print(f"[Vision] {len(participants)} participants in room")
            except Exception as e:
                print(f"[Vision] Could not fetch participants: {e} — sending without mentions")
                participants = None

            tools = AgentTools(room_id=room_id, rest=link.rest, participants=participants)
            if vision_task is None:
                vision_task = asyncio.create_task(_vision_loop(tools))

        # Vision agent doesn't respond to messages — it only publishes.


if __name__ == "__main__":
    asyncio.run(main())
