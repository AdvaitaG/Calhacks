r"""Portal-free webcam -> LiveKit publisher (HOUR 1, Windows-friendly).

`robot.py` uses livekit-portal, which has NO Windows wheel. This script does
the same Hour-1 job — publish the laptop webcam into the LiveKit room as a
video track Advaita's Vision Agent can subscribe to — using only the plain
`livekit` rtc SDK, which DOES run on native Windows (where the webcam works).

The Vision Agent subscribes to any KIND_VIDEO track (vision_agent.py), so the
track name is cosmetic here, but we keep `front_camera` for consistency.

Run (Windows PowerShell, from repo root):
    py -m venv .venv-win
    .\.venv-win\Scripts\pip install livekit livekit-api opencv-python python-dotenv
    cd robot
    ..\.venv-win\Scripts\python webcam_publish.py

Use robot.py (Portal) on the actual Linux/Jetson robot; use this on Windows.
"""
from __future__ import annotations

import asyncio
import logging
import os

import cv2
from livekit import rtc

from _common import env_int, load_env, mint_token, pace, required_env

IDENTITY = "robot"
CAMERA_TRACK = "front_camera"
WIDTH, HEIGHT = 640, 480

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_env()

    url = required_env("LIVEKIT_URL")
    room_name = required_env("LIVEKIT_ROOM")
    token = mint_token(IDENTITY, room_name)
    fps = env_int("PORTAL_FPS", 30)

    # --- open the webcam ------------------------------------------------
    cam_index = env_int("WEBCAM_INDEX", 0)
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    if not cap.isOpened():
        raise RuntimeError(
            f"could not open webcam index {cam_index}; "
            f"set WEBCAM_INDEX in .env (try 0, 1, 2)"
        )

    # --- connect + publish a video track -------------------------------
    room = rtc.Room()
    logger.info("[robot] connecting to %s as '%s' in room '%s' ...",
                url, IDENTITY, room_name)
    await room.connect(url, token)

    source = rtc.VideoSource(WIDTH, HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track(CAMERA_TRACK, source)
    await room.local_participant.publish_track(
        track,
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_CAMERA),
    )
    logger.info("[robot] published track '%s'; streaming webcam %d at %d fps; "
                "ctrl-c to stop", CAMERA_TRACK, cam_index, fps)

    try:
        async for tick in pace(fps):
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            # OpenCV gives BGR; the rtc RGBA buffer wants 4-channel RGBA.
            frame = cv2.resize(frame, (WIDTH, HEIGHT))
            rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            vframe = rtc.VideoFrame(WIDTH, HEIGHT,
                                    rtc.VideoBufferType.RGBA, rgba.tobytes())
            source.capture_frame(vframe)

            if tick % fps == 0:  # once per second
                logger.info("[robot] streaming '%s' %dx%d (tick %d)",
                            CAMERA_TRACK, WIDTH, HEIGHT, tick)
    except KeyboardInterrupt:
        logger.info("[robot] stopping ...")
    finally:
        logger.info("[robot] disconnecting ...")
        cap.release()
        try:
            await room.disconnect()
        except (asyncio.CancelledError, Exception):
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
