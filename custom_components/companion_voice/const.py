"""Constants for the Companion Voice integration."""

DOMAIN = "companion_voice"

CONF_HUB_URL = "hub_url"
CONF_MEMORY_URL = "memory_url"
CONF_MEMORY_API_KEY = "memory_api_key"
CONF_PORTAL_URL = "portal_url"
CONF_OIDC_CLIENT_ID = "oidc_client_id"
CONF_COMMAND_TOKEN = "command_token"
CONF_PORTAL_SUBJECT = "portal_subject"
CONF_PORTAL_EMAIL = "portal_email"
CONF_WATCHED_ENTITIES = "watched_entities"
CONF_ALLOWED_DOMAINS = "allowed_domains"

DEFAULT_PORTAL_URL = "https://hub.ci.computer"
DEFAULT_OIDC_CLIENT_ID = "ci-home-assistant"
OIDC_SCOPES = "openid profile email"

DEFAULT_ALLOWED_DOMAINS = [
    "light",
    "switch",
    "fan",
    "cover",
    "climate",
    "media_player",
    "scene",
    "script",
]

OAUTH_CALLBACK_PATH = "/api/companion_voice/oauth/callback"
COMMAND_PATH = "/api/companion_voice/command"

MEMORY_PLATFORM = "home-assistant"
