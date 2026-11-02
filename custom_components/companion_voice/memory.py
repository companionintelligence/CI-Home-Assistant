"""Companion Memory writes for Home Assistant events.

Each forwarded event is saved as a turn with POST /memory/turn, the same route
the Voice Bridge uses. The key must carry the `memory` scope.
"""
from __future__ import annotations

import logging

import aiohttp

from .const import MEMORY_PLATFORM

_LOGGER = logging.getLogger(__name__)


def turn_payload(text: str, session_id: str) -> dict:
    return {
        "messages": [{"role": "user", "content": text[:4000]}],
        "sessionId": session_id[:200],
        "platform": MEMORY_PLATFORM,
    }


async def save_event(
    session: aiohttp.ClientSession,
    memory_url: str,
    api_key: str,
    text: str,
    session_id: str,
) -> None:
    """Save one event. Failures are logged and never raised to Home Assistant."""
    url = f"{memory_url.rstrip('/')}/memory/turn"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    try:
        async with session.post(
            url, json=turn_payload(text, session_id), headers=headers, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status >= 300:
                _LOGGER.warning("Companion Memory turn save returned HTTP %s", resp.status)
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.warning("Companion Memory turn save failed: %s", err)
