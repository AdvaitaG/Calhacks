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
SLEW_XY = float(os.environ.get("BOOSTER_SLEW_XY", "0.015"))   # gentler accel = steadier gait
SLEW_YAW = float(os.environ.get("BOOSTER_SLEW_YAW", "0.03"))


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
        except Exception as e:  # noqa: BLE001 — never let a rejected Move kill the loop
            self._recover(e)

    def _recover(self, err) -> None:
        """Move rejected (502 / RPC timeout) = robot not walking-ready, usually
        FALLEN. In this Webots sim a fall is NOT recoverable from the SDK (GetUp
        just floods the runner with RPC timeouts and makes it worse) — only a
        Webots reset stands it back up. So don't fight it: keep the control loop
        alive and warn at most once / 5 s."""
        now = time.monotonic()
        if now - self._last_recover > 5.0:
            self._last_recover = now
            logger.warning("[b1] Move rejected (%s) — sim not executing motion. Check: is "
                           "Webots PLAYING (clock advancing)? is the runner alive? If the "
                           "robot fell, Simulation->Reset->Play; if it's standing/frozen, "
                           "press Play or restart the runner.", err)

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
