"""CI-Portal OIDC client: the error paths the flow tests do not reach directly."""
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.companion_voice import oidc
from custom_components.companion_voice.const import DEFAULT_PORTAL_URL

PORTAL = DEFAULT_PORTAL_URL
DISCOVERY = f"{PORTAL}/api/auth/.well-known/openid-configuration"
TOKEN = f"{PORTAL}/api/auth/oauth2/token"
USERINFO = f"{PORTAL}/api/auth/oauth2/userinfo"
ENDPOINTS = {
    "authorization_endpoint": f"{PORTAL}/api/auth/oauth2/authorize",
    "token_endpoint": TOKEN,
    "userinfo_endpoint": USERINFO,
}


async def test_discovery_returns_the_document(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json=ENDPOINTS)
    meta = await oidc.discover(async_get_clientsession(hass), PORTAL)
    assert meta["token_endpoint"] == TOKEN


async def test_discovery_reports_an_http_error(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, status=503)
    with pytest.raises(oidc.OIDCError, match="HTTP 503"):
        await oidc.discover(async_get_clientsession(hass), PORTAL)


async def test_discovery_must_name_every_endpoint(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json={"authorization_endpoint": ENDPOINTS["authorization_endpoint"]})
    with pytest.raises(oidc.OIDCError, match="token_endpoint, userinfo_endpoint"):
        await oidc.discover(async_get_clientsession(hass), PORTAL)


async def test_discovery_must_be_a_json_object(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY, json=["not", "an", "object"])
    with pytest.raises(oidc.OIDCError, match="not a JSON object"):
        await oidc.discover(async_get_clientsession(hass), PORTAL)


async def test_token_exchange_passes_on_the_portal_error(hass, aioclient_mock):
    aioclient_mock.post(TOKEN, status=400, json={"error_description": "code expired"})
    with pytest.raises(oidc.OIDCError, match="code expired"):
        await oidc.exchange_code(
            async_get_clientsession(hass), TOKEN, "ci-home-assistant", "http://ha/callback", "code", "verifier"
        )


async def test_userinfo_sends_the_bearer_token_and_returns_the_claims(hass, aioclient_mock):
    aioclient_mock.get(USERINFO, json={"sub": "user-1"})
    claims = await oidc.userinfo(async_get_clientsession(hass), USERINFO, "portal-access-token")
    assert claims == {"sub": "user-1"}
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["Authorization"] == "Bearer portal-access-token"


async def test_userinfo_reports_an_http_error(hass, aioclient_mock):
    aioclient_mock.get(USERINFO, status=401)
    with pytest.raises(oidc.OIDCError, match="HTTP 401"):
        await oidc.userinfo(async_get_clientsession(hass), USERINFO, "portal-access-token")
