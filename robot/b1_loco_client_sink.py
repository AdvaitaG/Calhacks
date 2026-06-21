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
            )
        except ImportError as e:  # SDK only present on/near the K1
            raise RuntimeError(
                "booster_robotics_sdk_python not installed — the 'real' sink only runs "
                "on/near the K1 (Jetson) with the SDK. Use --sink mujoco off-hardware."
            ) from e

        self._RobotMode = RobotMode
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

    def apply_actions(self, cmd) -> None:
        if cmd is None:
            return
        if cmd.is_emergency or cmd.free_arm_action == "HALT_EXTEND":
            self.damp()
            return
        # TODO(booth): map GENTLE_LEFT_PULL / GENTLE_RIGHT_PULL / FORWARD_PUSH to
        # client.MoveHandEndEffector(target_posture, time_ms, hand_index). The
        # target postures must be tuned against the real K1, so for now the base
        # Move() does the guiding and arm intents are just logged.
        logger.debug("[b1] arms L=%s R=%s free=%s",
                     cmd.left_arm_action, cmd.right_arm_action, cmd.free_arm_action)
