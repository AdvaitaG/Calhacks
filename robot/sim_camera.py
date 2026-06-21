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
import os
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

    # Cycle a few scenes so the Conductor produces varied commands and the robot
    # visibly walks + steers (instead of one static obstacle -> always STOP).
    def base() -> np.ndarray:
        f = np.full((H, W, 3), 205, np.uint8)
        cv2.rectangle(f, (0, 310), (W, H), (155, 155, 155), -1)  # ground
        return f

    def labelled(f, text):
        cv2.putText(f, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
        return cv2.cvtColor(f, cv2.COLOR_BGR2RGBA)

    clear = labelled(base(), "clear path ahead")
    f = base(); cv2.rectangle(f, (40, 170), (170, 320), (40, 40, 200), -1)
    obstacle_left = labelled(f, "obstacle on the LEFT")
    f = base(); cv2.rectangle(f, (470, 170), (600, 320), (40, 40, 200), -1)
    obstacle_right = labelled(f, "obstacle on the RIGHT")
    # obstacle DIRECTLY AHEAD (centered, large) — this should block forward motion
    f = base(); cv2.rectangle(f, (240, 120), (420, 340), (40, 40, 200), -1)
    blocked = labelled(f, "obstacle DIRECTLY AHEAD")
    frames = {"clear": clear, "obstacle-left": obstacle_left,
              "obstacle-right": obstacle_right, "blocked-ahead": blocked}

    # Demo-tuned order: mostly confident forward motion, guide around side
    # obstacles, with an occasional 'blocked-ahead' for the dramatic safety stop.
    # Override live with BAYMAX_SCENES="clear,obstacle-left,clear,..." and
    # BAYMAX_SCENE_SECS=<seconds per scene>.
    order = os.environ.get(
        "BAYMAX_SCENES",
        "clear,clear,obstacle-left,clear,obstacle-right,clear,clear,blocked-ahead,clear",
    ).split(",")
    period = float(os.environ.get("BAYMAX_SCENE_SECS", "7"))
    print(f"[sim_camera] scene order ({period:.0f}s each): {order}")
    try:
        for i in itertools.count():
            name = order[int(i / (15 * period)) % len(order)]
            rgba = frames.get(name, clear)
            if i % int(15 * period) == 0:
                print(f"[sim_camera] scene -> {name}")
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
