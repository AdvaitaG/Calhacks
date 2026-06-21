"""Real Booster hardware/sim sink — drives the robot via the K1 SDK
(booster_robotics_sdk_python -> B1LocoClient). Mirrors the bridge's sink
interface (Move / damp / apply_actions) so it's a drop-in for B1LocoClientStub
and MujocoSink:

    cd robot && python command_bridge.py mock real    # scripted commands -> sim
    cd robot && python command_bridge.py band real     # live Band commands -> sim

Talks to whatever controller is on BOOSTER_ROBOT_ADDR (default 127.0.0.1):
the Webots sim's control runner, Booster Studio, or the real robot's IP.

The firmware provides the presets, so this sink is thin — it forwards:
  Move(vx,vy,vyaw)   -> client.Move          (firmware walk cycle, slew-limited)
  damp()             -> ChangeMode(kDamping) (emergency hold)
  WaveHand()         -> client.WaveHand      (built-in wave gesture)
  apply_actions(cmd) -> arm guide signals (opt-in: BAYMAX_ARMS=1)

IMPORTANT (learned against the Webots sim): the controller rejects Move with
error 502 unless the robot is first brought up Prepare -> (stand) -> Walking.
We do that in __init__. Arm end-effector moves destabilize the lightweight sim,
so they're OFF unless BAYMAX_ARMS is set.
"""
from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger("b1_sink")

# Seconds to let the robot physically stand up after Prepare before Walking.
PREPARE_SECS = float(os.environ.get("BOOSTER_PREPARE_SECS", "6"))
# Max velocity change per Move() call (~20 Hz). Smooths abrupt command jumps so
# the gait isn't shocked into a fall. ~0.4 m/s^2 and ~1.0 rad/s^2.
SLEW_XY = float(os.environ.get("BOOSTER_SLEW_XY", "0.045"))   # snappy accel -> hits big strides fast
SLEW_YAW = float(os.environ.get("BOOSTER_SLEW_YAW", "0.07"))

# A rejected Move (502 / RPC timeout) is usually a transient blip, NOT a fall.
# Keep commanding through failures for this long before assuming the robot is
# actually down — this is the "down" sensitivity knob. Higher = less twitchy.
FALL_GRACE_S = float(os.environ.get("BOOSTER_FALL_GRACE", "2.5"))
# Don't re-attempt the get-up sequence more often than this.
RECOVER_COOLDOWN_S = float(os.environ.get("BOOSTER_RECOVER_COOLDOWN", "12"))
# Set BOOSTER_AUTORECOVER=0 to disable the auto stand-up attempt.
AUTORECOVER = os.environ.get("BOOSTER_AUTORECOVER", "1") != "0"


def _slew(cur: float, tgt: float, step: float) -> float:
    if tgt > cur:
        return min(cur + step, tgt)
    return max(cur - step, tgt)


class B1LocoClientSink:
    def __init__(self) -> None:
        try:
            from booster_robotics_sdk_python import (
                B1LocoClient, ChannelFactory, RobotMode,
                Position, Orientation, Posture, HandIndex,
            )
        except ImportError as e:  # SDK only present on the 22.04 distro
            raise RuntimeError(
                "booster_robotics_sdk_python not installed — the 'real' sink needs "
                "the SDK (Ubuntu 22.04). Use --sink mujoco off the SDK box."
            ) from e

        self._RobotMode = RobotMode
        self._Position, self._Orientation, self._Posture = Position, Orientation, Posture
        self._hand = {"L": HandIndex.kLeftHand, "R": HandIndex.kRightHand}
        self._last_arms = None
        self._cur = (0.0, 0.0, 0.0)  # current (slewed) velocity setpoint
        self._last_recover = 0.0     # last fall-recovery attempt (monotonic)
        self._fail_since = None      # monotonic time the current Move-failure streak began
        self._arms_enabled = bool(os.environ.get("BAYMAX_ARMS"))

        #   "127.0.0.1"      -> local sim control runner / Booster Studio
        #   <robot IP>       -> the physical robot
        addr = os.environ.get("BOOSTER_ROBOT_ADDR", "127.0.0.1")
        ChannelFactory.Instance().Init(0, addr)
        logger.info("[b1] DDS endpoint: %s", addr)
        self.client = B1LocoClient()
        self.client.Init()

        # Bring the robot up: Prepare (stand) -> Walking. Skipping Prepare is the
        # cause of Move error 502.
        logger.info("[b1] ChangeMode(Prepare) — standing up ...")
        self.client.ChangeMode(RobotMode.kPrepare)
        time.sleep(PREPARE_SECS)
        self.client.ChangeMode(RobotMode.kWalking)
        time.sleep(2.0)
        self._damping = False
        logger.info("[b1] connected to %s; mode=Walking, arms=%s",
                    addr, "on" if self._arms_enabled else "off")

    def Move(self, vx: float, vy: float, vyaw: float) -> None:  # noqa: N802 (SDK name)
        if self._damping and (vx or vy or vyaw):
            self.client.ChangeMode(self._RobotMode.kWalking)  # leave emergency hold
            self._damping = False
        cx, cy, cyaw = self._cur
        cx = _slew(cx, float(vx), SLEW_XY)
        cy = _slew(cy, float(vy), SLEW_XY)
        cyaw = _slew(cyaw, float(vyaw), SLEW_YAW)
        self._cur = (cx, cy, cyaw)
        try:
            self.client.Move(cx, cy, cyaw)
            self._fail_since = None          # a successful Move clears the fall timer
        except Exception as e:  # noqa: BLE001 — never let a rejected Move kill the loop
            self._on_move_fail(e)

    def _on_move_fail(self, err) -> None:
        """A rejected Move is usually a transient RPC blip, NOT a fall. Tolerate
        brief failures (keep commanding so the robot walks straight through them);
        only when motion stays dead past FALL_GRACE_S do we treat it as a real
        fall and attempt a stand-up. This is the de-twitched 'down' detection."""
        now = time.monotonic()
        if self._fail_since is None:
            self._fail_since = now
            return                            # first blip — ignore, keep walking
        if now - self._fail_since < FALL_GRACE_S:
            return                            # still inside the tolerance window
        if now - self._last_recover < RECOVER_COOLDOWN_S:
            return                            # recently attempted; let it settle
        self._last_recover = now
        if AUTORECOVER:
            self._self_recover()
        else:
            logger.warning("[b1] no motion for %.1fs — robot likely down (auto-recover off).",
                           now - self._fail_since)

    def _self_recover(self) -> None:
        """Confirmed fall — stand back up WITHOUT manual intervention. Best-effort
        damp -> get-up -> prepare -> walk; each step independent so a missing skill
        doesn't abort the rest. If this sim's RL controller has no get-up, this
        won't succeed (only a Webots reset would) — but it's safe to try."""
        RM = self._RobotMode
        logger.warning("[b1] motion dead >%.1fs — assuming a fall; attempting self-recovery ...",
                       FALL_GRACE_S)
        for name, fn, wait in (
            ("damp",    lambda: self.client.ChangeMode(RM.kDamping), 1.0),
            ("get-up",  lambda: self.client.GetUp(),                 3.0),
            ("prepare", lambda: self.client.ChangeMode(RM.kPrepare), PREPARE_SECS),
            ("walk",    lambda: self.client.ChangeMode(RM.kWalking), 1.5),
        ):
            try:
                fn()
                time.sleep(wait)
            except Exception as e:  # noqa: BLE001
                logger.warning("[b1]   recovery step '%s' not available: %s",
                               name, str(e).splitlines()[0][:60])
        self._cur = (0.0, 0.0, 0.0)
        self._fail_since = None
        logger.info("[b1] recovery sequence finished — resuming commands")

    def damp(self) -> None:
        if not self._damping:
            self.client.ChangeMode(self._RobotMode.kDamping)
            self._damping = True
            self._cur = (0.0, 0.0, 0.0)
            logger.info("[b1] EMERGENCY -> Damping mode")

    def WaveHand(self, hand_action=None) -> None:  # noqa: N802 (SDK name)
        """Built-in wave gesture preset (B1LocoClient.WaveHand)."""
        try:
            from booster_robotics_sdk_python import HandAction
            self.client.WaveHand(hand_action or HandAction.kHandOpen)
            logger.info("[b1] WaveHand")
        except Exception as e:  # noqa: BLE001
            logger.warning("[b1] WaveHand failed: %s", e)

    def _posture(self, action: str, hand: str):
        """Hand end-effector target for a guide signal. Frame: x fwd, +y left,
        z up. TODO(booth): tune to the real reach envelope."""
        side = 1.0 if hand == "L" else -1.0
        base_y = 0.25 * side
        table = {
            "HOLD_STEADY":       (0.30, base_y,        0.00),
            "RELEASE":           (0.22, base_y,       -0.10),
            "FORWARD_PUSH":      (0.42, base_y,        0.05),
            "GENTLE_LEFT_PULL":  (0.32, base_y + 0.12, 0.02),
            "GENTLE_RIGHT_PULL": (0.32, base_y - 0.12, 0.02),
        }
        x, y, z = table.get(action, table["HOLD_STEADY"])
        p = self._Posture()
        p.position = self._Position(x, y, z)
        p.orientation = self._Orientation(0.0, 0.0, 0.0)
        return p

    def apply_actions(self, cmd) -> None:
        if cmd is None:
            return
        if cmd.is_emergency or cmd.free_arm_action == "HALT_EXTEND":
            self.damp()
            return
        if not self._arms_enabled:
            return  # arms off by default — they topple the lightweight sim T1
        la = cmd.left_arm_action or "HOLD_STEADY"
        ra = cmd.right_arm_action or "HOLD_STEADY"
        if (la, ra) == self._last_arms:
            return  # only re-send to the SDK when the guide signal changes
        self._last_arms = (la, ra)
        t = max(300, int(getattr(cmd, "pace_ms", 500)))
        try:
            self.client.MoveHandEndEffector(self._posture(la, "L"), t, self._hand["L"])
            self.client.MoveHandEndEffector(self._posture(ra, "R"), t, self._hand["R"])
            logger.info("[b1] arms L=%s R=%s -> MoveHandEndEffector", la, ra)
        except Exception as e:  # noqa: BLE001
            logger.warning("[b1] MoveHandEndEffector failed: %s", e)
