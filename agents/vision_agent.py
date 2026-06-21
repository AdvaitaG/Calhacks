"""
Vision Agent — Sensory Cortex
Consumes LiveKit camera frames, describes the scene via Claude claude-sonnet-4-6,
publishes structured scene JSON to Band room.
"""

import asyncio
import base64
import json
import os
import time

import anthropic
from livekit import rtc

# --- Config --------------------------------------------------------------- #

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
# Auth: prefer a pre-minted token if given, else mint one from the API
# key/secret scoped to LIVEKIT_ROOM. This MUST be the same room Adil's
# robot.py publishes to (default: baymax-robot) or the camera track won't
# be visible here.
LIVEKIT_TOKEN = os.environ.get("LIVEKIT_TOKEN", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")
LIVEKIT_ROOM = os.environ.get("LIVEKIT_ROOM", "baymax-robot")


def _resolve_livekit_token() -> str:
    """Use a provided token, otherwise mint one (identity 'vision') from key/secret."""
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

FRAME_INTERVAL_SECONDS = 1.0  # describe the scene once per second

SYSTEM_PROMPT = """\
You are the sensory cortex of Baymax, a humanoid guide robot for visually impaired people.
Your single job: describe exactly what you see in the camera frame so the navigation agents can make decisions.

Output ONLY a valid JSON object with these fields:
{
  "obstacles": ["list of obstacles within 3 meters — people, cars, poles, furniture, steps, etc."],
  "terrain": "flat / curb / stairs / ramp / crosswalk / uneven",
  "crosswalk": true or false,
  "immediate_threat": true or false,
  "threat_description": "describe the threat if immediate_threat is true, else null",
  "scene_summary": "one sentence, plain English, what the person guided by the robot is about to encounter"
}

Rules:
- Be concise. One word or short phrase per obstacle.
- Do not speculate beyond what is visible.
- Do not give navigation advice — that is the Conductor's job.
- Output ONLY the JSON object, no other text.
"""

# --- Anthropic client ----------------------------------------------------- #

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
VISION_MODEL = "claude-sonnet-4-6"

# --- Band stub ------------------------------------------------------------ #
# Eshwar: replace this with your Band SDK publish call.
# scene_data is the dict from Claude — post it to the "vision" channel.

async def publish_to_band(scene_data: dict) -> None:
    # TODO: Band SDK publish
    print(f"[Band] {scene_data.get('scene_summary', '?')} | "
          f"threat={scene_data.get('immediate_threat')} | "
          f"terrain={scene_data.get('terrain')} | "
          f"latency={scene_data.get('latency_ms')}ms")


# --- Core vision call ----------------------------------------------------- #

def _resize_if_needed(jpeg_bytes: bytes, max_bytes: int = 9 * 1024 * 1024) -> bytes:
    if len(jpeg_bytes) <= max_bytes:
        return jpeg_bytes
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    for quality in (75, 60, 45):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes:
            return buf.getvalue()
    # scale down to 1280 wide if still too big
    w, h = img.size
    img = img.resize((1280, int(h * 1280 / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()


def describe_frame_sync(jpeg_bytes: bytes) -> dict:
    jpeg_bytes = _resize_if_needed(jpeg_bytes)
    b64 = base64.standard_b64encode(jpeg_bytes).decode()
    response = _client.messages.create(
        model=VISION_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": "Describe this frame."},
                ],
            }
        ],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


# --- Vision Agent --------------------------------------------------------- #

class VisionAgent:
    def __init__(self, band_room: str = "baymax"):
        self.band_room = band_room

    async def run(self) -> None:
        token = _resolve_livekit_token()
        if not LIVEKIT_URL or not token:
            raise RuntimeError(
                "Set LIVEKIT_URL and either LIVEKIT_TOKEN or "
                "LIVEKIT_API_KEY + LIVEKIT_API_SECRET (room = LIVEKIT_ROOM, "
                f"currently {LIVEKIT_ROOM!r}). Coordinate the room name with Adil."
            )

        room = rtc.Room()

        @room.on("track_subscribed")
        def on_track(track: rtc.Track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_VIDEO:
                asyncio.ensure_future(self._consume_video(track))

        await room.connect(LIVEKIT_URL, token)
        print(f"[VisionAgent] Connected to LiveKit: {room.name}")

        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        finally:
            await room.disconnect()

    async def _consume_video(self, track: rtc.VideoTrack) -> None:
        video_stream = rtc.VideoStream(track)
        last_sent = 0.0
        loop = asyncio.get_event_loop()

        async for frame_event in video_stream:
            now = time.monotonic()
            if now - last_sent < FRAME_INTERVAL_SECONDS:
                continue
            last_sent = now

            jpeg_bytes = _frame_to_jpeg(frame_event.frame)
            if jpeg_bytes is None:
                continue

            try:
                t0 = time.monotonic()
                scene = await loop.run_in_executor(
                    None, describe_frame_sync, jpeg_bytes
                )
                scene["latency_ms"] = round((time.monotonic() - t0) * 1000)
                scene["agent"] = "vision"
                await publish_to_band(scene)
            except Exception as e:
                print(f"[VisionAgent] Error: {e}")


def _frame_to_jpeg(frame: rtc.VideoFrame) -> bytes | None:
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
        print(f"[VisionAgent] Frame error: {e}")
        return None


# --- Entrypoint ----------------------------------------------------------- #

if __name__ == "__main__":
    agent = VisionAgent(band_room=os.environ.get("BAND_ROOM", "baymax"))
    asyncio.run(agent.run())
