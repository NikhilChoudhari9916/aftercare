from functools import lru_cache
from typing import Any, Protocol

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import Request, Response

from app.config import Settings, get_settings

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


class LoginFailed(Exception):
    """The sign-in could not be completed (bad state, bad token, user cancelled)."""


class IdentityProvider(Protocol):
    """What the routes need from a sign-in provider. Tests replace it with a fake."""

    async def start_login(self, request: Request, redirect_uri: str) -> Response: ...

    async def finish_login(self, request: Request) -> dict[str, Any]: ...


class GoogleProvider:
    def __init__(self, settings: Settings) -> None:
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=GOOGLE_DISCOVERY_URL,
            client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
        )
        self._client = oauth.google

    async def start_login(self, request: Request, redirect_uri: str) -> Response:
        # Authlib adds the state, the nonce, and the PKCE challenge, and keeps them
        # in the short-lived login cookie until the callback.
        return await self._client.authorize_redirect(request, redirect_uri)

    async def finish_login(self, request: Request) -> dict[str, Any]:
        try:
            token = await self._client.authorize_access_token(request)
        except OAuthError as error:
            raise LoginFailed(type(error).__name__) from error
        claims = token.get("userinfo")
        if not claims:
            raise LoginFailed("no identity claims")
        return dict(claims)


@lru_cache
def _build_google_provider(settings: Settings) -> GoogleProvider:
    return GoogleProvider(settings)


def get_identity_provider() -> IdentityProvider:
    return _build_google_provider(get_settings())
