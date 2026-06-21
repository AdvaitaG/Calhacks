"""Baymax robot-side process — HOUR 1: webcam -> LiveKit.

Captures your laptop webcam and publishes it into the LiveKit room as the
`front_camera` video track so Advaita's Vision Agent can subscribe.

It also already listens for incoming actions (the command path) and just
logs them — that's the hook you'll flesh out in Hour 2 to drive the
Booster K1 via B1LocoClient.

Run:
    cd robot
    python robot.py

Swap the webcam for the real K1 camera later; everything else stays.
"""
from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import time

import cv2
from livekit.portal import Action, PortalError, Robot, RobotConfig

from _common import env_int, load_env, mint_token, pace, required_env

IDENTITY = "robot"
CAMERA_TRACK = "front_camera"
CONFIG_PATH = pathlib.Path(__file__).resolve().parent / "portal.yaml"

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_env()

    url = required_env("LIVEKIT_URL")
    room = required_env("LIVEKIT_ROOM")
    token = mint_token(IDENTITY, room)

    cfg = RobotConfig.from_yaml_file(CONFIG_PATH, room)
    fps = env_int("PORTAL_FPS", 30)

    # --- open the webcam ------------------------------------------------
    cam_index = env_int("WEBCAM_INDEX", 0)
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise RuntimeError(
            f"could not open webcam index {cam_index}; "
            f"set WEBCAM_INDEX in .env (try 0, 1, 2)"
        )

    # --- connect to LiveKit --------------------------------------------
    robot = Robot(cfg)
    latest_action: dict[str, float] = {}

    def on_action(action: Action) -> None:
        # HOUR 2 hook: this is where a FINAL_COMMAND, translated to
        # {vx, vy, vyaw}, arrives. For now just log it.
        nonlocal latest_action
        latest_action = {k: float(v) for k, v in action.values.items()}
        logger.info("[robot] action received: %s", latest_action)

    robot.on_action(on_action)

    logger.info("[robot] connecting to %s as '%s' in room '%s' ...", url, IDENTITY, room)
    await robot.connect(url, token)
    logger.info("[robot] connected; streaming webcam %d at %d fps; ctrl-c to stop",
                cam_index, fps)

    try:
        async for tick in pace(fps):
            ts_us = int(time.time() * 1_000_000)

            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            # h264 publisher rejects odd dimensions — crop to even.
            h, w = frame.shape[:2]
            frame = frame[: h - (h % 2), : w - (w % 2)]
            # OpenCV gives BGR; Portal expects RGB. If colors look swapped
            # in the viewer, comment this line out.
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            try:
                robot.send_video_frame(CAMERA_TRACK, frame, timestamp_us=ts_us)
            except PortalError as e:
                logger.warning("[robot] send_video_frame failed: %s", e)

            if tick % fps == 0:  # once per second
                logger.info("[robot] streaming '%s' %dx%d (tick %d)",
                            CAMERA_TRACK, frame.shape[1], frame.shape[0], tick)
    except KeyboardInterrupt:
        logger.info("[robot] stopping ...")
    finally:
        logger.info("[robot] disconnecting ...")
        try:
            await robot.disconnect()
        finally:
            robot.close()
            cap.release()


if __name__ == "__main__":
    asyncio.run(main())
