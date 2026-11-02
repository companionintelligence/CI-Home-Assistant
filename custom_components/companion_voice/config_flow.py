"""Setup flow: Companion Hub and Memory URLs, then sign-in with CI-Portal (OIDC + PKCE)."""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.network import get_url
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from . import pkce
from .const import (
    CONF_ALLOWED_DOMAINS,
    CONF_COMMAND_TOKEN,
    CONF_HUB_URL,
    CONF_MEMORY_API_KEY,
    CONF_MEMORY_URL,
    CONF_OIDC_CLIENT_ID,
    CONF_PORTAL_EMAIL,
    CONF_PORTAL_SUBJECT,
    CONF_PORTAL_URL,
    CONF_WATCHED_ENTITIES,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_OIDC_CLIENT_ID,
    DEFAULT_PORTAL_URL,
    DOMAIN,
    OAUTH_CALLBACK_PATH,
    OIDC_SCOPES,
)
from .oidc import OIDCError, discover, exchange_code, userinfo


class CompanionVoiceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Collects the endpoints, then signs the user in with CI-Portal."""

    VERSION = 1

    def __init__(self) -> None:
        self._settings: dict[str, Any] = {}
        self._verifier = ""
        self._state = ""
        self._command_token = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_HUB_URL].startswith(("http://", "https://")):
                errors[CONF_HUB_URL] = "invalid_url"
            if user_input.get(CONF_MEMORY_URL) and not user_input[CONF_MEMORY_API_KEY]:
                errors[CONF_MEMORY_API_KEY] = "memory_key_required"
            if not errors:
                self._settings = user_input
                return await self.async_step_sign_in()

        schema = vol.Schema(
            {
                vol.Required(CONF_HUB_URL, default=user_input[CONF_HUB_URL] if user_input else ""): str,
                vol.Optional(CONF_PORTAL_URL, default=DEFAULT_PORTAL_URL): str,
                vol.Optional(CONF_OIDC_CLIENT_ID, default=DEFAULT_OIDC_CLIENT_ID): str,
                vol.Optional(CONF_MEMORY_URL, default=""): str,
                vol.Optional(CONF_MEMORY_API_KEY, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_WATCHED_ENTITIES, default=[]): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sign_in(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if not self._verifier:
            self._verifier = pkce.new_code_verifier()
            self._state = pkce.new_state()
            self._command_token = secrets.token_urlsafe(32)

        redirect_uri = f"{get_url(self.hass, allow_external=False)}{OAUTH_CALLBACK_PATH}"

        if user_input is not None:
            try:
                await self._complete_sign_in(user_input["code"].strip(), redirect_uri)
            except OIDCError:
                errors["base"] = "sign_in_failed"
            else:
                return self._create_entry()

        session = async_get_clientsession(self.hass)
        authorize = await self._authorize_url(redirect_uri, session)
        schema = vol.Schema({vol.Required("code"): str})
        return self.async_show_form(
            step_id="sign_in",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "authorize_url": authorize,
                "command_token": self._command_token,
                "redirect_uri": redirect_uri,
            },
        )

    async def _authorize_url(self, redirect_uri: str, session) -> str:
        meta = await discover(session, self._settings[CONF_PORTAL_URL])
        return pkce.authorize_url(
            meta["authorization_endpoint"],
            self._settings[CONF_OIDC_CLIENT_ID],
            redirect_uri,
            OIDC_SCOPES,
            self._state,
            pkce.code_challenge(self._verifier),
        )

    async def _complete_sign_in(self, code: str, redirect_uri: str) -> None:
        session = async_get_clientsession(self.hass)
        meta = await discover(session, self._settings[CONF_PORTAL_URL])
        tokens = await exchange_code(
            session,
            meta["token_endpoint"],
            self._settings[CONF_OIDC_CLIENT_ID],
            redirect_uri,
            code,
            self._verifier,
        )
        claims = await userinfo(session, meta["userinfo_endpoint"], tokens["access_token"])
        if not claims.get("sub"):
            raise OIDCError("userinfo had no subject")
        self._settings[CONF_PORTAL_SUBJECT] = claims["sub"]
        self._settings[CONF_PORTAL_EMAIL] = claims.get("email", "")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return CompanionVoiceOptionsFlow()

    def _create_entry(self):
        data = {
            CONF_HUB_URL: self._settings[CONF_HUB_URL].rstrip("/"),
            CONF_PORTAL_URL: self._settings[CONF_PORTAL_URL].rstrip("/"),
            CONF_OIDC_CLIENT_ID: self._settings[CONF_OIDC_CLIENT_ID],
            CONF_MEMORY_URL: self._settings.get(CONF_MEMORY_URL, "").rstrip("/"),
            CONF_MEMORY_API_KEY: self._settings.get(CONF_MEMORY_API_KEY, ""),
            CONF_COMMAND_TOKEN: self._command_token,
            CONF_PORTAL_SUBJECT: self._settings[CONF_PORTAL_SUBJECT],
            CONF_PORTAL_EMAIL: self._settings[CONF_PORTAL_EMAIL],
            CONF_ALLOWED_DOMAINS: DEFAULT_ALLOWED_DOMAINS,
        }
        options = {CONF_WATCHED_ENTITIES: self._settings.get(CONF_WATCHED_ENTITIES, [])}
        return self.async_create_entry(
            title=self._settings[CONF_PORTAL_EMAIL] or "Companion Voice",
            data=data,
            options=options,
        )


class CompanionVoiceOptionsFlow(config_entries.OptionsFlow):
    """Chooses which entities are forwarded to Companion Memory."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(CONF_WATCHED_ENTITIES, [])
        schema = vol.Schema(
            {
                vol.Optional(CONF_WATCHED_ENTITIES, default=current): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
