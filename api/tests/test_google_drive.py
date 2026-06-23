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


def test_list_google_drive_root_uses_my_drive_only(monkeypatch) -> None:
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
    assert params["corpora"] == "user"
    assert params["q"] == "'root' in parents and trashed=false"


def test_list_google_drive_shared_with_me_uses_shared_filter(monkeypatch) -> None:
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
        google_drive.list_google_drive_files(
            pg_engine, FakeHttpClient(), user_id, section="shared_with_me"
        )
    )

    assert refs == []
    assert next_page_token is None
    assert incomplete_search is False
    _url, params, _headers = calls["gets"][0]
    assert params["corpora"] == "allDrives"
    assert params["q"] == "sharedWithMe = true and trashed=false"


def test_list_google_shared_drives_calls_drives_api(monkeypatch) -> None:
    user_id = uuid.uuid4()
    pg_engine = object()
    calls: dict[str, list] = {"gets": []}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "drives": [{"id": "shared-drive-1", "name": "Team Drive"}],
                "nextPageToken": "next-page",
            }

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

    drives, next_page_token = asyncio.run(
        google_drive.list_google_shared_drives(
            pg_engine, FakeHttpClient(), user_id, page_token="page-1"
        )
    )

    assert [(drive.id, drive.name) for drive in drives] == [("shared-drive-1", "Team Drive")]
    assert next_page_token == "next-page"
    url, params, headers = calls["gets"][0]
    assert url == f"{google_drive.GOOGLE_DRIVE_API_BASE}/drives"
    assert params == {
        "fields": "nextPageToken,drives(id,name)",
        "pageSize": "100",
        "pageToken": "page-1",
    }
    assert headers == {"Authorization": "Bearer access-token"}


def test_download_google_sheet_exports_markdown_from_all_tabs(monkeypatch) -> None:
    user_id = uuid.uuid4()
    pg_engine = object()
    calls: dict[str, list] = {"gets": []}
    ref = ExternalFileRef(
        id=uuid.uuid4(),
        user_id=user_id,
        provider=google_drive.GOOGLE_DRIVE_PROVIDER,
        external_id="sheet-file-1",
        name="Budget",
        mime_type=google_drive.GOOGLE_SPREADSHEET_MIME_TYPE,
    )

    class FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self.text = ""
            self.payload = payload
            self.content = b""

        def json(self):
            return self.payload

    class FakeHttpClient:
        async def get(self, url, *, params=None, headers=None):
            calls["gets"].append((url, params, headers))
            if url.endswith("/sheet-file-1"):
                return FakeResponse(
                    {
                        "properties": {"title": "Budget 2026"},
                        "sheets": [
                            {"properties": {"title": "Summary"}},
                            {"properties": {"title": "Team's Plan"}},
                        ],
                    }
                )
            return FakeResponse(
                {
                    "valueRanges": [
                        {"values": [["Month", "Revenue"], ["Jan", "12,000"]]},
                        {"values": [["Owner", "Status"], ["Mathis", "Active"]]},
                    ]
                }
            )

    async def fake_get_google_drive_access_token(*_args):
        return "access-token"

    monkeypatch.setattr(
        google_drive,
        "get_google_drive_access_token",
        fake_get_google_drive_access_token,
    )

    downloaded = asyncio.run(
        google_drive.download_google_drive_file(pg_engine, FakeHttpClient(), user_id, ref)
    )

    assert downloaded.filename == "Budget.md"
    assert downloaded.content_type == "text/markdown"
    markdown = downloaded.content.decode("utf-8")
    assert "# Spreadsheet: Budget 2026" in markdown
    assert "## Sheet: Summary" in markdown
    assert 'Month,Revenue\nJan,"12,000"' in markdown
    assert "## Sheet: Team's Plan" in markdown
    assert "Owner,Status\nMathis,Active" in markdown
    assert downloaded.content_hash == google_drive.hashlib.sha256(downloaded.content).hexdigest()
    assert calls["gets"] == [
        (
            f"{google_drive.GOOGLE_SHEETS_API_BASE}/sheet-file-1",
            {"fields": "properties(title),sheets(properties(title))"},
            {"Authorization": "Bearer access-token"},
        ),
        (
            f"{google_drive.GOOGLE_SHEETS_API_BASE}/sheet-file-1/values:batchGet",
            [
                ("valueRenderOption", "FORMATTED_VALUE"),
                ("dateTimeRenderOption", "FORMATTED_STRING"),
                ("ranges", "'Summary'"),
                ("ranges", "'Team''s Plan'"),
            ],
            {"Authorization": "Bearer access-token"},
        ),
    ]


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
        assert (engine, client, current_user_id, current_ref) == (
            pg_engine,
            http_client,
            user_id,
            ref,
        )
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
            (
                engine,
                current_user_id,
                current_ref_id,
                storage_path,
                size,
                content_type,
                content_hash,
            )
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


def test_materialize_google_drive_file_uses_valid_cache_without_download(
    monkeypatch, tmp_path
) -> None:
    user_id = uuid.uuid4()
    ref_id = uuid.uuid4()
    pg_engine = object()
    http_client = object()
    cached_storage_path = f".cache/external/google_drive/{ref_id}/cached-image.png"
    cached_disk_path = tmp_path / cached_storage_path
    cached_disk_path.parent.mkdir(parents=True)
    cached_disk_path.write_bytes(b"cached-png-bytes")
    ref = ExternalFileRef(
        id=ref_id,
        user_id=user_id,
        provider=google_drive.GOOGLE_DRIVE_PROVIDER,
        external_id="drive-file-1",
        name="Original Drive Name",
        mime_type="image/png",
    )

    async def fake_get_external_file_ref(engine, current_user_id, current_ref_id):
        assert (engine, current_user_id, current_ref_id) == (pg_engine, user_id, ref_id)
        return ref

    async def fake_get_valid_cache(engine, current_user_id, current_ref_id):
        assert (engine, current_user_id, current_ref_id) == (pg_engine, user_id, ref_id)
        return file_sources.ExternalFileCacheSnapshot(
            storage_path=cached_storage_path,
            content_type="image/png; charset=binary",
            size=len(b"cached-png-bytes"),
            content_hash="cached-hash",
        )

    async def fail_download_google_drive_file(*_args):
        raise AssertionError("cached files should not be downloaded again")

    monkeypatch.setattr(file_sources, "get_user_storage_path", lambda _user_id: str(tmp_path))
    monkeypatch.setattr(file_sources, "get_external_file_ref", fake_get_external_file_ref)
    monkeypatch.setattr(file_sources, "_get_valid_cache", fake_get_valid_cache)
    monkeypatch.setattr(file_sources, "download_google_drive_file", fail_download_google_drive_file)

    materialized = asyncio.run(
        file_sources.materialize_attachment_file(
            pg_engine,
            http_client,
            user_id,
            {"source": "google_drive", "id": str(ref_id)},
        )
    )

    assert materialized.source == google_drive.GOOGLE_DRIVE_PROVIDER
    assert materialized.file_id == str(ref_id)
    assert materialized.path == cached_disk_path
    assert materialized.storage_path == cached_storage_path
    assert materialized.name == "cached-image.png"
    assert materialized.content_type == "image/png; charset=binary"
    assert materialized.size == len(b"cached-png-bytes")
    assert materialized.content_hash == "cached-hash"


def test_get_valid_cache_returns_snapshot_readable_after_commit(monkeypatch) -> None:
    user_id = uuid.uuid4()
    ref_id = uuid.uuid4()

    class ExpiringCacheRow:
        def __init__(self) -> None:
            self.expired = False
            self.last_accessed_at = None

        def _value(self, value):
            if self.expired:
                raise AssertionError("cache row attributes were accessed after commit")
            return value

        @property
        def storage_path(self):
            return self._value(f".cache/external/google_drive/{ref_id}/cached-image.png")

        @property
        def size(self):
            return self._value(16)

        @property
        def content_type(self):
            return self._value("image/png")

        @property
        def content_hash(self):
            return self._value("cached-hash")

    cache_row = ExpiringCacheRow()

    class FakeScalars:
        def first(self):
            return cache_row

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeSession:
        def __init__(self, _engine) -> None:
            self.added = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def exec(self, _stmt):
            return FakeResult()

        def add(self, row):
            self.added.append(row)

        async def commit(self):
            cache_row.expired = True

    monkeypatch.setattr(file_sources, "AsyncSession", FakeSession)

    snapshot = asyncio.run(file_sources._get_valid_cache(object(), user_id, ref_id))

    assert snapshot is not None
    assert snapshot.storage_path == f".cache/external/google_drive/{ref_id}/cached-image.png"
    assert snapshot.size == 16
    assert snapshot.content_type == "image/png"
    assert snapshot.content_hash == "cached-hash"
