"""PKCE (RFC 7636) and authorize-URL helpers. Standard library only."""
from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def new_code_verifier() -> str:
    """A 43-character URL-safe verifier from 32 random bytes."""
    return _b64url(secrets.token_bytes(32))


def code_challenge(verifier: str) -> str:
    """The S256 challenge for a verifier."""
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def new_state() -> str:
    return secrets.token_urlsafe(16)


def authorize_url(
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    challenge: str,
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{authorization_endpoint}?{query}"
