"""Minimal Booster SDK smoke test — proves B1LocoClient can drive a SIM.

Standalone (no Band, no agents, no LiveKit): just the SDK, so you can confirm the
DDS link + locomotion presets work before wiring anything else in. Mirrors the
sequence in Booster's own b1_loco_example_client:

    mp  -> ChangeMode(kPrepare)   # robot stands up  (REQUIRED before walking)
    mw  -> ChangeMode(kWalking)
    w/q -> Move(...)              # forward / turn
    wh  -> WaveHand

Skipping kPrepare and calling Move directly fails with "API call failed,
code = 502" — the controller rejects motion until the robot has stood up.

PREREQUISITES:
  * Ubuntu 22.04 with booster_robotics_sdk_python installed (`SDK ok`).
  * A controller listening on 127.0.0.1 — e.g. the Webots sim with its control
    runner up (start the Webots world, then booster-runner-*.run), or the real
    robot / Booster Studio.

Run:
    python3 sdk_smoke_test.py                                  # 127.0.0.1
    BOOSTER_ROBOT_ADDR=192.168.10.102 python3 sdk_smoke_test.py   # real K1
"""
from __future__ import annotations

import os
import time

ADDR = os.environ.get("BOOSTER_ROBOT_ADDR", "127.0.0.1")

# Time for the robot to physically stand up after Prepare before it can walk.
PREPARE_SECS = float(os.environ.get("BOOSTER_PREPARE_SECS", "6"))


def main() -> None:
    try:
        from booster_robotics_sdk_python import (
            B1LocoClient, ChannelFactory, RobotMode, HandAction,
        )
    except ImportError as e:
        raise SystemExit(
            "booster_robotics_sdk_python not importable — are you on the Ubuntu\n"
            "22.04 distro where the SDK was installed? "
            f"Original error: {e}"
        )

    print(f"[smoke] connecting to DDS endpoint {ADDR} ...")
    ChannelFactory.Instance().Init(0, ADDR)
    client = B1LocoClient()
    client.Init()

    # --- bring the robot up: Prepare (stand) -> Walking. Skipping this is the
    #     cause of Move error 502. ---
    print("[smoke] ChangeMode(Prepare) — robot stands up ...")
    client.ChangeMode(RobotMode.kPrepare)
    print(f"[smoke]   waiting {PREPARE_SECS:.0f}s for the stand-up to finish ...")
    time.sleep(PREPARE_SECS)
    print("[smoke] ChangeMode(Walking) ...")
    client.ChangeMode(RobotMode.kWalking)
    time.sleep(2.0)
    print("[smoke] walking-ready. Sending motion ...")

    # Move(vx, vy, vyaw): x fwd (m/s), y left (m/s), yaw CCW (rad/s). Move is a
    # setpoint — resend at ~20 Hz for the duration. Magnitudes match the example.
    def hold(vx: float, vy: float, vyaw: float, secs: float, label: str) -> None:
        print(f"[smoke] {label}: Move({vx}, {vy}, {vyaw}) for {secs}s")
        t_end = time.monotonic() + secs
        while time.monotonic() < t_end:
            client.Move(float(vx), float(vy), float(vyaw))
            time.sleep(0.05)

    def ramp(vx: float, vyaw: float, up: float, steady: float, label: str) -> None:
        """Ease the gait in and out so abrupt setpoint jumps don't topple it."""
        print(f"[smoke] {label}: ramp->({vx}, 0, {vyaw}) hold {steady}s")
        n = max(1, int(up / 0.05))
        for i in range(n):                       # ease in
            k = (i + 1) / n
            client.Move(vx * k, 0.0, vyaw * k); time.sleep(0.05)
        t_end = time.monotonic() + steady        # steady
        while time.monotonic() < t_end:
            client.Move(vx, 0.0, vyaw); time.sleep(0.05)
        for i in range(n):                       # ease out
            k = (n - i - 1) / n
            client.Move(vx * k, 0.0, vyaw * k); time.sleep(0.05)

    try:
        hold(0.0, 0.0, 0.0, 1.5, "settle in place")
        ramp(0.10, 0.0, 1.0, 3.0, "walk forward (gentle)")
        hold(0.0, 0.0, 0.0, 1.5, "stand")
        ramp(0.0, 0.3, 1.0, 2.0, "turn left (gentle)")
        hold(0.0, 0.0, 0.0, 1.5, "stand")
        print("[smoke] WaveHand (greeting)")
        client.WaveHand(HandAction.kHandOpen)
        time.sleep(2.5)
    finally:
        print("[smoke] done -> Damping (safe hold)")
        client.Move(0.0, 0.0, 0.0)
        client.ChangeMode(RobotMode.kDamping)
    print("[smoke] OK")


if __name__ == "__main__":
    main()
