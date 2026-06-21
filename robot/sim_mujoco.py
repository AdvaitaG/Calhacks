"""MuJoCo sim sink for the return-path bridge (HOUR 2 → simulation).

Drop-in replacement for B1LocoClientStub: same Move(vx,vy,vyaw)/damp() interface
plus apply_actions(cmd) for the arm/gait signals, so the EXACT command_bridge
arbitration + failsafe logic drives a simulated Booster humanoid. Runs fully
locally — no Nebius, no Band, no SDK.

Model: the real Booster **K1** humanoid (K1_22dof.xml from BoosterRobotics/
booster_assets) — the actual robot this project targets. Self-contained MJCF
(meshes + floor + lights); 22 DOF including the arm joints used for guide signals.

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

MODEL_PATH = pathlib.Path(__file__).resolve().parent / "models" / "booster_k1" / "K1_22dof.xml"

BASE = slice(0, 7)  # free joint occupies qpos[0:7]

# Use name-based lookup at runtime — immune to XML joint ordering changes.
def _jaddr(model, name: str) -> int:
    return int(model.joint(name).qposadr[0])

# Proper standing pose for K1 — slight knee bend so robot doesn't fall through floor.
# Hip/knee/ankle angles are in radians; arms hang naturally.
STANDING_POSE = {
    "Left_Hip_Pitch":   -0.05,
    "Left_Hip_Roll":     0.03,
    "Left_Knee_Pitch":   0.10,
    "Left_Ankle_Pitch":  0.05,
    "Right_Hip_Pitch":  -0.05,
    "Right_Hip_Roll":   -0.03,
    "Right_Knee_Pitch":  0.10,
    "Right_Ankle_Pitch": 0.05,
    "ALeft_Shoulder_Pitch":  0.1,
    "Left_Shoulder_Roll":    0.2,
    "ARight_Shoulder_Pitch": 0.1,
    "Right_Shoulder_Roll":  -0.2,
}

# Per-arm shoulder offsets (radians) for each guide signal.
# pitch<0 = arm swings forward/up; roll = abducts sideways.
# sign parameter mirrors roll direction for left (+1) vs right (-1) arm.
ARM_SIGNAL = {
    "HOLD_STEADY":       (0.0,  0.0),
    "GENTLE_LEFT_PULL":  (-0.5, 0.6),
    "GENTLE_RIGHT_PULL": (-0.5,-0.6),
    "FORWARD_PUSH":      (-1.2, 0.0),
    "RELEASE":           (0.5,  0.0),
}
HALT_EXTEND = (-1.6, 0.0)  # emergency: arm raised palm-out

# Leg joint names for gait animation.
LEG_JOINTS = {
    "L_hip":   "Left_Hip_Pitch",
    "L_knee":  "Left_Knee_Pitch",
    "L_ankle": "Left_Ankle_Pitch",
    "R_hip":   "Right_Hip_Pitch",
    "R_knee":  "Right_Knee_Pitch",
    "R_ankle": "Right_Ankle_Pitch",
}
# Gait shaping (radians / Hz). Kinematic stand-in for a learned locomotion
# policy — legs swing in anti-phase, amplitude scales with speed. The real
# physics gait needs an RL policy trained on GPU (booster_gym/booster_train,
# i.e. Nebius); booster_deploy has the K1 locomotion config but ships no K1
# walk checkpoint.
STEP_FREQ = 1.4        # steps/sec at full speed
REF_SPEED = 0.3        # m/s that maps to full stride (matches MOVE_FORWARD vx)
HIP_AMP = 0.55         # thigh swing
KNEE_AMP = 0.9         # knee flexion on the swinging leg


class MujocoSink:
    """Velocity-commanded kinematic humanoid. Matches the B1LocoClient interface."""

    def __init__(self, model_path: str | None = None, viewer=None) -> None:
        self.model = mujoco.MjModel.from_xml_path(str(model_path or MODEL_PATH))
        self.data = mujoco.MjData(self.model)
        mujoco.mj_resetData(self.model, self.data)

        # Build name -> qpos address map for all joints we care about
        self._jmap = {}
        for name in list(STANDING_POSE.keys()) + list(LEG_JOINTS.values()) + [
            "ALeft_Shoulder_Pitch", "Left_Shoulder_Roll",
            "ARight_Shoulder_Pitch", "Right_Shoulder_Roll",
        ]:
            try:
                self._jmap[name] = _jaddr(self.model, name)
            except Exception:
                pass

        # Set proper standing pose
        for jname, angle in STANDING_POSE.items():
            if jname in self._jmap:
                self.data.qpos[self._jmap[jname]] = angle

        # Place robot at standing height
        self.data.qpos[2] = 0.72  # K1 hip height ~0.72m
        self.data.qpos[3] = 1.0   # quaternion w=1 (upright)
        self.data.qpos[4] = 0.0
        self.data.qpos[5] = 0.0
        self.data.qpos[6] = 0.0
        mujoco.mj_forward(self.model, self.data)

        self.home = self.data.qpos.copy()
        self.x, self.y, self.yaw = 0.0, 0.0, 0.0
        self.base_z = float(self.home[2])
        self.phase = 0.0  # gait cycle phase
        self._wave_until = 0.0  # kinematic wave active until this monotonic time
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
        self._walk(vx, vy, vyaw, dt)
        self._set()

    def _walk(self, vx: float, vy: float, vyaw: float, dt: float) -> None:
        """Procedural anti-phase leg gait; amplitude scales with speed, legs
        return to standing when stopped."""
        q = self.data.qpos
        speed = math.hypot(vx, vy) + 0.3 * abs(vyaw)
        amp = max(0.0, min(speed / REF_SPEED, 1.0))
        if amp > 0.02:
            self.phase += 2 * math.pi * STEP_FREQ * amp * dt
            s = math.sin(self.phase)
            for side, ph in (("L", self.phase), ("R", self.phase + math.pi)):
                sw = math.sin(ph)
                q[LEG[f"{side}_hip_pitch"]] = HIP_AMP * amp * sw
                q[LEG[f"{side}_knee"]] = KNEE_AMP * amp * max(0.0, sw)   # bend on forward swing
                q[LEG[f"{side}_ankle_pitch"]] = -0.4 * HIP_AMP * amp * sw
        else:
            # ease legs back to a straight stand
            for k in LEG.values():
                q[k] += (self.home[k] - q[k]) * 0.2

    def _arm_to(self, side: str, sign: int, pitch: float, roll: float) -> None:
        """Lerp one shoulder toward (home + offset) for smooth motion."""
        q = self.data.qpos
        tp = self.home[ARM[f"{side}_sh_pitch"]] + pitch
        tr = self.home[ARM[f"{side}_sh_roll"]] + sign * roll
        ip, ir = ARM[f"{side}_sh_pitch"], ARM[f"{side}_sh_roll"]
        q[ip] += (tp - q[ip]) * 0.25
        q[ir] += (tr - q[ir]) * 0.25

    def WaveHand(self, hand_action=None) -> None:  # noqa: N802 (mirror SDK name)
        """Kinematic wave — mirrors B1LocoClient.WaveHand. Waves the right arm
        for ~2.5s; the wave overrides arm signals while active."""
        self._wave_until = time.monotonic() + 2.5
        logger.info("[sim] WaveHand")

    def apply_actions(self, cmd) -> None:
        """Drive the arms from a FINAL_COMMAND's arm actions (or None -> rest)."""
        if time.monotonic() < self._wave_until:
            # hello wave: raise the right arm high and rock the FOREARM at the
            # elbow side-to-side (a greeting, not a sideways arm swing).
            q = self.data.qpos
            w = math.sin((self._wave_until - time.monotonic()) * 9.0)
            q[ARM["R_sh_pitch"]] = self.home[ARM["R_sh_pitch"]] - 1.8   # arm raised high
            q[ARM["R_sh_roll"]] = self.home[ARM["R_sh_roll"]] - 0.25    # slightly out from body
            q[ARM["R_el_pitch"]] = self.home[ARM["R_el_pitch"]] + 0.5 + 0.6 * w  # forearm waves
            self._set()
            return
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
    logger.info("[sim] driving Booster K1 from mock FINAL_COMMANDs ...")
    await run(mock_command_source(), sink)
    logger.info("[sim] final pose: x=%.2f y=%.2f yaw=%.0f°", *sink.pose)
    if viewer is not None:
        viewer.close()


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(_demo("--view" in sys.argv))


if __name__ == "__main__":
    main()
