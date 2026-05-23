"""In-memory favorites change broadcast (single-worker assumption on Render)."""

from __future__ import annotations

import asyncio

_favorites_event = asyncio.Event()
_favorites_seq: int = 0


def current_favorites_seq() -> int:
    return _favorites_seq


def notify_favorites_change() -> None:
    global _favorites_seq
    _favorites_seq += 1
    _favorites_event.set()


async def wait_favorites_change(timeout: float = 15.0) -> None:
    _favorites_event.clear()
    try:
        await asyncio.wait_for(_favorites_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
