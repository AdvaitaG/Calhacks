"""Shared helpers for the Baymax robot-side processes.

Mirrors the helpers in the LiveKit embodied-ai-hackathon reference repo
(mint_token / pace / env loading) so robot.py reads the same way as the
official examples.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import time
from datetime import timedelta

from dotenv import load_dotenv
from livekit import api


def load_env() -> None:
    """Load .env then .env.local (local overrides) from this dir or its parent."""
    here = pathlib.Path(__file__).resolve().parent
    for directory in (here, here.parent):
        for name in (".env", ".env.local"):
            path = directory / name
            if path.exists():
                load_dotenv(path, override=name.endswith(".local"))


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required env var {name!r} — see .env.example")
    return value


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def mint_token(identity: str, room: str, ttl: timedelta = timedelta(hours=6)) -> str:
    """Mint a LiveKit JWT for `identity` scoped to `room`."""
    key = required_env("LIVEKIT_API_KEY")
    secret = required_env("LIVEKIT_API_SECRET")
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
        can_update_own_metadata=True,
    )
    return (
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(grants)
        .with_ttl(ttl)
        .to_jwt()
    )


async def pace(fps: int):
    """Async generator that yields a tick index at a steady `fps`."""
    period = 1.0 / fps
    start = time.perf_counter()
    n = 0
    while True:
        yield n
        n += 1
        delay = (start + n * period) - time.perf_counter()
        if delay > 0:
            await asyncio.sleep(delay)
