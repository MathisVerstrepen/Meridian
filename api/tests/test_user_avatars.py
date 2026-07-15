import asyncio
import sys
import uuid
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.models import User
from models.auth import ProviderEnum
from services import user_avatars


def _image_bytes(image_format: str = "PNG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "green").save(buffer, format=image_format)
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, status_code, headers=None, chunks=()):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class FakeStream:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeAsyncClient:
    def __init__(self, responses, calls):
        self.responses = iter(responses)
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, method, url):
        self.calls.append((method, url))
        return FakeStream(next(self.responses))


def _user(avatar_url=None):
    return User(id=uuid.uuid4(), username="avatar-user", avatar_url=avatar_url)


def test_download_provider_avatar_follows_only_allowed_redirects(monkeypatch):
    calls = []
    responses = [
        FakeResponse(302, {"Location": "/image"}),
        FakeResponse(200, {"Content-Type": "image/png"}, [_image_bytes()]),
    ]
    monkeypatch.setattr(
        user_avatars.httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(responses, calls),
    )

    avatar = asyncio.run(
        user_avatars._download_provider_avatar(
            ProviderEnum.GOOGLE, "https://lh3.googleusercontent.com/avatar"
        )
    )

    assert avatar.content_type == "image/png"
    assert avatar.filename == "avatar.png"
    assert calls == [
        ("GET", "https://lh3.googleusercontent.com/avatar"),
        ("GET", "https://lh3.googleusercontent.com/image"),
    ]


def test_download_provider_avatar_rejects_off_host_redirect_before_request(monkeypatch):
    calls = []
    monkeypatch.setattr(
        user_avatars.httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            [FakeResponse(302, {"Location": "https://evil.example/avatar"})], calls
        ),
    )

    with pytest.raises(user_avatars.AvatarDownloadError):
        asyncio.run(
            user_avatars._download_provider_avatar(
                ProviderEnum.GITHUB, "https://avatars.githubusercontent.com/avatar"
            )
        )

    assert calls == [("GET", "https://avatars.githubusercontent.com/avatar")]


@pytest.mark.parametrize(
    "value",
    [
        "http://lh3.googleusercontent.com/avatar",
        "https://evilgoogleusercontent.com/avatar",
        "https://user@lh3.googleusercontent.com/avatar",
        "https://avatars.githubusercontent.com.evil.example/avatar",
    ],
)
def test_provider_avatar_url_requires_https_and_label_boundaries(value):
    with pytest.raises(user_avatars.AvatarDownloadError):
        user_avatars._validate_provider_avatar_url(ProviderEnum.GOOGLE, value)


def test_bounded_response_rejects_declared_and_streamed_oversize():
    declared_oversize = FakeResponse(
        200,
        {
            "Content-Type": "image/png",
            "Content-Length": str(user_avatars.MAX_AVATAR_SIZE_BYTES + 1),
        },
    )
    streamed_oversize = FakeResponse(
        200,
        {"Content-Type": "image/png"},
        [b"x" * (user_avatars.MAX_AVATAR_SIZE_BYTES + 1)],
    )

    with pytest.raises(user_avatars.AvatarDownloadError):
        asyncio.run(user_avatars._read_bounded_avatar_response(declared_oversize))
    with pytest.raises(user_avatars.AvatarDownloadError):
        asyncio.run(user_avatars._read_bounded_avatar_response(streamed_oversize))


def test_avatar_validation_rejects_mime_decode_and_format_failures():
    with pytest.raises(user_avatars.AvatarDownloadError):
        user_avatars._validate_avatar_bytes(_image_bytes(), "image/jpeg")
    with pytest.raises(user_avatars.AvatarDownloadError):
        user_avatars._validate_avatar_bytes(b"not an image", "image/png")
    with pytest.raises(user_avatars.AvatarDownloadError):
        asyncio.run(
            user_avatars._read_bounded_avatar_response(
                FakeResponse(200, {"Content-Type": "image/gif"}, [_image_bytes()])
            )
        )


def test_avatar_validation_rejects_decompression_bomb(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(user_avatars.AvatarDownloadError):
        user_avatars._validate_avatar_bytes(_image_bytes(), "image/png")


def test_sync_provider_avatar_preserves_valid_local_avatar(monkeypatch):
    user = _user("uploaded-avatar.png")

    async def should_not_run(*args, **kwargs):
        raise AssertionError("local avatars must not trigger synchronization")

    monkeypatch.setattr(user_avatars, "_download_provider_avatar", should_not_run)
    monkeypatch.setattr(user_avatars, "update_user_avatar_url", should_not_run)

    result = asyncio.run(
        user_avatars.sync_provider_avatar(
            "engine", user, ProviderEnum.GOOGLE, "https://lh3.googleusercontent.com/avatar"
        )
    )

    assert result == "uploaded-avatar.png"


def test_sync_provider_avatar_network_failure_clears_legacy_reference(monkeypatch):
    user = _user("https://old-provider.example/avatar")
    updates = []

    async def fail_download(*args, **kwargs):
        raise httpx.RequestError("network unavailable")

    async def fake_update(engine, user_id, avatar_url):
        updates.append((engine, user_id, avatar_url))

    monkeypatch.setattr(user_avatars, "_download_provider_avatar", fail_download)
    monkeypatch.setattr(user_avatars, "update_user_avatar_url", fake_update)

    result = asyncio.run(
        user_avatars.sync_provider_avatar(
            "engine", user, ProviderEnum.GOOGLE, "https://lh3.googleusercontent.com/avatar"
        )
    )

    assert result is None
    assert updates == [("engine", str(user.id), None)]


def test_sync_provider_avatar_stores_only_generated_local_filename(monkeypatch):
    user = _user()
    updates = []

    async def fake_download(*args, **kwargs):
        return user_avatars.DownloadedAvatar(_image_bytes(), "image/png", "avatar.png")

    async def fake_save(user_id, file_contents, original_filename, subdirectory):
        assert original_filename == "avatar.png"
        assert subdirectory == "profile_pictures"
        return "generated-avatar.png"

    async def fake_update(engine, user_id, avatar_url):
        updates.append((engine, user_id, avatar_url))

    monkeypatch.setattr(user_avatars, "_download_provider_avatar", fake_download)
    monkeypatch.setattr(user_avatars, "save_file_to_disk", fake_save)
    monkeypatch.setattr(user_avatars, "update_user_avatar_url", fake_update)

    result = asyncio.run(
        user_avatars.sync_provider_avatar(
            "engine", user, ProviderEnum.GOOGLE, "https://lh3.googleusercontent.com/avatar"
        )
    )

    assert result == "generated-avatar.png"
    assert updates == [("engine", str(user.id), "generated-avatar.png")]


def test_sync_provider_avatar_saves_local_filename_and_cleans_up_db_failure(monkeypatch):
    user = _user("https://old-provider.example/avatar")
    calls = []

    async def fake_download(*args, **kwargs):
        return user_avatars.DownloadedAvatar(_image_bytes(), "image/png", "avatar.png")

    async def fake_save(user_id, file_contents, original_filename, subdirectory):
        calls.append(("save", user_id, original_filename, subdirectory))
        return "stored-avatar.png"

    async def fail_update(engine, user_id, avatar_url):
        calls.append(("update", avatar_url))
        if avatar_url is not None:
            raise RuntimeError("database unavailable")

    async def fake_delete(user_id, filename, subdirectory):
        calls.append(("delete", user_id, filename, subdirectory))
        return True

    monkeypatch.setattr(user_avatars, "_download_provider_avatar", fake_download)
    monkeypatch.setattr(user_avatars, "save_file_to_disk", fake_save)
    monkeypatch.setattr(user_avatars, "update_user_avatar_url", fail_update)
    monkeypatch.setattr(user_avatars, "delete_file_from_disk", fake_delete)

    result = asyncio.run(
        user_avatars.sync_provider_avatar(
            "engine", user, ProviderEnum.GITHUB, "https://avatars.githubusercontent.com/avatar"
        )
    )

    assert result is None
    assert calls == [
        ("save", user.id, "avatar.png", "profile_pictures"),
        ("update", "stored-avatar.png"),
        ("delete", user.id, "stored-avatar.png", "profile_pictures"),
        ("update", None),
    ]


def test_safe_avatar_reference_rejects_external_and_path_values():
    assert user_avatars.safe_avatar_reference("stored-avatar.webp") == "stored-avatar.webp"
    assert (
        user_avatars.safe_avatar_reference("https://avatars.githubusercontent.com/avatar") is None
    )
    assert user_avatars.safe_avatar_reference("../avatar.png") is None
    assert user_avatars.safe_avatar_reference("folder/avatar.png") is None
