"""Home Assistant state changes forwarded to Companion Memory as turns."""
import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.companion_voice import memory
from custom_components.companion_voice.const import (
    CONF_MEMORY_API_KEY,
    CONF_MEMORY_URL,
    CONF_WATCHED_ENTITIES,
    DOMAIN,
)

MEMORY_TURN = "https://memory.example.com/api/memory/turn"


def add_memory_entry(hass, watched=("light.kitchen",), memory_url="https://memory.example.com/api/", key="memory-key"):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MEMORY_URL: memory_url, CONF_MEMORY_API_KEY: key},
        options={CONF_WATCHED_ENTITIES: list(watched)},
        title="owner@example.com",
    )
    entry.add_to_hass(hass)
    return entry


async def start(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_a_watched_entity_change_is_saved_as_a_turn(hass, aioclient_mock):
    aioclient_mock.post(MEMORY_TURN, json={"created": 1, "skipped": 0})
    entry = add_memory_entry(hass)
    await start(hass, entry)

    hass.states.async_set("light.kitchen", "on", {"friendly_name": "Kitchen light"})
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    method, url, body, headers = aioclient_mock.mock_calls[0]
    assert method == "POST"
    assert str(url) == MEMORY_TURN
    assert headers["x-api-key"] == "memory-key"
    assert body["platform"] == "home-assistant"
    assert body["sessionId"] == f"ha-{entry.entry_id}"
    assert body["messages"] == [
        {"role": "user", "content": "Home Assistant: Kitchen light (light.kitchen) changed from unknown to on."}
    ]


async def test_changes_to_other_entities_are_not_saved(hass, aioclient_mock):
    aioclient_mock.post(MEMORY_TURN, json={"created": 1, "skipped": 0})
    await start(hass, add_memory_entry(hass))

    hass.states.async_set("switch.lamp", "on")
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls == []


async def test_nothing_is_saved_without_a_memory_key(hass, aioclient_mock):
    aioclient_mock.post(MEMORY_TURN, json={"created": 1, "skipped": 0})
    await start(hass, add_memory_entry(hass, key=""))

    hass.states.async_set("light.kitchen", "on")
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls == []


async def test_nothing_is_saved_without_a_memory_url(hass, aioclient_mock):
    aioclient_mock.post(MEMORY_TURN, json={"created": 1, "skipped": 0})
    await start(hass, add_memory_entry(hass, memory_url=""))

    hass.states.async_set("light.kitchen", "on")
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls == []


async def test_removing_an_entity_is_not_saved(hass, aioclient_mock):
    aioclient_mock.post(MEMORY_TURN, json={"created": 1, "skipped": 0})
    await start(hass, add_memory_entry(hass))
    hass.states.async_set("light.kitchen", "on")
    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 1

    hass.states.async_remove("light.kitchen")
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1


async def test_unloading_the_entry_stops_forwarding(hass, aioclient_mock):
    aioclient_mock.post(MEMORY_TURN, json={"created": 1, "skipped": 0})
    entry = add_memory_entry(hass)
    await start(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("light.kitchen", "on")
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls == []


async def test_changing_the_watched_entities_reloads_the_entry(hass, aioclient_mock):
    aioclient_mock.post(MEMORY_TURN, json={"created": 1, "skipped": 0})
    entry = add_memory_entry(hass)
    await start(hass, entry)

    hass.config_entries.async_update_entry(entry, options={CONF_WATCHED_ENTITIES: ["switch.lamp"]})
    await hass.async_block_till_done()

    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("switch.lamp", "on")
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2]["messages"][0]["content"].endswith("(switch.lamp) changed from unknown to on.")


async def test_a_failed_save_is_logged_and_not_raised(hass, aioclient_mock, caplog):
    aioclient_mock.post(MEMORY_TURN, status=500)
    await start(hass, add_memory_entry(hass))

    hass.states.async_set("light.kitchen", "on")
    await hass.async_block_till_done()

    assert "returned HTTP 500" in caplog.text


async def test_an_unreachable_memory_is_logged_and_not_raised(hass, aioclient_mock, caplog):
    aioclient_mock.post(MEMORY_TURN, exc=aiohttp.ClientConnectionError("memory is down"))
    await start(hass, add_memory_entry(hass))

    hass.states.async_set("light.kitchen", "on")
    await hass.async_block_till_done()

    assert "save failed" in caplog.text


def test_turn_payload_limits_the_text_and_the_session_id():
    payload = memory.turn_payload("x" * 5000, "s" * 500)
    assert len(payload["messages"][0]["content"]) == 4000
    assert len(payload["sessionId"]) == 200
    assert payload["platform"] == "home-assistant"


@pytest.mark.parametrize("text", ["short"])
def test_turn_payload_keeps_short_text(text):
    assert memory.turn_payload(text, "session")["messages"][0]["content"] == text
