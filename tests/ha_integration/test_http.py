"""HTTP views: the sign-in callback page and the Companion Hub command endpoint."""
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.companion_voice.const import (
    COMMAND_PATH,
    CONF_ALLOWED_DOMAINS,
    CONF_COMMAND_TOKEN,
    CONF_HUB_URL,
    DOMAIN,
    OAUTH_CALLBACK_PATH,
)

TOKEN = "command-token-for-tests"
COMMAND_HEADERS = {"Authorization": f"Bearer {TOKEN}"}


async def setup_views(hass):
    assert await async_setup_component(hass, "http", {"http": {}})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


def add_hub_entry(hass, allowed=("light", "switch")):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HUB_URL: "https://hub.example.com",
            CONF_COMMAND_TOKEN: TOKEN,
            CONF_ALLOWED_DOMAINS: list(allowed),
        },
        options={},
        title="owner@example.com",
    )
    entry.add_to_hass(hass)
    return entry


async def test_callback_page_shows_the_code_to_copy(hass, hass_client_no_auth):
    await setup_views(hass)
    client = await hass_client_no_auth()
    resp = await client.get(f"{OAUTH_CALLBACK_PATH}?code=abc123&state=xyz")
    assert resp.status == 200
    body = await resp.text()
    assert "<pre>abc123</pre>" in body
    assert "State: <code>xyz</code>" in body


async def test_callback_page_escapes_what_it_shows(hass, hass_client_no_auth):
    await setup_views(hass)
    client = await hass_client_no_auth()
    resp = await client.get(f"{OAUTH_CALLBACK_PATH}?code=a%26b%22c&state=x")
    body = await resp.text()
    assert "<pre>a&amp;b&quot;c</pre>" in body


async def test_callback_page_reports_a_refused_sign_in(hass, hass_client_no_auth):
    await setup_views(hass)
    client = await hass_client_no_auth()
    resp = await client.get(f"{OAUTH_CALLBACK_PATH}?error=access_denied&error_description=User%20refused")
    body = await resp.text()
    assert "Sign-in was not completed: User refused" in body
    assert "<pre>" not in body


async def test_command_needs_the_command_token(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    client = await hass_client_no_auth()
    resp = await client.post(COMMAND_PATH, json={"command": "list_entities"})
    assert resp.status == 401
    resp = await client.post(
        COMMAND_PATH, json={"command": "list_entities"}, headers={"Authorization": "Bearer wrong"}
    )
    assert resp.status == 401


async def test_command_rejects_a_body_that_is_not_json(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    client = await hass_client_no_auth()
    resp = await client.post(COMMAND_PATH, data="not json", headers=COMMAND_HEADERS)
    assert resp.status == 400
    assert await resp.json() == {"error": "body must be JSON"}


async def test_command_rejects_an_unknown_command(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    client = await hass_client_no_auth()
    resp = await client.post(COMMAND_PATH, json={"command": "restart"}, headers=COMMAND_HEADERS)
    assert resp.status == 400


async def test_list_entities_returns_only_allowed_domains(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    hass.states.async_set("light.kitchen", "on", {"friendly_name": "Kitchen light"})
    hass.states.async_set("lock.front_door", "locked")
    client = await hass_client_no_auth()
    resp = await client.post(COMMAND_PATH, json={"command": "list_entities"}, headers=COMMAND_HEADERS)
    assert resp.status == 200
    entities = (await resp.json())["entities"]
    assert [entity["entity_id"] for entity in entities] == ["light.kitchen"]
    assert entities[0]["name"] == "Kitchen light"


async def test_get_state_returns_the_state_and_attributes(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    hass.states.async_set("light.kitchen", "on", {"brightness": 200})
    client = await hass_client_no_auth()
    resp = await client.post(
        COMMAND_PATH,
        json={"command": "get_state", "entity_id": "light.kitchen"},
        headers=COMMAND_HEADERS,
    )
    assert resp.status == 200
    assert await resp.json() == {
        "entity_id": "light.kitchen",
        "state": "on",
        "attributes": {"brightness": 200},
    }


async def test_call_service_runs_an_allowed_service(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    calls = []

    async def record(call):
        calls.append(call)

    hass.services.async_register("switch", "test_service", record)
    client = await hass_client_no_auth()
    resp = await client.post(
        COMMAND_PATH,
        json={
            "command": "call_service",
            "domain": "switch",
            "service": "test_service",
            "data": {"entity_id": "switch.lamp"},
        },
        headers=COMMAND_HEADERS,
    )
    assert resp.status == 200
    assert await resp.json() == {"ok": True}
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "switch.lamp"}


async def test_call_service_refuses_a_domain_outside_the_allowlist(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    calls = []

    async def record(call):
        calls.append(call)

    hass.services.async_register("lock", "unlock", record)
    client = await hass_client_no_auth()
    resp = await client.post(
        COMMAND_PATH,
        json={"command": "call_service", "domain": "lock", "service": "unlock"},
        headers=COMMAND_HEADERS,
    )
    assert resp.status == 400
    assert "not allowed" in (await resp.json())["error"]
    assert calls == []


async def test_get_state_for_an_unknown_entity_has_no_state(hass, hass_client_no_auth):
    await setup_views(hass)
    add_hub_entry(hass)
    client = await hass_client_no_auth()
    resp = await client.post(
        COMMAND_PATH,
        json={"command": "get_state", "entity_id": "light.missing"},
        headers=COMMAND_HEADERS,
    )
    assert resp.status == 200
    assert await resp.json() == {"entity_id": "light.missing", "state": None}
