"""Synthetic camera publisher — a stand-in for webcam_publish.py when there's no
webcam (e.g. running the whole pipeline in WSL). Publishes a static scene with an
obstacle into the LiveKit room as `front_camera`, so the Vision Agent has frames
to describe.

    cd robot && python sim_camera.py

Use webcam_publish.py instead when you have a real camera (Windows).
"""
from __future__ import annotations

import asyncio
import itertools
import sys

import cv2
import numpy as np

sys.path.insert(0, ".")
from _common import load_env, mint_token, required_env

W, H = 640, 480


async def main() -> None:
    load_env()
    from livekit import rtc

    url = required_env("LIVEKIT_URL")
    room_name = required_env("LIVEKIT_ROOM")
    room = rtc.Room()
    await room.connect(url, mint_token("robot", room_name))
    source = rtc.VideoSource(W, H)
    track = rtc.LocalVideoTrack.create_video_track("front_camera", source)
    await room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_CAMERA))

    # a sidewalk scene: ground + a red obstacle slightly right of center
    frame = np.full((H, W, 3), 205, np.uint8)
    cv2.rectangle(frame, (0, 310), (W, H), (155, 155, 155), -1)
    cv2.rectangle(frame, (360, 170), (480, 320), (40, 40, 200), -1)
    cv2.putText(frame, "obstacle ahead-right", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
    print("[sim_camera] publishing front_camera frames; ctrl-c to stop")
    try:
        for _ in itertools.count():
            source.capture_frame(rtc.VideoFrame(W, H, rtc.VideoBufferType.RGBA, rgba.tobytes()))
            await asyncio.sleep(1 / 15)
    except KeyboardInterrupt:
        pass
    finally:
        await room.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
