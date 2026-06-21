"""MuJoCo sim sink for the return-path bridge (HOUR 2 → simulation).

Drop-in replacement for B1LocoClientStub: same Move(vx,vy,vyaw)/damp() interface
plus apply_actions(cmd) for the arm/gait signals, so the EXACT command_bridge
arbitration + failsafe logic drives a simulated Booster humanoid. Runs fully
locally — no Nebius, no Band, no SDK.

Model: the real Booster **T1** humanoid (MuJoCo Menagerie) — the K1's sibling,
used here because a public K1 MJCF isn't available. It has the arm joints we need
(shoulder/elbow), so the guide signals are visible.

This is a *kinematic* driver: the base glides per {vx,vy,vyaw} and the legs hold a
standing pose, while the ARMS animate per arm_action — that's the core guiding
mechanism (gentle left/right pull, forward push, halt). Making it actually WALK
needs a trained locomotion policy (BoosterRobotics/booster_gym) on a GPU — that's
the Nebius upgrade. The bridge code doesn't change either way.

Run a scripted demo (reuses the bridge's mock commands):
    cd robot && python sim_mujoco.py            # headless: prints base + arm state
    cd robot && python sim_mujoco.py --view     # opens the MuJoCo viewer (WSLg/X)

Or drive the sim from real Band commands:
    cd robot && python command_bridge.py band mujoco
"""
from __future__ import annotations

import asyncio
import logging
import math
import pathlib
import sys
import time

import mujoco

logger = logging.getLogger("sim_mujoco")

MODEL_PATH = pathlib.Path(__file__).resolve().parent / "models" / "booster_t1" / "scene.xml"

# qpos addresses (from the T1 model; base free joint is qpos[0:7]).
BASE = slice(0, 7)
ARM = {  # joint -> qpos index
    "L_sh_pitch": 9, "L_sh_roll": 10, "L_el_pitch": 11, "L_el_yaw": 12,
    "R_sh_pitch": 13, "R_sh_roll": 14, "R_el_pitch": 15, "R_el_yaw": 16,
}

# Per-arm shoulder offsets (radians) relative to the home pose for each guide
# signal. side = +1 for the left arm, -1 for the right (mirrors the roll).
# Tunable — the point is each action yields a visibly distinct, correct-direction
# arm pose. (pitch<0 swings the arm forward/up; roll abducts it sideways.)
ARM_SIGNAL = {
    "HOLD_STEADY":       (0.0, 0.0),   # rest at home
    "GENTLE_LEFT_PULL":  (-0.4, 0.5),  # lead toward the left
    "GENTLE_RIGHT_PULL": (-0.4, -0.5),
    "FORWARD_PUSH":      (-1.0, 0.0),  # extend arm forward
    "RELEASE":           (0.6, 0.0),   # arm relaxes downward
}
HALT_EXTEND = (-1.4, 0.0)  # emergency: arm raised palm-out (traffic-stop)


class MujocoSink:
    """Velocity-commanded kinematic humanoid. Matches the B1LocoClient interface."""

    def __init__(self, model_path: str | None = None, viewer=None) -> None:
        self.model = mujoco.MjModel.from_xml_path(str(model_path or MODEL_PATH))
        self.data = mujoco.MjData(self.model)
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)  # 'home' standing pose
        self.home = self.data.qpos.copy()
        self.x, self.y, self.yaw = 0.0, 0.0, 0.0
        self.base_z = float(self.home[2])
        self._last_t: float | None = None
        self._viewer = viewer
        self._last_log = None
        self._emergency = False
        self._set()

    def _set(self) -> None:
        self.data.qpos[BASE] = [self.x, self.y, self.base_z,
                                math.cos(self.yaw / 2), 0.0, 0.0, math.sin(self.yaw / 2)]
        mujoco.mj_forward(self.model, self.data)
        if self._viewer is not None:
            self._viewer.sync()

    def Move(self, vx: float, vy: float, vyaw: float) -> None:  # noqa: N802 (SDK name)
        now = time.monotonic()
        dt = 0.0 if self._last_t is None else min(now - self._last_t, 0.2)
        self._last_t = now
        self.yaw += vyaw * dt
        self.x += (vx * math.cos(self.yaw) - vy * math.sin(self.yaw)) * dt
        self.y += (vx * math.sin(self.yaw) + vy * math.cos(self.yaw)) * dt
        self._set()

    def _arm_to(self, side: str, sign: int, pitch: float, roll: float) -> None:
        """Lerp one shoulder toward (home + offset) for smooth motion."""
        q = self.data.qpos
        tp = self.home[ARM[f"{side}_sh_pitch"]] + pitch
        tr = self.home[ARM[f"{side}_sh_roll"]] + sign * roll
        ip, ir = ARM[f"{side}_sh_pitch"], ARM[f"{side}_sh_roll"]
        q[ip] += (tp - q[ip]) * 0.25
        q[ir] += (tr - q[ir]) * 0.25

    def apply_actions(self, cmd) -> None:
        """Drive the arms from a FINAL_COMMAND's arm actions (or None -> rest)."""
        if cmd is None:
            la = ra = "HOLD_STEADY"
            emergency = False
        else:
            emergency = cmd.is_emergency or cmd.free_arm_action == "HALT_EXTEND"
            la = cmd.left_arm_action or "HOLD_STEADY"
            ra = cmd.right_arm_action or "HOLD_STEADY"
        if emergency:
            self._arm_to("L", +1, *HALT_EXTEND)
            self._arm_to("R", -1, *HALT_EXTEND)
        else:
            self._arm_to("L", +1, *ARM_SIGNAL.get(la, ARM_SIGNAL["HOLD_STEADY"]))
            self._arm_to("R", -1, *ARM_SIGNAL.get(ra, ARM_SIGNAL["HOLD_STEADY"]))
        self._set()
        key = (la, ra, emergency)
        if key != self._last_log:
            logger.info("[sim] arms L=%s R=%s%s", la, ra, "  [EMERGENCY HALT]" if emergency else "")
            self._last_log = key

    def damp(self) -> None:
        logger.info("[sim] emergency hold (damping) at x=%.2f y=%.2f", self.x, self.y)

    @property
    def pose(self) -> tuple[float, float, float]:
        return (self.x, self.y, math.degrees(self.yaw))


def _front_view(viewer, model) -> None:
    """Camera that follows the robot with a clean, full front view."""
    # track the base body (the one carrying the free joint) so it stays centered
    free_joint = 0  # the only free joint in the model
    cam = viewer.cam
    cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
    cam.trackbodyid = int(model.jnt_bodyid[free_joint])
    cam.distance = 3.2      # whole ~1.3 m robot in frame
    cam.azimuth = 180.0     # in front of a +x-facing robot -> sees the front
    cam.elevation = -8.0    # slight downward tilt
    viewer.sync()


async def _demo(view: bool) -> None:
    from command_bridge import run, mock_command_source

    sink = MujocoSink()
    viewer = None
    if view:
        import mujoco.viewer
        viewer = mujoco.viewer.launch_passive(sink.model, sink.data)
        _front_view(viewer, sink.model)
        sink._viewer = viewer
    logger.info("[sim] driving Booster T1 from mock FINAL_COMMANDs ...")
    await run(mock_command_source(), sink)
    logger.info("[sim] final pose: x=%.2f y=%.2f yaw=%.0f°", *sink.pose)
    if viewer is not None:
        viewer.close()


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(_demo("--view" in sys.argv))


if __name__ == "__main__":
    main()
