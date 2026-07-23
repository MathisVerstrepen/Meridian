import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.user_ops.user_crud import ProviderUserPayload
from models.auth import OAuthLoginPayload, ProviderEnum

_ORIGINAL_WORKING_DIRECTORY = Path.cwd()
os.chdir(Path(__file__).resolve().parents[1] / "app")
try:
    from routers import users
finally:
    os.chdir(_ORIGINAL_WORKING_DIRECTORY)


def _user(avatar_url=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        username="oauth-user",
        email="oauth@example.com",
        avatar_url=avatar_url,
        oauth_provider="google",
        created_at=datetime.now(timezone.utc),
        is_admin=False,
        plan_type="free",
        is_verified=True,
        has_seen_welcome=False,
        is_suspended=False,
        suspended_reason=None,
        suspended_until=None,
    )


def _request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine="engine")))


def _configure_existing_login(monkeypatch, user, profile, avatar_result):
    async def fake_verify(provider, payload):
        return profile

    async def fake_get_by_provider(engine, oauth_id, provider):
        return user

    async def fake_sync(engine, synced_user, provider, provider_avatar_url):
        assert synced_user is user
        assert provider_avatar_url == profile.avatar_url
        return avatar_result

    async def fake_refresh(engine, user_id):
        return "refresh-token"

    monkeypatch.setattr(users, "verify_oauth_login", fake_verify)
    monkeypatch.setattr(users, "get_user_by_provider_id", fake_get_by_provider)
    monkeypatch.setattr(users, "sync_provider_avatar", fake_sync)
    monkeypatch.setattr(users, "create_access_token", lambda data: "access-token")
    monkeypatch.setattr(users, "create_refresh_token", fake_refresh)


def test_oauth_existing_external_avatar_migrates_and_response_is_local(monkeypatch):
    user = _user("https://legacy.example/avatar")
    profile = ProviderUserPayload(
        oauthId="provider-user", avatarUrl="https://lh3.googleusercontent.com/avatar"
    )
    _configure_existing_login(monkeypatch, user, profile, "localized-avatar.png")

    response = asyncio.run(
        users.sync_user.__wrapped__(
            _request(), ProviderEnum.GOOGLE, OAuthLoginPayload(idToken="token")
        )
    )

    assert response.accessToken == "access-token"
    assert response.user.avatar_url == "localized-avatar.png"


def test_oauth_avatar_failure_still_issues_tokens_without_external_reference(monkeypatch):
    user = _user("https://legacy.example/avatar")
    profile = ProviderUserPayload(
        oauthId="provider-user", avatarUrl="https://lh3.googleusercontent.com/avatar"
    )
    _configure_existing_login(monkeypatch, user, profile, None)

    response = asyncio.run(
        users.sync_user.__wrapped__(
            _request(), ProviderEnum.GOOGLE, OAuthLoginPayload(idToken="token")
        )
    )

    assert response.accessToken == "access-token"
    assert response.refreshToken == "refresh-token"
    assert response.user.avatar_url is None


def test_oauth_new_user_provisions_before_avatar_sync(monkeypatch):
    user = _user()
    profile = ProviderUserPayload(
        oauthId="provider-user", avatarUrl="https://avatars.githubusercontent.com/avatar"
    )
    calls = []

    async def fake_verify(provider, payload):
        return profile

    async def no_existing_user(*args):
        return None

    async def fake_create(*args):
        calls.append("create")
        return user

    async def fake_root(*args):
        calls.append("root")

    async def fake_settings(*args):
        calls.append("settings")

    async def fake_sync(*args):
        calls.append("avatar")
        return "localized-avatar.webp"

    async def fake_refresh(*args):
        return "refresh-token"

    monkeypatch.setattr(users, "verify_oauth_login", fake_verify)
    monkeypatch.setattr(users, "get_user_by_provider_id", no_existing_user)
    monkeypatch.setattr(users, "create_user_from_provider", fake_create)
    monkeypatch.setattr(users, "create_user_root_folder", fake_root)
    monkeypatch.setattr(users, "update_settings", fake_settings)
    monkeypatch.setattr(users, "sync_provider_avatar", fake_sync)
    monkeypatch.setattr(users, "create_access_token", lambda data: "access-token")
    monkeypatch.setattr(users, "create_refresh_token", fake_refresh)

    response = asyncio.run(
        users.sync_user.__wrapped__(
            _request(), ProviderEnum.GITHUB, OAuthLoginPayload(accessToken="token")
        )
    )

    assert calls == ["create", "root", "settings", "avatar"]
    assert response.user.avatar_url == "localized-avatar.webp"


def test_user_and_admin_serialization_hide_legacy_external_values():
    user = _user("https://legacy.example/avatar")

    assert users._to_user_read(user).avatar_url is None
    assert users._to_admin_user_list_item(user).avatar_url is None


def test_get_avatar_returns_404_for_legacy_external_value(monkeypatch):
    user = _user("https://legacy.example/avatar")

    async def fake_get_user(*args):
        return user

    monkeypatch.setattr(users, "get_user_by_id", fake_get_user)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(users.get_avatar(_request(), str(user.id)))

    assert exc_info.value.status_code == 404
