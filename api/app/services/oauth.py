import os
import time
from typing import Any, cast

import httpx
from database.pg.user_ops.user_crud import ProviderUserPayload
from fastapi import HTTPException, status
from jose import JWTError, jwt
from models.auth import OAuthLoginPayload, ProviderEnum

GOOGLE_OPENID_CONFIGURATION_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
GITHUB_ACCEPT_HEADER = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"
MERIDIAN_USER_AGENT = "Meridian OAuth"
PROVIDER_HTTP_TIMEOUT = 10.0

_google_openid_configuration_cache: dict[str, Any] | None = None
_google_openid_configuration_cache_expires_at = 0.0
_google_jwks_cache: dict[str, Any] | None = None
_google_jwks_cache_expires_at = 0.0


def _cache_ttl_seconds(headers: httpx.Headers, default: int = 300) -> int:
    cache_control = headers.get("Cache-Control", "")
    for directive in cache_control.split(","):
        directive = directive.strip().lower()
        if directive.startswith("max-age="):
            try:
                return max(int(directive.split("=", 1)[1]), 0)
            except ValueError:
                break
    return default


def _google_client_ids() -> list[str]:
    client_ids: list[str] = []
    for env_var in ("GOOGLE_CLIENT_ID", "NUXT_OAUTH_GOOGLE_CLIENT_ID"):
        raw_value = os.getenv(env_var, "")
        for client_id in (value.strip() for value in raw_value.split(",")):
            if client_id and client_id not in client_ids:
                client_ids.append(client_id)

    if not client_ids:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured on the server.",
        )

    return client_ids


def _github_oauth_client_credentials() -> tuple[str, str]:
    for client_id_env, client_secret_env in (
        ("NUXT_OAUTH_GITHUB_CLIENT_ID", "NUXT_OAUTH_GITHUB_CLIENT_SECRET"),
        ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"),
    ):
        client_id = os.getenv(client_id_env)
        client_secret = os.getenv(client_secret_env)
        if client_id and client_secret:
            return client_id, client_secret

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="GitHub OAuth is not configured on the server.",
    )


async def _get_google_openid_configuration(force_refresh: bool = False) -> dict[str, Any]:
    global _google_openid_configuration_cache
    global _google_openid_configuration_cache_expires_at

    now = time.time()
    if (
        not force_refresh
        and _google_openid_configuration_cache is not None
        and now < _google_openid_configuration_cache_expires_at
    ):
        return _google_openid_configuration_cache

    async with httpx.AsyncClient(timeout=PROVIDER_HTTP_TIMEOUT) as client:
        response = await client.get(GOOGLE_OPENID_CONFIGURATION_URL)

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve Google OpenID configuration.",
        )

    config = response.json()
    if not config.get("jwks_uri"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google OpenID configuration is missing a JWKS URI.",
        )

    _google_openid_configuration_cache = config
    _google_openid_configuration_cache_expires_at = now + _cache_ttl_seconds(response.headers)
    return cast(dict[str, Any], config)


async def _get_google_jwks(force_refresh: bool = False) -> dict[str, Any]:
    global _google_jwks_cache
    global _google_jwks_cache_expires_at

    now = time.time()
    if not force_refresh and _google_jwks_cache is not None and now < _google_jwks_cache_expires_at:
        return _google_jwks_cache

    openid_configuration = await _get_google_openid_configuration(force_refresh=force_refresh)
    jwks_uri = openid_configuration["jwks_uri"]

    async with httpx.AsyncClient(timeout=PROVIDER_HTTP_TIMEOUT) as client:
        response = await client.get(jwks_uri)

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve Google signing keys.",
        )

    jwks = response.json()
    if not jwks.get("keys"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google signing keys response is invalid.",
        )

    _google_jwks_cache = jwks
    _google_jwks_cache_expires_at = now + _cache_ttl_seconds(response.headers)
    return cast(dict[str, Any], jwks)


def _find_jwk(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
    return next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)


async def _verify_google_login(payload: OAuthLoginPayload) -> ProviderUserPayload:
    if not payload.id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth ID token is required.",
        )

    try:
        token_header = jwt.get_unverified_header(payload.id_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google OAuth token.",
        ) from exc

    key_id = token_header.get("kid")
    algorithm = token_header.get("alg")
    if not key_id or not algorithm:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google OAuth token.",
        )

    jwks = await _get_google_jwks()
    jwk = _find_jwk(jwks, key_id)
    if jwk is None:
        jwks = await _get_google_jwks(force_refresh=True)
        jwk = _find_jwk(jwks, key_id)

    if jwk is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google OAuth token.",
        )

    claims = None
    for client_id in _google_client_ids():
        try:
            claims = jwt.decode(
                payload.id_token,
                jwk,
                algorithms=[algorithm],
                audience=client_id,
                issuer=GOOGLE_ISSUERS,
                access_token=payload.access_token,
            )
            break
        except JWTError:
            continue

    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google OAuth token.",
        )

    provider_user_id = claims.get("sub")
    if not provider_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google OAuth token.",
        )

    return ProviderUserPayload(
        oauthId=str(provider_user_id),
        email=claims.get("email"),
        name=claims.get("name"),
        avatarUrl=claims.get("picture"),
    )


async def _get_github_primary_email(client: httpx.AsyncClient, access_token: str) -> str | None:
    response = await client.get(
        "https://api.github.com/user/emails",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": GITHUB_ACCEPT_HEADER,
            "User-Agent": MERIDIAN_USER_AGENT,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )

    if response.status_code != 200:
        return None

    emails = response.json()
    primary_verified_email = cast(
        str | None,
        next(
            (
                email_record.get("email")
                for email_record in emails
                if email_record.get("primary") and email_record.get("verified")
            ),
            None,
        ),
    )
    if primary_verified_email:
        return primary_verified_email

    return cast(
        str | None,
        next(
            (email_record.get("email") for email_record in emails if email_record.get("verified")),
            None,
        ),
    )


async def _verify_github_login(payload: OAuthLoginPayload) -> ProviderUserPayload:
    if not payload.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth access token is required.",
        )

    github_client_id, github_client_secret = _github_oauth_client_credentials()

    async with httpx.AsyncClient(timeout=PROVIDER_HTTP_TIMEOUT) as client:
        token_check_response = await client.post(
            f"https://api.github.com/applications/{github_client_id}/token",
            auth=(github_client_id, github_client_secret),
            headers={
                "Accept": GITHUB_ACCEPT_HEADER,
                "User-Agent": MERIDIAN_USER_AGENT,
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            },
            json={"access_token": payload.access_token},
        )

        if token_check_response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub OAuth token.",
            )

        if token_check_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to validate GitHub OAuth token.",
            )

        token_metadata = token_check_response.json()
        verified_user = token_metadata.get("user") or {}

        profile_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {payload.access_token}",
                "Accept": GITHUB_ACCEPT_HEADER,
                "User-Agent": MERIDIAN_USER_AGENT,
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            },
        )

        if profile_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub OAuth token.",
            )

        profile = profile_response.json()

        if str(profile.get("id")) != str(verified_user.get("id")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub OAuth token.",
            )

        email = profile.get("email") or await _get_github_primary_email(
            client, payload.access_token
        )

    provider_user_id = profile.get("id")
    if provider_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub OAuth token.",
        )

    return ProviderUserPayload(
        oauthId=str(provider_user_id),
        email=email,
        name=profile.get("name") or profile.get("login"),
        avatarUrl=profile.get("avatar_url"),
    )


async def verify_oauth_login(
    provider: ProviderEnum, payload: OAuthLoginPayload
) -> ProviderUserPayload:
    if provider == ProviderEnum.GOOGLE:
        return await _verify_google_login(payload)
    if provider == ProviderEnum.GITHUB:
        return await _verify_github_login(payload)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported OAuth provider.",
    )
