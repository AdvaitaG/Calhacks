"""Real Booster K1 hardware sink — drives the actual robot via the K1 SDK
(booster_robotics_sdk_python -> B1LocoClient). Mirrors the bridge's sink
interface (Move / damp / apply_actions) so it's a drop-in for B1LocoClientStub
and MujocoSink:

    cd robot && python command_bridge.py band real

The K1 firmware provides the presets, so this sink is thin — it just forwards:
  Move(vx,vy,vyaw)   -> client.Move          (firmware walk cycle)
  damp()             -> ChangeMode(kDamping) (emergency hold)
  WaveHand()         -> client.WaveHand      (built-in wave gesture)
  apply_actions(cmd) -> arm guide signals; EMERGENCY/HALT_EXTEND -> damp

Requires booster_robotics_sdk_python (installed on/near the K1's Jetson) and the
robot reachable over DDS. Set BOOSTER_NET_IFACE to the NIC that reaches the robot.
Run --sink mujoco for the simulator when off-hardware.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("b1_sink")


class B1LocoClientSink:
    def __init__(self) -> None:
        try:
            from booster_robotics_sdk_python import (
                B1LocoClient, ChannelFactory, RobotMode,
                Position, Orientation, Posture, B1HandIndex,
            )
        except ImportError as e:  # SDK only present on/near the K1
            raise RuntimeError(
                "booster_robotics_sdk_python not installed — the 'real' sink only runs "
                "on/near the K1 (Jetson) with the SDK. Use --sink mujoco off-hardware."
            ) from e

        self._RobotMode = RobotMode
        self._Position, self._Orientation, self._Posture = Position, Orientation, Posture
        self._hand = {"L": B1HandIndex.kLeftHand, "R": B1HandIndex.kRightHand}
        self._last_arms = None
        iface = os.environ.get("BOOSTER_NET_IFACE", "")
        if iface:
            ChannelFactory.Instance().Init(0, iface)
        else:
            ChannelFactory.Instance().Init(0)
        self.client = B1LocoClient()
        self.client.Init()
        self.client.ChangeMode(RobotMode.kWalking)
        self._damping = False
        logger.info("[b1] connected to K1 via SDK (iface=%r); mode=Walking",
                    iface or "default")

    def Move(self, vx: float, vy: float, vyaw: float) -> None:  # noqa: N802 (SDK name)
        if self._damping and (vx or vy or vyaw):
            self.client.ChangeMode(self._RobotMode.kWalking)  # leave emergency hold
            self._damping = False
        self.client.Move(float(vx), float(vy), float(vyaw))

    def damp(self) -> None:
        if not self._damping:
            self.client.ChangeMode(self._RobotMode.kDamping)
            self._damping = True
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
        z up. TODO(booth): tune these against the real K1 reach envelope."""
        side = 1.0 if hand == "L" else -1.0
        base_y = 0.25 * side                      # left hand at +y, right at -y
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
