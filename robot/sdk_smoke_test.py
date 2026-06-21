"""Minimal Booster K1 SDK smoke test — proves B1LocoClient can drive a SIM.

This is the *simplest possible* use of the real K1 SDK against a simulated robot
controller (Booster Studio on localhost). It is deliberately standalone: no Band,
no agents, no LiveKit, no command_bridge — just the SDK, so you can confirm the
DDS link works before wiring anything else in.

It mirrors Booster's official example (`./b1_loco_example_client 127.0.0.1`):
connect over Fast-DDS, enter Walking mode, send a few Move() velocities, wave,
then stop and damp.

PREREQUISITES (see the chat notes):
  * Run this on Ubuntu 22.04 (the SDK does NOT support 24.04). On this Windows
    box that means an Ubuntu-22.04 WSL distro, NOT the current 24.04 one.
  * `booster_robotics_sdk_python` installed in that distro (sudo ./install.sh in
    the SDK repo, then `pip install booster_robotics_sdk_python`).
  * Booster Studio running IN THE SAME distro with a K1 sim loaded and "playing",
    so the simulated controller is live on 127.0.0.1. (Same distro => Fast-DDS
    loopback/shared-memory just works. Studio on the Windows host will NOT be
    reachable at 127.0.0.1 from WSL — different network namespace.)

Run:
    python sdk_smoke_test.py                  # connects to 127.0.0.1
    BOOSTER_ROBOT_ADDR=192.168.10.102 python sdk_smoke_test.py   # real K1 instead
"""
from __future__ import annotations

import os
import time

# Address of the robot/sim DDS endpoint. 127.0.0.1 = local Booster Studio sim.
ADDR = os.environ.get("BOOSTER_ROBOT_ADDR", "127.0.0.1")


def main() -> None:
    try:
        from booster_robotics_sdk_python import (
            B1LocoClient, ChannelFactory, RobotMode, HandAction,
        )
    except ImportError as e:
        raise SystemExit(
            "booster_robotics_sdk_python not importable.\n"
            "  -> You are almost certainly on Ubuntu 24.04 (unsupported) or the SDK\n"
            "     isn't installed. Use an Ubuntu 22.04 distro and run the SDK's\n"
            "     install.sh, then `pip install booster_robotics_sdk_python`.\n"
            f"  Original error: {e}"
        )

    print(f"[smoke] connecting to DDS endpoint {ADDR} ...")
    ChannelFactory.Instance().Init(0, ADDR)        # domain 0, same as the sink
    client = B1LocoClient()
    client.Init()
    client.ChangeMode(RobotMode.kWalking)          # firmware/sim walk controller on
    print("[smoke] connected; mode=Walking. Sending motion ...")

    # Tiny scripted routine. Move(vx, vy, vyaw): x fwd (m/s), y left (m/s),
    # yaw CCW (rad/s). Send repeatedly — Move is a setpoint, not a one-shot.
    def hold(vx: float, vy: float, vyaw: float, secs: float, label: str) -> None:
        print(f"[smoke] {label}: Move({vx}, {vy}, {vyaw}) for {secs}s")
        t_end = time.monotonic() + secs
        while time.monotonic() < t_end:
            client.Move(float(vx), float(vy), float(vyaw))
            time.sleep(0.05)                       # ~20 Hz, matches the bridge

    try:
        hold(0.0, 0.0, 0.0, 1.0, "settle")
        hold(0.3, 0.0, 0.0, 2.0, "walk forward")
        hold(0.0, 0.0, 0.4, 2.0, "turn left in place")
        hold(0.0, 0.0, 0.0, 0.5, "pause")
        print("[smoke] WaveHand (greeting)")
        client.WaveHand(HandAction.kHandOpen)
        time.sleep(2.5)
    finally:
        print("[smoke] stop + damp")
        client.Move(0.0, 0.0, 0.0)
        client.ChangeMode(RobotMode.kDamping)      # safe hold
    print("[smoke] done.")


if __name__ == "__main__":
    main()
