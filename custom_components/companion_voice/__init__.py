"""Companion Voice: Home Assistant integration for Companion Hub and Companion Memory.

Two directions:
- Home Assistant to Companion Memory: state changes of the watched entities
  are saved as turns (see memory.py).
- Companion Hub to Home Assistant: Hub sends commands to the command endpoint
  with the command token, limited to the allowed domains (see commands.py).
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MEMORY_API_KEY,
    CONF_MEMORY_URL,
    CONF_WATCHED_ENTITIES,
    DOMAIN,
)
from .http import CommandView, OAuthCallbackView
from .memory import save_event


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.http.register_view(OAuthCallbackView())
    hass.http.register_view(CommandView(hass))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    watched = set(entry.options.get(CONF_WATCHED_ENTITIES, []))
    memory_url = entry.data.get(CONF_MEMORY_URL, "")
    memory_key = entry.data.get(CONF_MEMORY_API_KEY, "")

    async def _forward_state(event: Event) -> None:
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if entity_id not in watched or new_state is None or not memory_url or not memory_key:
            return
        old_state = event.data.get("old_state")
        old_value = old_state.state if old_state else "unknown"
        text = (
            f"Home Assistant: {new_state.name or entity_id} ({entity_id}) changed "
            f"from {old_value} to {new_state.state}."
        )
        await save_event(
            async_get_clientsession(hass),
            memory_url,
            memory_key,
            text,
            session_id=f"ha-{entry.entry_id}",
        )

    entry.async_on_unload(hass.bus.async_listen(EVENT_STATE_CHANGED, _forward_state))
    entry.async_on_unload(entry.add_update_listener(_reload_on_update))
    return True


async def _reload_on_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True
