"""Baymax return path (HOUR 2) — Band FINAL_COMMAND -> robot velocity.

Consumes FINAL_COMMAND messages (from Eshwar's Conductor, via Band), arbitrates
priority (EMERGENCY_STOP / REFLEX always wins when commands race), enforces a
2-second no-command STOP failsafe, maps the command to a {vx, vy, vyaw} velocity,
and drives the robot through B1LocoClient.

Runs end-to-end on a laptop TODAY with mocks:

    cd robot && python command_bridge.py        # scripted mock demo

Two swaps for live integration (tracked in ../DEPENDENCIES_FROM_ESHWAR.md):
  1. command source : MockCommandSource  -> BandCommandSource   (needs deps #1-4)
  2. motion sink     : B1LocoClientStub   -> real B1LocoClient    (needs SDK / K1)
Everything in between — parsing, arbitration, failsafe, velocity map — is final
and unit-testable, so flipping to live is a small, low-risk change.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, Tuple

logger = logging.getLogger("command_bridge")

# --- tunables ------------------------------------------------------------- #

Velocity = Tuple[float, float, float]  # (vx, vy, vyaw)
STOP: Velocity = (0.0, 0.0, 0.0)

# Placeholder velocities — tune against the K1 sim (MuJoCo/Isaac) before hardware.
# Source: ADIL_READ_THIS.md COMMAND_MAP.
COMMAND_MAP: dict[str, Velocity] = {
    "GUIDE_LEFT":     (0.2, 0.0,  0.3),
    "GUIDE_RIGHT":    (0.2, 0.0, -0.3),
    "MOVE_FORWARD":   (0.3, 0.0,  0.0),
    "SLOW_DOWN":      (0.1, 0.0,  0.0),
    "STOP":           STOP,
    "EMERGENCY_STOP": STOP,
}

REFLEX_WINDOW_S = 0.20   # if a CORTICAL command lands within this of a REFLEX, REFLEX wins
COMMAND_TIMEOUT_S = 2.0  # no fresh command for this long -> STOP (ADIL_READ_THIS.md:79)
TICK_HZ = 20             # control loop rate


# --- command model -------------------------------------------------------- #

@dataclass
class Command:
    command: str
    path: str = "CORTICAL"            # CORTICAL | REFLEX
    pace_ms: int = 500
    gait_action: Optional[str] = None
    # contract has a single arm_action; conductor.py emits split fields. Accept both.
    left_arm_action: Optional[str] = None
    right_arm_action: Optional[str] = None
    free_arm_action: Optional[str] = None
    reason: str = ""
    recv_mono: float = field(default_factory=time.monotonic)

    @property
    def is_emergency(self) -> bool:
        return self.path == "REFLEX" or self.command == "EMERGENCY_STOP"


def parse_final_command(raw: str) -> Optional[Command]:
    """Tolerant parse: accepts raw JSON or a tagged '[FINAL_COMMAND] {json}' string,
    and either the contract's `arm_action` or the code's left/right/free split."""
    text = raw.strip()
    # strip an optional leading tag like "[FINAL_COMMAND]" or "FINAL_COMMAND:"
    if text.startswith("["):
        text = text.split("]", 1)[-1].strip()
    elif text.upper().startswith("FINAL_COMMAND"):
        text = text.split(":", 1)[-1].strip() if ":" in text else text

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[bridge] could not parse command: %r", raw[:120])
        return None

    if data.get("type") not in (None, "FINAL_COMMAND"):
        return None
    cmd = data.get("command")
    if cmd not in COMMAND_MAP:
        logger.warning("[bridge] unknown command %r — ignoring", cmd)
        return None

    single_arm = data.get("arm_action")  # contract form
    return Command(
        command=cmd,
        path=data.get("path", "CORTICAL"),
        pace_ms=int(data.get("pace_ms", 500)),
        gait_action=data.get("gait_action"),
        left_arm_action=data.get("left_arm_action", single_arm),
        right_arm_action=data.get("right_arm_action", single_arm),
        free_arm_action=data.get("free_arm_action"),
        reason=data.get("reason", ""),
    )


# --- arbitration ---------------------------------------------------------- #

class CommandArbiter:
    """Holds the active command; enforces 'REFLEX wins on a close race'."""

    def __init__(self) -> None:
        self.active: Optional[Command] = None

    def submit(self, cmd: Command) -> str:
        prev = self.active
        if cmd.is_emergency:
            self.active = cmd
            return "accepted (reflex/emergency)"
        if prev is not None and prev.is_emergency and \
                (cmd.recv_mono - prev.recv_mono) < REFLEX_WINDOW_S:
            return "REJECTED (reflex still wins the race)"
        self.active = cmd
        return "accepted"

    def decide(self, now: float) -> Tuple[Velocity, str]:
        if self.active is None:
            return STOP, "idle-stop"
        age = now - self.active.recv_mono
        if age > COMMAND_TIMEOUT_S:
            return STOP, "timeout-stop"   # stable label so the tick loop logs once
        return COMMAND_MAP[self.active.command], self.active.command


# --- motion sink (last hop) ----------------------------------------------- #

class B1LocoClientStub:
    """Stand-in for booster_robotics_sdk.B1LocoClient. Swap for the real SDK on
    the K1 / Jetson (see ADIL_READ_THIS.md:244). Logs instead of moving."""

    def __init__(self) -> None:
        self._last: Optional[Velocity] = None

    def Move(self, vx: float, vy: float, vyaw: float) -> None:  # noqa: N802 (SDK name)
        vel = (vx, vy, vyaw)
        if vel != self._last:  # only log transitions to keep output readable
            logger.info("[K1] Move(vx=%.2f, vy=%.2f, vyaw=%.2f)", vx, vy, vyaw)
            self._last = vel

    def damp(self) -> None:
        logger.info("[K1] damping mode (emergency hold)")


# --- command sources ------------------------------------------------------ #

async def mock_command_source() -> AsyncIterator[str]:
    """Scripted FINAL_COMMANDs that exercise every behavior, no Band needed."""

    def mk(command: str, path: str = "CORTICAL", tag: bool = True) -> str:
        body = json.dumps({
            "type": "FINAL_COMMAND", "command": command, "path": path,
            "gait_action": "WALK_NORMAL", "left_arm_action": "HOLD_STEADY",
            "right_arm_action": "HOLD_STEADY", "free_arm_action": "SWEEP",
            "pace_ms": 500, "reason": f"mock {command}",
        })
        return f"[FINAL_COMMAND] {body}" if tag else body

    yield mk("MOVE_FORWARD");                 await asyncio.sleep(1.5)
    yield mk("GUIDE_LEFT");                   await asyncio.sleep(1.5)
    # race: a CORTICAL then a REFLEX 100ms later -> REFLEX must win
    yield mk("MOVE_FORWARD");                 await asyncio.sleep(0.1)
    yield mk("EMERGENCY_STOP", path="REFLEX")
    # a trailing CORTICAL 100ms after the reflex -> rejected (inside window)
    await asyncio.sleep(0.1)
    yield mk("MOVE_FORWARD");                 await asyncio.sleep(1.5)
    # clear the emergency far from the reflex -> accepted, resumes
    yield mk("SLOW_DOWN")
    # then go silent -> 2s failsafe STOP kicks in
    await asyncio.sleep(4.0)


# Band wire constants (mirror agents/shared/config.py).
WS_URL = "wss://app.band.ai/api/v1/socket/websocket"
REST_URL = "https://app.band.ai"


async def band_command_source() -> AsyncIterator[str]:
    """LIVE source: subscribe to the Band room(s) and yield raw message content
    for anything containing FINAL_COMMAND. Mirrors the BandLink pattern in
    agents/vision_agent.py. We filter on content only (parse_final_command
    validates the rest), so this accepts CORTICAL and REFLEX commands no matter
    which agent posts them — robust to the open questions in
    ../DEPENDENCIES_FROM_ESHWAR.md #2-4. Needs RobotID/RobotBandAPI (dep #1)."""
    from band.platform.link import BandLink
    from band.platform.event import MessageEvent, RoomAddedEvent
    from band.client.rest import DEFAULT_REQUEST_OPTIONS

    agent_id = os.environ["RobotID"]
    link = BandLink(agent_id=agent_id, api_key=os.environ["RobotBandAPI"],
                    ws_url=WS_URL, rest_url=REST_URL)
    await link.connect()
    logger.info("[bridge] connected to Band as RobotID; discovering rooms ...")

    try:
        resp = await link.rest.agent_api_chats.list_agent_chats(
            request_options=DEFAULT_REQUEST_OPTIONS)
        rooms = resp.data or []
    except Exception as e:  # noqa: BLE001 — log and keep waiting for invites
        logger.warning("[bridge] could not list rooms: %s", e)
        rooms = []
    for r in rooms:
        await link.subscribe_room(r.id)
        logger.info("[bridge] subscribed to room %s", r.id)
    await link.subscribe_agent_rooms(agent_id)
    if not rooms:
        logger.info("[bridge] no existing rooms — waiting for invite ...")

    async for event in link:
        if isinstance(event, RoomAddedEvent) and event.room_id:
            await link.subscribe_room(event.room_id)
            logger.info("[bridge] joined new room %s", event.room_id)
        elif isinstance(event, MessageEvent) and event.payload:
            content = event.payload.content or ""
            if "FINAL_COMMAND" in content:
                who = event.payload.sender_name or event.payload.sender_id
                logger.info("[bridge] FINAL_COMMAND received from %s", who)
                yield content


# --- run loop ------------------------------------------------------------- #

async def run(source: AsyncIterator[str], client: B1LocoClientStub) -> None:
    arbiter = CommandArbiter()

    async def consume() -> None:
        async for raw in source:
            cmd = parse_final_command(raw)
            if cmd is None:
                continue
            status = arbiter.submit(cmd)
            logger.info("[bridge] %-14s path=%-8s -> %s",
                        cmd.command, cmd.path, status)

    async def control_tick() -> None:
        period = 1.0 / TICK_HZ
        last_state = None
        while True:
            (vx, vy, vyaw), state = arbiter.decide(time.monotonic())
            if state != last_state:
                logger.info("[bridge] applying: %s", state)
                # damp once on entering an emergency hold, not every tick
                if (vx, vy, vyaw) == STOP and arbiter.active and arbiter.active.is_emergency:
                    client.damp()
                last_state = state
            client.Move(vx, vy, vyaw)
            await asyncio.sleep(period)

    consumer = asyncio.create_task(consume())
    ticker = asyncio.create_task(control_tick())
    await consumer            # mock source ends -> stop the demo
    await asyncio.sleep(0.3)  # let the failsafe STOP register
    ticker.cancel()


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    mode = sys.argv[1] if len(sys.argv) > 1 else "mock"

    if mode == "band":
        from _common import load_env  # loads .env from robot/ or repo root
        load_env()
        logger.info("[bridge] HOUR-2 return path — LIVE Band source, stubbed K1")
        asyncio.run(run(band_command_source(), B1LocoClientStub()))
    else:
        logger.info("[bridge] HOUR-2 return path — MOCK mode (no Band, stubbed K1)")
        asyncio.run(run(mock_command_source(), B1LocoClientStub()))
        logger.info("[bridge] demo complete")


if __name__ == "__main__":
    main()
