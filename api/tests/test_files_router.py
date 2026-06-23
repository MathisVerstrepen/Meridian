import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "app"

os.chdir(APP_DIR)
sys.path.append(str(APP_DIR))

from database.pg.models import Files
from routers.files import (
    BulkDeletePayload,
    BulkDestinationPayload,
    _build_id_download_filename,
    bulk_copy_items,
    bulk_delete_items,
    bulk_move_items,
)


def test_build_id_download_filename_uses_video_content_type_extension() -> None:
    file_id = uuid.uuid4()
    file_record = Files(
        id=file_id,
        user_id=uuid.uuid4(),
        name="Video Context: prompt...",
        type="file",
        file_path="generated_videos/generated_123.mov",
        content_type="video/quicktime; charset=binary",
    )

    assert _build_id_download_filename(file_record) == f"{file_id}.mov"


def test_build_id_download_filename_supports_legacy_video_mov_content_type() -> None:
    file_id = uuid.uuid4()
    file_record = Files(
        id=file_id,
        user_id=uuid.uuid4(),
        name="Video Context: prompt...",
        type="file",
        file_path="generated_videos/generated_123.mov",
        content_type="video/mov",
    )

    assert _build_id_download_filename(file_record) == f"{file_id}.mov"


def test_build_id_download_filename_falls_back_to_storage_extension() -> None:
    file_id = uuid.uuid4()
    file_record = Files(
        id=file_id,
        user_id=uuid.uuid4(),
        name="Video Context: prompt...",
        type="file",
        file_path="generated_videos/generated_123.webm",
        content_type=None,
    )

    assert _build_id_download_filename(file_record) == f"{file_id}.webm"


def test_bulk_delete_items_deletes_all_items_and_releases_combined_storage(monkeypatch) -> None:
    user_id = uuid.uuid4()
    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {
        "sizes": [],
        "deleted_items": [],
        "deleted_files": [],
        "released": [],
    }

    async def fake_get_recursive_item_size(engine, item_id, current_user_id):
        calls["sizes"].append((engine, item_id, current_user_id))
        return 10 if item_id == first_item_id else 15

    async def fake_delete_db_item_recursively(*, pg_engine, item_id, user_id):
        calls["deleted_items"].append((pg_engine, item_id, user_id))
        return [f"{item_id}.png"]

    async def fake_delete_file_from_disk(current_user_id, file_path):
        calls["deleted_files"].append((current_user_id, file_path))

    async def fake_release_storage(engine, current_user_id, size):
        calls["released"].append((engine, current_user_id, size))

    monkeypatch.setattr("routers.files.get_recursive_item_size", fake_get_recursive_item_size)
    monkeypatch.setattr("routers.files.delete_db_item_recursively", fake_delete_db_item_recursively)
    monkeypatch.setattr("routers.files.delete_file_from_disk", fake_delete_file_from_disk)
    monkeypatch.setattr("routers.files.release_storage", fake_release_storage)

    asyncio.run(
        bulk_delete_items(
            request,
            BulkDeletePayload(item_ids=[first_item_id, second_item_id]),
            user_id_str=str(user_id),
        )
    )

    assert calls["sizes"] == [
        (pg_engine, first_item_id, user_id),
        (pg_engine, second_item_id, user_id),
    ]
    assert calls["deleted_items"] == [
        (pg_engine, first_item_id, user_id),
        (pg_engine, second_item_id, user_id),
    ]
    assert calls["deleted_files"] == [
        (user_id, f"{first_item_id}.png"),
        (user_id, f"{second_item_id}.png"),
    ]
    assert calls["released"] == [(pg_engine, user_id, 25)]


def test_bulk_move_items_moves_all_items_to_destination(monkeypatch) -> None:
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"moved": [], "mapped": []}

    async def fake_move_item(engine, *, item_id, user_id, destination_folder_id):
        calls["moved"].append((engine, item_id, user_id, destination_folder_id))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        calls["mapped"].append((engine, item.id))
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.move_item", fake_move_item)
    monkeypatch.setattr("routers.files._to_file_system_object", fake_to_file_system_object)

    result = asyncio.run(
        bulk_move_items(
            request,
            BulkDestinationPayload(
                item_ids=[first_item_id, second_item_id],
                destination_folder_id=destination_folder_id,
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls["moved"] == [
        (pg_engine, first_item_id, user_id, destination_folder_id),
        (pg_engine, second_item_id, user_id, destination_folder_id),
    ]
    assert calls["mapped"] == [(pg_engine, first_item_id), (pg_engine, second_item_id)]
    assert result == [f"mapped-{first_item_id}", f"mapped-{second_item_id}"]


def test_bulk_copy_items_copies_all_items_to_destination(monkeypatch) -> None:
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"copied": [], "mapped": []}

    async def fake_copy_file_system_item(pg_engine, *, user_id, item_id, destination_folder_id):
        calls["copied"].append((pg_engine, user_id, item_id, destination_folder_id))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        calls["mapped"].append((engine, item.id))
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.copy_file_system_item", fake_copy_file_system_item)
    monkeypatch.setattr("routers.files._to_file_system_object", fake_to_file_system_object)

    result = asyncio.run(
        bulk_copy_items(
            request,
            BulkDestinationPayload(
                item_ids=[first_item_id, second_item_id],
                destination_folder_id=destination_folder_id,
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls["copied"] == [
        (pg_engine, user_id, first_item_id, destination_folder_id),
        (pg_engine, user_id, second_item_id, destination_folder_id),
    ]
    assert calls["mapped"] == [(pg_engine, first_item_id), (pg_engine, second_item_id)]
    assert result == [f"mapped-{first_item_id}", f"mapped-{second_item_id}"]


def test_bulk_move_items_applies_keep_both_conflict_name(monkeypatch) -> None:
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"resolved": [], "moved": []}

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="report.pdf", type="file")

    async def fake_resolve_conflict(
        engine,
        *,
        user_id,
        parent_id,
        name,
        item_type,
        conflict_policy,
        exclude_item_id=None,
    ):
        calls["resolved"].append(
            (engine, user_id, parent_id, name, item_type, conflict_policy, exclude_item_id)
        )
        return "report (1).pdf", None

    async def fake_move_item(engine, *, item_id, user_id, destination_folder_id, new_name=None):
        calls["moved"].append((engine, item_id, user_id, destination_folder_id, new_name))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._resolve_child_name_conflict", fake_resolve_conflict)
    monkeypatch.setattr("routers.files.move_item", fake_move_item)
    monkeypatch.setattr("routers.files._to_file_system_object", fake_to_file_system_object)

    result = asyncio.run(
        bulk_move_items(
            request,
            BulkDestinationPayload(
                item_ids=[item_id],
                destination_folder_id=destination_folder_id,
                conflict_policy="keep_both",
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls["resolved"] == [
        (pg_engine, user_id, destination_folder_id, "report.pdf", "file", "keep_both", item_id)
    ]
    assert calls["moved"] == [
        (pg_engine, item_id, user_id, destination_folder_id, "report (1).pdf")
    ]
    assert result == [f"mapped-{item_id}"]


def test_bulk_copy_items_skips_conflicting_items(monkeypatch) -> None:
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"copied": []}

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="report.pdf", type="file")

    async def fake_resolve_conflict(*args, **kwargs):
        return "report.pdf", SimpleNamespace(id=uuid.uuid4())

    async def fake_copy_file_system_item(*args, **kwargs):
        calls["copied"].append((args, kwargs))
        return SimpleNamespace(id=item_id)

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._resolve_child_name_conflict", fake_resolve_conflict)
    monkeypatch.setattr("routers.files.copy_file_system_item", fake_copy_file_system_item)

    result = asyncio.run(
        bulk_copy_items(
            request,
            BulkDestinationPayload(
                item_ids=[item_id],
                destination_folder_id=destination_folder_id,
                conflict_policy="skip",
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls["copied"] == []
    assert result == []
