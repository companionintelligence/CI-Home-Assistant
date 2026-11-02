"""Commands the Companion Hub may send to Home Assistant.

Pure validation lives here so it can be tested without Home Assistant. Only
the domains in the integration's allowlist can be called, and the caller
authenticates with the command token in the HTTP view.
"""
from __future__ import annotations

from typing import Any

COMMANDS = ("list_entities", "get_state", "call_service")


def validate(payload: Any, allowed_domains: list[str]) -> str | None:
    """Return an error message for an invalid command, or None if it is valid."""
    if not isinstance(payload, dict):
        return "body must be a JSON object"
    command = payload.get("command")
    if command not in COMMANDS:
        return f"command must be one of {', '.join(COMMANDS)}"
    if command == "get_state":
        if not _entity_id(payload.get("entity_id")):
            return "entity_id must look like domain.object_id"
    if command == "call_service":
        domain = payload.get("domain")
        service = payload.get("service")
        if domain not in allowed_domains:
            return f"domain {domain!r} is not allowed"
        if not isinstance(service, str) or not service.replace("_", "").isalnum():
            return "service must be a plain service name"
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return "data must be an object"
    return None


def _entity_id(value: Any) -> bool:
    return isinstance(value, str) and value.count(".") == 1 and " " not in value


async def execute(hass: Any, payload: dict, allowed_domains: list[str]) -> dict:
    """Run a validated command against Home Assistant's state and services."""
    command = payload["command"]
    if command == "list_entities":
        return {
            "entities": [
                {"entity_id": s.entity_id, "state": s.state, "name": s.name}
                for s in hass.states.async_all()
                if s.entity_id.split(".", 1)[0] in allowed_domains
            ]
        }
    if command == "get_state":
        state = hass.states.get(payload["entity_id"])
        if state is None:
            return {"entity_id": payload["entity_id"], "state": None}
        return {"entity_id": state.entity_id, "state": state.state, "attributes": dict(state.attributes)}
    await hass.services.async_call(
        payload["domain"],
        payload["service"],
        payload.get("data", {}),
        blocking=True,
    )
    return {"ok": True}
