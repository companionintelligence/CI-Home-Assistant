"""Config and options flow: the endpoints, the CI-Portal sign-in and the watched entities."""
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.companion_voice.const import (
    CONF_ALLOWED_DOMAINS,
    CONF_COMMAND_TOKEN,
    CONF_HUB_URL,
    CONF_MEMORY_API_KEY,
    CONF_MEMORY_URL,
    CONF_PORTAL_SUBJECT,
    CONF_WATCHED_ENTITIES,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_PORTAL_URL,
    DOMAIN,
)

PORTAL = DEFAULT_PORTAL_URL
DISCOVERY = f"{PORTAL}/api/auth/.well-known/openid-configuration"
TOKEN = f"{PORTAL}/api/auth/oauth2/token"
USERINFO = f"{PORTAL}/api/auth/oauth2/userinfo"
DISCOVERY_DOC = {
    "authorization_endpoint": f"{PORTAL}/api/auth/oauth2/authorize",
    "token_endpoint": TOKEN,
    "userinfo_endpoint": USERINFO,
}
REDIRECT_URI = "http://192.168.1.10:8123/api/companion_voice/oauth/callback"
USER_INPUT = {
    CONF_HUB_URL: "https://hub.example.com/",
    CONF_MEMORY_URL: "",
    CONF_MEMORY_API_KEY: "",
    CONF_WATCHED_ENTITIES: [],
}


async def start_flow(hass):
    hass.config.internal_url = "http://192.168.1.10:8123"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def submit_user_step(hass, user_input=USER_INPUT):
    result = await start_flow(hass)
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_user_step_asks_for_the_hub(hass):
    result = await start_flow(hass)
    assert result["errors"] == {}


async def test_hub_url_must_be_http_or_https(hass):
    result = await submit_user_step(hass, dict(USER_INPUT, **{CONF_HUB_URL: "ftp://hub.example.com"}))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HUB_URL: "invalid_url"}


async def test_memory_url_needs_a_key(hass):
    result = await submit_user_step(
        hass, dict(USER_INPUT, **{CONF_MEMORY_URL: "https://memory.example.com/api", CONF_MEMORY_API_KEY: ""})
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MEMORY_API_KEY: "memory_key_required"}


async def test_sign_in_step_shows_the_pkce_authorize_link(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json=DISCOVERY_DOC)
    result = await submit_user_step(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sign_in"
    placeholders = result["description_placeholders"]
    assert placeholders["authorize_url"].startswith(f"{PORTAL}/api/auth/oauth2/authorize?")
    assert "code_challenge_method=S256" in placeholders["authorize_url"]
    assert placeholders["redirect_uri"] == REDIRECT_URI
    assert len(placeholders["command_token"]) >= 40


async def test_completing_sign_in_creates_the_entry(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json=DISCOVERY_DOC)
    aioclient_mock.post(TOKEN, json={"access_token": "portal-access-token"})
    aioclient_mock.get(USERINFO, json={"sub": "user-1", "email": "owner@example.com"})
    result = await submit_user_step(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": " abc "})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "owner@example.com"
    assert result["data"][CONF_HUB_URL] == "https://hub.example.com"
    assert result["data"][CONF_PORTAL_SUBJECT] == "user-1"
    assert result["data"][CONF_ALLOWED_DOMAINS] == DEFAULT_ALLOWED_DOMAINS
    assert len(result["data"][CONF_COMMAND_TOKEN]) >= 40
    assert result["options"] == {CONF_WATCHED_ENTITIES: []}
    token_call = next(call for call in aioclient_mock.mock_calls if call[0] == "POST")
    assert token_call[2]["code"] == "abc"


async def test_entry_title_falls_back_when_the_portal_gives_no_email(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json=DISCOVERY_DOC)
    aioclient_mock.post(TOKEN, json={"access_token": "portal-access-token"})
    aioclient_mock.get(USERINFO, json={"sub": "user-2"})
    result = await submit_user_step(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "abc"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Companion Voice"


async def test_rejected_code_asks_for_a_new_one(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json=DISCOVERY_DOC)
    aioclient_mock.post(TOKEN, status=400, json={"error": "invalid_grant"})
    result = await submit_user_step(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "stale"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sign_in"
    assert result["errors"] == {"base": "sign_in_failed"}


async def test_userinfo_without_a_subject_is_rejected(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json=DISCOVERY_DOC)
    aioclient_mock.post(TOKEN, json={"access_token": "portal-access-token"})
    aioclient_mock.get(USERINFO, json={"email": "owner@example.com"})
    result = await submit_user_step(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "abc"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "sign_in_failed"}


async def test_options_flow_changes_the_watched_entities(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HUB_URL: "https://hub.example.com"},
        options={CONF_WATCHED_ENTITIES: []},
        title="owner@example.com",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WATCHED_ENTITIES: ["light.kitchen"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WATCHED_ENTITIES] == ["light.kitchen"]


async def test_unreachable_portal_is_reported_on_the_first_step(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, status=503)
    result = await submit_user_step(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_reach_portal"}


async def test_portal_without_its_endpoints_is_reported_on_the_first_step(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json={"issuer": PORTAL})
    result = await submit_user_step(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_reach_portal"}
