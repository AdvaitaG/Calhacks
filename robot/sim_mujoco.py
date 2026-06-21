"""MuJoCo sim sink for the return-path bridge (HOUR 2 → simulation).

Drop-in replacement for B1LocoClientStub: same Move(vx,vy,vyaw)/damp() interface,
so the EXACT command_bridge arbitration + failsafe logic now drives a simulated
robot instead of just logging. Runs fully locally — no Nebius, no Band, no SDK.

This is a *kinematic mobile base*: it integrates {vx, vy, vyaw} into the robot's
base pose and renders it. That's deliberate — driving a real humanoid like the
Booster K1 from velocity commands needs a whole-body locomotion policy (see
BoosterRobotics/booster_gym, which ships a velocity-tracking PPO policy + the K1
MuJoCo model). This sink lets you build, watch, and TUNE the command→motion
mapping today; swap in the K1 model + policy when we have it.

Run a scripted demo (reuses the bridge's mock commands):
    cd robot && python sim_mujoco.py            # headless: prints trajectory
    cd robot && python sim_mujoco.py --view     # opens the MuJoCo viewer (WSLg/X)

Or drive the sim from real Band commands:
    cd robot && python command_bridge.py band mujoco
"""
from __future__ import annotations

import asyncio
import logging
import math
import sys
import time

import mujoco

logger = logging.getLogger("sim_mujoco")

# A minimal scene: floor + a "robot" torso/head with a blue forward-arrow, plus
# two capsule "people" it guides on the left (+y) and right (-y). All one body on
# a free joint, so the people travel with the robot. Swap this MJCF for the real
# Booster K1 model when available.
SCENE_XML = """
<mujoco model="baymax_guide">
  <option gravity="0 0 -9.81" timestep="0.005"/>
  <visual><global offwidth="1280" offheight="720"/></visual>
  <worldbody>
    <light pos="0 0 4" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="20 20 0.1" rgba="0.82 0.88 0.82 1"/>
    <body name="robot" pos="0 0 0.35">
      <freejoint name="root"/>
      <geom name="torso" type="box" size="0.14 0.18 0.30" rgba="0.92 0.93 0.97 1"/>
      <geom name="head" type="sphere" pos="0 0 0.40" size="0.12" rgba="0.92 0.93 0.97 1"/>
      <geom name="heading" type="box" pos="0.26 0 0.0" size="0.14 0.025 0.025" rgba="0.20 0.45 0.95 1"/>
      <geom name="person_left"  type="capsule" fromto="0 0.42 -0.35 0 0.42 0.45" size="0.08" rgba="0.25 0.7 0.35 1"/>
      <geom name="person_right" type="capsule" fromto="0 -0.42 -0.35 0 -0.42 0.45" size="0.08" rgba="0.75 0.35 0.25 1"/>
    </body>
  </worldbody>
</mujoco>
"""

BASE_Z = 0.35  # keep the base at a fixed height (kinematic)


class MujocoSink:
    """Velocity-commanded kinematic base. Matches B1LocoClientStub's interface."""

    def __init__(self, xml: str | None = None, model_path: str | None = None,
                 viewer=None) -> None:
        if model_path:
            self.model = mujoco.MjModel.from_xml_path(model_path)
        else:
            self.model = mujoco.MjModel.from_xml_string(xml or SCENE_XML)
        self.data = mujoco.MjData(self.model)
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self._last_t: float | None = None
        self._viewer = viewer
        self._last_log: tuple | None = None
        self._set_pose()

    def _set_pose(self) -> None:
        # free joint qpos = [x, y, z, qw, qx, qy, qz]
        self.data.qpos[0:3] = [self.x, self.y, BASE_Z]
        self.data.qpos[3:7] = [math.cos(self.yaw / 2), 0.0, 0.0, math.sin(self.yaw / 2)]
        mujoco.mj_forward(self.model, self.data)
        if self._viewer is not None:
            self._viewer.sync()

    def Move(self, vx: float, vy: float, vyaw: float) -> None:  # noqa: N802 (SDK name)
        now = time.monotonic()
        dt = 0.0 if self._last_t is None else min(now - self._last_t, 0.2)
        self._last_t = now
        # integrate body-frame velocities into world pose
        self.yaw += vyaw * dt
        self.x += (vx * math.cos(self.yaw) - vy * math.sin(self.yaw)) * dt
        self.y += (vx * math.sin(self.yaw) + vy * math.cos(self.yaw)) * dt
        self._set_pose()
        key = (round(vx, 2), round(vy, 2), round(vyaw, 2))
        if key != self._last_log:
            logger.info("[sim] cmd vx=%.2f vy=%.2f vyaw=%.2f -> pose x=%.2f y=%.2f yaw=%.0f°",
                        vx, vy, vyaw, self.x, self.y, math.degrees(self.yaw))
            self._last_log = key

    def damp(self) -> None:
        logger.info("[sim] emergency hold (damping) at x=%.2f y=%.2f", self.x, self.y)

    @property
    def pose(self) -> tuple[float, float, float]:
        return (self.x, self.y, math.degrees(self.yaw))


async def _demo(view: bool) -> None:
    # reuse the bridge's arbitration loop + scripted commands, but drive the sim
    from command_bridge import run, mock_command_source

    viewer = None
    if view:
        import mujoco.viewer
        sink = MujocoSink()
        viewer = mujoco.viewer.launch_passive(sink.model, sink.data)
        sink._viewer = viewer
    else:
        sink = MujocoSink()

    logger.info("[sim] driving MuJoCo base from mock FINAL_COMMANDs ...")
    await run(mock_command_source(), sink)
    logger.info("[sim] final pose: x=%.2f y=%.2f yaw=%.0f°", *sink.pose)
    if viewer is not None:
        viewer.close()


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    view = "--view" in sys.argv
    asyncio.run(_demo(view))


if __name__ == "__main__":
    main()
