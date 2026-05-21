"""In-memory room scroll broadcast (single-worker assumption on Render)."""

from __future__ import annotations

import asyncio
from datetime import datetime

_room_event = asyncio.Event()
_live_scroll_anchor: str | None = None
_live_scroll_updated_at: datetime | None = None
_state_seq: int = 0


def current_state_seq() -> int:
    return _state_seq


def get_live_scroll() -> tuple[str | None, datetime | None]:
    return _live_scroll_anchor, _live_scroll_updated_at


def set_live_scroll(anchor: str) -> None:
    global _live_scroll_anchor, _live_scroll_updated_at, _state_seq
    _live_scroll_anchor = anchor
    _live_scroll_updated_at = datetime.utcnow()
    _state_seq += 1
    _room_event.set()


def clear_live_scroll() -> None:
    global _live_scroll_anchor, _live_scroll_updated_at, _state_seq
    _live_scroll_anchor = None
    _live_scroll_updated_at = None
    _state_seq += 1
    _room_event.set()


def notify_room_song_change() -> None:
    global _state_seq
    _state_seq += 1
    _room_event.set()


async def wait_room_change(timeout: float = 15.0) -> None:
    _room_event.clear()
    try:
        await asyncio.wait_for(_room_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
