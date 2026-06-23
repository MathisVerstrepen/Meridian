import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "app"

os.chdir(APP_DIR)
sys.path.append(str(APP_DIR))

from database.pg.models import ExternalFileRef
from services import file_sources, google_drive
from services.google_drive import DownloadedDriveFile


def test_store_google_drive_token_encrypts_and_persists_refresh_metadata(monkeypatch) -> None:
    user_id = str(uuid.uuid4())
    pg_engine = object()
    calls: dict[str, list] = {"encrypted": [], "stored": []}

    async def fake_encrypt_api_key(raw: str) -> str:
        calls["encrypted"].append(raw)
        return f"encrypted:{raw}"

    async def fake_store_provider_token(
        engine,
        current_user_id,
        provider,
        encrypted_token,
        *,
        encrypted_refresh_token=None,
        scopes=None,
        expires_at=None,
    ):
        calls["stored"].append(
            (
                engine,
                current_user_id,
                provider,
                encrypted_token,
                encrypted_refresh_token,
                scopes,
                expires_at,
            )
        )
        return SimpleNamespace(provider=provider)

    monkeypatch.setattr(google_drive, "encrypt_api_key", fake_encrypt_api_key)
    monkeypatch.setattr(google_drive, "store_provider_token", fake_store_provider_token)

    result = asyncio.run(
        google_drive.store_google_drive_token(
            pg_engine,
            user_id,
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 120,
                "scope": "scope-a scope-b",
            },
        )
    )

    assert result.provider == google_drive.GOOGLE_DRIVE_PROVIDER
    assert calls["encrypted"] == ["access-token", "refresh-token"]
    stored = calls["stored"][0]
    assert stored[:6] == (
        pg_engine,
        user_id,
        google_drive.GOOGLE_DRIVE_PROVIDER,
        "encrypted:access-token",
        "encrypted:refresh-token",
        "scope-a scope-b",
    )
    assert stored[6] > datetime.now(timezone.utc)


def test_list_google_drive_files_uses_all_drive_params_and_upserts(monkeypatch) -> None:
    user_id = uuid.uuid4()
    pg_engine = object()
    calls: dict[str, list] = {"gets": [], "items": []}
    first_ref = ExternalFileRef(
        id=uuid.uuid4(),
        user_id=user_id,
        provider=google_drive.GOOGLE_DRIVE_PROVIDER,
        external_id="drive-file-1",
        name="Report.pdf",
        mime_type="application/pdf",
    )

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "files": [
                    {
                        "id": "drive-file-1",
                        "name": "Report.pdf",
                        "mimeType": "application/pdf",
                        "size": "42",
                    }
                ],
                "nextPageToken": "next-page",
                "incompleteSearch": True,
            }

    class FakeHttpClient:
        async def get(self, url, *, params=None, headers=None):
            calls["gets"].append((url, params, headers))
            return FakeResponse()

    async def fake_get_google_drive_access_token(engine, http_client, current_user_id):
        assert engine is pg_engine
        assert current_user_id == str(user_id)
        return "access-token"

    async def fake_upsert_external_file_ref(engine, current_user_id, item):
        calls["items"].append((engine, current_user_id, item))
        return first_ref

    monkeypatch.setattr(
        google_drive,
        "get_google_drive_access_token",
        fake_get_google_drive_access_token,
    )
    monkeypatch.setattr(google_drive, "upsert_external_file_ref", fake_upsert_external_file_ref)

    refs, next_page_token, incomplete_search = asyncio.run(
        google_drive.list_google_drive_files(
            pg_engine,
            FakeHttpClient(),
            user_id,
            folder_id="shared-folder'with-quote",
            page_token="page-1",
        )
    )

    assert refs == [first_ref]
    assert next_page_token == "next-page"
    assert incomplete_search is True
    url, params, headers = calls["gets"][0]
    assert url == f"{google_drive.GOOGLE_DRIVE_API_BASE}/files"
    assert params["supportsAllDrives"] == "true"
    assert params["includeItemsFromAllDrives"] == "true"
    assert params["pageToken"] == "page-1"
    assert params["q"] == "'shared-folder\\'with-quote' in parents and trashed=false"
    assert headers == {"Authorization": "Bearer access-token"}
    assert calls["items"] == [
        (
            pg_engine,
            user_id,
            {
                "id": "drive-file-1",
                "name": "Report.pdf",
                "mimeType": "application/pdf",
                "size": "42",
            },
        )
    ]


def test_list_google_drive_root_includes_shared_with_me(monkeypatch) -> None:
    user_id = uuid.uuid4()
    pg_engine = object()
    calls: dict[str, list] = {"gets": []}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"files": []}

    class FakeHttpClient:
        async def get(self, url, *, params=None, headers=None):
            calls["gets"].append((url, params, headers))
            return FakeResponse()

    async def fake_get_google_drive_access_token(*_args):
        return "access-token"

    monkeypatch.setattr(
        google_drive,
        "get_google_drive_access_token",
        fake_get_google_drive_access_token,
    )

    refs, next_page_token, incomplete_search = asyncio.run(
        google_drive.list_google_drive_files(pg_engine, FakeHttpClient(), user_id)
    )

    assert refs == []
    assert next_page_token is None
    assert incomplete_search is False
    _url, params, _headers = calls["gets"][0]
    assert params["corpora"] == "allDrives"
    assert params["q"] == "('root' in parents or sharedWithMe = true) and trashed=false"


def test_materialize_google_drive_file_downloads_and_tracks_cache(monkeypatch, tmp_path) -> None:
    user_id = uuid.uuid4()
    ref_id = uuid.uuid4()
    pg_engine = object()
    http_client = object()
    calls: dict[str, list] = {"reserved": [], "released": [], "cached": []}
    ref = ExternalFileRef(
        id=ref_id,
        user_id=user_id,
        provider=google_drive.GOOGLE_DRIVE_PROVIDER,
        external_id="drive-file-1",
        name="Report.pdf",
        mime_type="application/pdf",
    )

    async def fake_get_external_file_ref(engine, current_user_id, current_ref_id):
        assert (engine, current_user_id, current_ref_id) == (pg_engine, user_id, ref_id)
        return ref

    async def fake_get_valid_cache(*_args):
        return None

    async def fake_download_google_drive_file(engine, client, current_user_id, current_ref):
        assert (engine, client, current_user_id, current_ref) == (pg_engine, http_client, user_id, ref)
        return DownloadedDriveFile(
            filename="Report.pdf",
            content=b"drive-bytes",
            content_type="application/pdf",
            content_hash="content-hash",
        )

    async def fake_check_and_reserve_storage(engine, current_user_id, size):
        calls["reserved"].append((engine, current_user_id, size))

    async def fake_release_storage(engine, current_user_id, size):
        calls["released"].append((engine, current_user_id, size))

    async def fake_create_cache_row(
        engine,
        current_user_id,
        current_ref_id,
        storage_path,
        size,
        content_type,
        content_hash,
    ):
        calls["cached"].append(
            (engine, current_user_id, current_ref_id, storage_path, size, content_type, content_hash)
        )
        return SimpleNamespace(
            storage_path=storage_path,
            size=size,
            content_type=content_type,
            content_hash=content_hash,
        )

    monkeypatch.setattr(file_sources, "get_user_storage_path", lambda _user_id: str(tmp_path))
    monkeypatch.setattr(file_sources, "get_external_file_ref", fake_get_external_file_ref)
    monkeypatch.setattr(file_sources, "_get_valid_cache", fake_get_valid_cache)
    monkeypatch.setattr(file_sources, "download_google_drive_file", fake_download_google_drive_file)
    monkeypatch.setattr(file_sources, "check_and_reserve_storage", fake_check_and_reserve_storage)
    monkeypatch.setattr(file_sources, "release_storage", fake_release_storage)
    monkeypatch.setattr(file_sources, "_create_cache_row", fake_create_cache_row)

    materialized = asyncio.run(
        file_sources.materialize_attachment_file(
            pg_engine,
            http_client,
            user_id,
            {"source": "google_drive", "id": str(ref_id)},
        )
    )

    expected_storage_path = f".cache/external/google_drive/{ref_id}/Report.pdf"
    expected_disk_path = tmp_path / expected_storage_path
    assert expected_disk_path.read_bytes() == b"drive-bytes"
    assert materialized.source == google_drive.GOOGLE_DRIVE_PROVIDER
    assert materialized.file_id == str(ref_id)
    assert materialized.path == expected_disk_path
    assert materialized.storage_path == expected_storage_path
    assert materialized.name == "Report.pdf"
    assert materialized.content_type == "application/pdf"
    assert materialized.size == len(b"drive-bytes")
    assert materialized.content_hash == "content-hash"
    assert calls["reserved"] == [(pg_engine, user_id, len(b"drive-bytes"))]
    assert calls["released"] == []
    assert calls["cached"] == [
        (
            pg_engine,
            user_id,
            ref_id,
            expected_storage_path,
            len(b"drive-bytes"),
            "application/pdf",
            "content-hash",
        )
    ]
