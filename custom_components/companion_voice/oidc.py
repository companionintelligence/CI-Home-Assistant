"""CI-Portal OIDC client: discovery, code exchange and userinfo.

CI-Portal is a Better-Auth OIDC provider. Clients are public and must use PKCE.
The redirect URI must be a private or localhost address, which is why the
callback is served by Home Assistant itself on its local URL.
"""
from __future__ import annotations

from typing import Any

import aiohttp


class OIDCError(Exception):
    """Sign-in with CI-Portal failed."""


async def discover(session: aiohttp.ClientSession, portal_url: str) -> dict[str, Any]:
    url = f"{portal_url.rstrip('/')}/api/auth/.well-known/openid-configuration"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise OIDCError(f"discovery returned HTTP {resp.status}")
        return await resp.json()


async def exchange_code(
    session: aiohttp.ClientSession,
    token_endpoint: str,
    client_id: str,
    redirect_uri: str,
    code: str,
    verifier: str,
) -> dict[str, Any]:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    async with session.post(token_endpoint, data=form) as resp:
        body = await resp.json(content_type=None)
        if resp.status != 200 or "access_token" not in body:
            raise OIDCError(body.get("error_description") or body.get("error") or "token exchange failed")
        return body


async def userinfo(
    session: aiohttp.ClientSession, userinfo_endpoint: str, access_token: str
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with session.get(userinfo_endpoint, headers=headers) as resp:
        if resp.status != 200:
            raise OIDCError(f"userinfo returned HTTP {resp.status}")
        return await resp.json()
