"""HTTP views: the OAuth callback page and the Companion Hub command endpoint."""
from __future__ import annotations

import hmac
import html
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .commands import execute, validate
from .const import COMMAND_PATH, CONF_ALLOWED_DOMAINS, CONF_COMMAND_TOKEN, DOMAIN, OAUTH_CALLBACK_PATH


class OAuthCallbackView(HomeAssistantView):
    """Shows the authorization code so it can be pasted into the setup flow."""

    url = OAUTH_CALLBACK_PATH
    name = "api:companion_voice:oauth_callback"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        code = request.query.get("code", "")
        state = request.query.get("state", "")
        error = request.query.get("error_description") or request.query.get("error", "")
        if error:
            body = f"<p>Sign-in was not completed: {html.escape(error)}</p>"
        else:
            body = (
                "<p>Copy this code and paste it into Home Assistant to finish setup:</p>"
                f"<pre>{html.escape(code)}</pre>"
                f"<p>State: <code>{html.escape(state)}</code></p>"
            )
        page = (
            "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Companion Voice sign-in</title>"
            "<body style='font-family:system-ui;margin:16px'>"
            f"<h1>Companion Voice</h1>{body}</body>"
        )
        return web.Response(text=page, content_type="text/html")


class CommandView(HomeAssistantView):
    """Accepts commands from Companion Hub, authenticated by the command token."""

    url = COMMAND_PATH
    name = "api:companion_voice:command"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def post(self, request: web.Request) -> web.Response:
        entry = _entry_for_token(self._hass, request.headers.get("Authorization", ""))
        if entry is None:
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            payload: Any = await request.json()
        except ValueError:
            return web.json_response({"error": "body must be JSON"}, status=400)

        allowed = entry.options.get(CONF_ALLOWED_DOMAINS) or entry.data.get(CONF_ALLOWED_DOMAINS, [])
        error = validate(payload, allowed)
        if error:
            return web.json_response({"error": error}, status=400)

        result = await execute(self._hass, payload, allowed)
        return web.json_response(result)


def _entry_for_token(hass: HomeAssistant, header: str) -> Any:
    """Return the config entry whose command token matches the bearer header."""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    for entry in hass.config_entries.async_entries(DOMAIN):
        expected = entry.data.get(CONF_COMMAND_TOKEN, "")
        if expected and hmac.compare_digest(expected, token):
            return entry
    return None
