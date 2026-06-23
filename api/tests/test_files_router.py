import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

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
    upload_file,
)
from services.files import copy_file_system_item


def patch_filter_top_level_item_ids(monkeypatch):
    async def fake_filter_top_level_item_ids(engine, current_user_id, item_ids):
        return list(dict.fromkeys(item_ids))

    monkeypatch.setattr("routers.files.filter_top_level_item_ids", fake_filter_top_level_item_ids)


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

    async def fake_filter_top_level_item_ids(engine, current_user_id, item_ids):
        return list(dict.fromkeys(item_ids))

    monkeypatch.setattr("routers.files.filter_top_level_item_ids", fake_filter_top_level_item_ids)
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


def test_bulk_delete_items_filters_nested_selected_items(monkeypatch) -> None:
    user_id = uuid.uuid4()
    parent_item_id = uuid.uuid4()
    child_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"filtered": [], "deleted_items": []}

    async def fake_filter_top_level_item_ids(engine, current_user_id, item_ids):
        calls["filtered"].append((engine, current_user_id, item_ids))
        return [parent_item_id]

    async def fake_get_recursive_item_size(*args, **kwargs):
        return 15

    async def fake_delete_db_item_recursively(*, pg_engine, item_id, user_id):
        calls["deleted_items"].append((pg_engine, item_id, user_id))
        return ["child.png"]

    async def fake_delete_file_from_disk(*args, **kwargs):
        return None

    async def fake_release_storage(*args, **kwargs):
        return None

    monkeypatch.setattr("routers.files.filter_top_level_item_ids", fake_filter_top_level_item_ids)
    monkeypatch.setattr("routers.files.get_recursive_item_size", fake_get_recursive_item_size)
    monkeypatch.setattr("routers.files.delete_db_item_recursively", fake_delete_db_item_recursively)
    monkeypatch.setattr("routers.files.delete_file_from_disk", fake_delete_file_from_disk)
    monkeypatch.setattr("routers.files.release_storage", fake_release_storage)

    asyncio.run(
        bulk_delete_items(
            request,
            BulkDeletePayload(item_ids=[child_item_id, parent_item_id]),
            user_id_str=str(user_id),
        )
    )

    assert calls["filtered"] == [(pg_engine, user_id, [child_item_id, parent_item_id])]
    assert calls["deleted_items"] == [(pg_engine, parent_item_id, user_id)]


def test_bulk_move_items_moves_all_items_to_destination(monkeypatch) -> None:
    patch_filter_top_level_item_ids(monkeypatch)
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"moved": [], "mapped": []}

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name=f"{file_id}.txt", type="file")

    async def fake_find_child_by_name(*args, **kwargs):
        return None

    async def fake_move_item(
        engine, *, item_id, user_id, destination_folder_id, new_name=None, replace_item_id=None
    ):
        calls["moved"].append((engine, item_id, user_id, destination_folder_id))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        calls["mapped"].append((engine, item.id))
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
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


def test_bulk_move_items_filters_nested_selected_items(monkeypatch) -> None:
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    parent_item_id = uuid.uuid4()
    child_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"filtered": [], "moved": []}

    async def fake_filter_top_level_item_ids(engine, current_user_id, item_ids):
        calls["filtered"].append((engine, current_user_id, item_ids))
        return [parent_item_id]

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="folder", type="folder")

    async def fake_find_child_by_name(*args, **kwargs):
        return None

    async def fake_move_item(
        engine, *, item_id, user_id, destination_folder_id, new_name=None, replace_item_id=None
    ):
        calls["moved"].append((engine, item_id, user_id, destination_folder_id))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.filter_top_level_item_ids", fake_filter_top_level_item_ids)
    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
    monkeypatch.setattr("routers.files.move_item", fake_move_item)
    monkeypatch.setattr("routers.files._to_file_system_object", fake_to_file_system_object)

    result = asyncio.run(
        bulk_move_items(
            request,
            BulkDestinationPayload(
                item_ids=[child_item_id, parent_item_id],
                destination_folder_id=destination_folder_id,
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls["filtered"] == [(pg_engine, user_id, [child_item_id, parent_item_id])]
    assert calls["moved"] == [(pg_engine, parent_item_id, user_id, destination_folder_id)]
    assert result == [f"mapped-{parent_item_id}"]


def test_bulk_copy_items_copies_all_items_to_destination(monkeypatch) -> None:
    patch_filter_top_level_item_ids(monkeypatch)
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"copied": [], "mapped": []}

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name=f"{file_id}.txt", type="file")

    async def fake_find_child_by_name(*args, **kwargs):
        return None

    async def fake_copy_file_system_item(
        pg_engine, *, user_id, item_id, destination_folder_id, new_name=None, replace_item_id=None
    ):
        calls["copied"].append((pg_engine, user_id, item_id, destination_folder_id))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        calls["mapped"].append((engine, item.id))
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
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


def test_bulk_copy_items_filters_nested_selected_items(monkeypatch) -> None:
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    parent_item_id = uuid.uuid4()
    child_item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"filtered": [], "copied": []}

    async def fake_filter_top_level_item_ids(engine, current_user_id, item_ids):
        calls["filtered"].append((engine, current_user_id, item_ids))
        return [parent_item_id]

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="folder", type="folder")

    async def fake_find_child_by_name(*args, **kwargs):
        return None

    async def fake_copy_file_system_item(
        pg_engine, *, user_id, item_id, destination_folder_id, new_name=None, replace_item_id=None
    ):
        calls["copied"].append((pg_engine, user_id, item_id, destination_folder_id))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.filter_top_level_item_ids", fake_filter_top_level_item_ids)
    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
    monkeypatch.setattr("routers.files.copy_file_system_item", fake_copy_file_system_item)
    monkeypatch.setattr("routers.files._to_file_system_object", fake_to_file_system_object)

    result = asyncio.run(
        bulk_copy_items(
            request,
            BulkDestinationPayload(
                item_ids=[child_item_id, parent_item_id],
                destination_folder_id=destination_folder_id,
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls["filtered"] == [(pg_engine, user_id, [child_item_id, parent_item_id])]
    assert calls["copied"] == [(pg_engine, user_id, parent_item_id, destination_folder_id)]
    assert result == [f"mapped-{parent_item_id}"]


def test_bulk_move_items_applies_keep_both_conflict_name(monkeypatch) -> None:
    patch_filter_top_level_item_ids(monkeypatch)
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"available_names": [], "moved": []}

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="report.pdf", type="file")

    async def fake_find_child_by_name(*args, **kwargs):
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_get_available_child_name(
        engine,
        current_user_id,
        current_parent_id,
        name,
        item_type,
        exclude_item_id=None,
        reserved_names=None,
    ):
        calls["available_names"].append(
            (engine, current_user_id, current_parent_id, name, item_type, exclude_item_id)
        )
        return "report (1).pdf"

    async def fake_move_item(
        engine, *, item_id, user_id, destination_folder_id, new_name=None, replace_item_id=None
    ):
        calls["moved"].append((engine, item_id, user_id, destination_folder_id, new_name))
        return SimpleNamespace(id=item_id)

    async def fake_to_file_system_object(engine, item):
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
    monkeypatch.setattr("routers.files._get_available_child_name", fake_get_available_child_name)
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

    assert calls["available_names"] == [
        (pg_engine, user_id, destination_folder_id, "report.pdf", "file", item_id)
    ]
    assert calls["moved"] == [
        (pg_engine, item_id, user_id, destination_folder_id, "report (1).pdf")
    ]
    assert result == [f"mapped-{item_id}"]


def test_bulk_copy_items_skips_conflicting_items(monkeypatch) -> None:
    patch_filter_top_level_item_ids(monkeypatch)
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    item_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"copied": []}

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="report.pdf", type="file")

    async def fake_find_child_by_name(*args, **kwargs):
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_copy_file_system_item(*args, **kwargs):
        calls["copied"].append((args, kwargs))
        return SimpleNamespace(id=item_id)

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
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


def test_bulk_copy_items_defers_replace_delete_until_after_copy(monkeypatch) -> None:
    patch_filter_top_level_item_ids(monkeypatch)
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    item_id = uuid.uuid4()
    replacement_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: list[tuple[str, uuid.UUID]] = []

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="report.pdf", type="file")

    async def fake_find_child_by_name(*args, **kwargs):
        return SimpleNamespace(id=replacement_id)

    async def fake_copy_file_system_item(
        pg_engine,
        *,
        user_id,
        item_id,
        destination_folder_id,
        new_name=None,
        replace_item_id=None,
    ):
        calls.append(("copy", replace_item_id))
        return SimpleNamespace(id=item_id)

    async def fake_delete_item_and_release_storage(pg_engine, user_id, item_id):
        calls.append(("delete", item_id))

    async def fake_to_file_system_object(engine, item):
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
    monkeypatch.setattr("routers.files.copy_file_system_item", fake_copy_file_system_item)
    monkeypatch.setattr(
        "routers.files._delete_item_and_release_storage", fake_delete_item_and_release_storage
    )
    monkeypatch.setattr("routers.files._to_file_system_object", fake_to_file_system_object)

    result = asyncio.run(
        bulk_copy_items(
            request,
            BulkDestinationPayload(
                item_ids=[item_id],
                destination_folder_id=destination_folder_id,
                conflict_policy="replace",
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls == [("copy", replacement_id), ("delete", replacement_id)]
    assert result == [f"mapped-{item_id}"]


def test_bulk_move_items_does_not_replace_earlier_duplicate_sources(monkeypatch) -> None:
    patch_filter_top_level_item_ids(monkeypatch)
    user_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    first_item_id = uuid.uuid4()
    second_item_id = uuid.uuid4()
    replacement_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    calls: dict[str, list] = {"moved": [], "deleted": []}

    async def fake_get_file_by_id(pg_engine, file_id, user_id):
        return SimpleNamespace(id=file_id, name="report.pdf", type="file")

    async def fake_find_child_by_name(*args, **kwargs):
        return SimpleNamespace(id=replacement_id)

    async def fake_get_available_child_name(*args, **kwargs):
        return "report (1).pdf"

    async def fake_move_item(
        engine, *, item_id, user_id, destination_folder_id, new_name=None, replace_item_id=None
    ):
        calls["moved"].append((item_id, new_name, replace_item_id))
        return SimpleNamespace(id=item_id)

    async def fake_delete_item_and_release_storage(pg_engine, user_id, item_id):
        calls["deleted"].append(item_id)

    async def fake_to_file_system_object(engine, item):
        return f"mapped-{item.id}"

    monkeypatch.setattr("routers.files.get_file_by_id", fake_get_file_by_id)
    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
    monkeypatch.setattr("routers.files._get_available_child_name", fake_get_available_child_name)
    monkeypatch.setattr("routers.files.move_item", fake_move_item)
    monkeypatch.setattr(
        "routers.files._delete_item_and_release_storage", fake_delete_item_and_release_storage
    )
    monkeypatch.setattr("routers.files._to_file_system_object", fake_to_file_system_object)

    result = asyncio.run(
        bulk_move_items(
            request,
            BulkDestinationPayload(
                item_ids=[first_item_id, second_item_id],
                destination_folder_id=destination_folder_id,
                conflict_policy="replace",
            ),
            user_id_str=str(user_id),
        )
    )

    assert calls["moved"] == [
        (first_item_id, None, replacement_id),
        (second_item_id, "report (1).pdf", None),
    ]
    assert calls["deleted"] == [replacement_id]
    assert result == [f"mapped-{first_item_id}", f"mapped-{second_item_id}"]


def test_upload_file_does_not_cleanup_committed_file_when_replace_delete_fails(
    monkeypatch,
) -> None:
    user_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    replacement_id = uuid.uuid4()
    pg_engine = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=pg_engine)))
    response = SimpleNamespace(status_code=None)
    upload = SimpleNamespace(filename="report.pdf", size=10, content_type="application/pdf")
    calls: list[tuple[str, object]] = []

    async def fake_find_child_by_name(*args, **kwargs):
        return SimpleNamespace(id=replacement_id)

    async def fake_check_and_reserve_storage(*args, **kwargs):
        calls.append(("reserve", args[2]))

    async def fake_save_upload_file_to_disk(*args, **kwargs):
        calls.append(("save", kwargs["original_filename"]))
        return "stored-report.pdf", "file-hash"

    async def fake_create_db_file(**kwargs):
        calls.append(("create", kwargs["file_path"]))
        return SimpleNamespace(
            id=uuid.uuid4(),
            name=kwargs["name"],
            type="file",
            size=kwargs["size"],
            content_type=kwargs["content_type"],
            created_at=None,
            updated_at=None,
        )

    async def fake_delete_item_and_release_storage(*args, **kwargs):
        calls.append(("delete-replacement", replacement_id))
        raise RuntimeError("replacement cleanup failed")

    async def fake_delete_file_from_disk(*args, **kwargs):
        calls.append(("delete-new-file", args[1]))

    async def fake_release_storage(*args, **kwargs):
        calls.append(("release-new-file", args[2]))

    monkeypatch.setattr("routers.files._find_child_by_name", fake_find_child_by_name)
    monkeypatch.setattr("routers.files.check_and_reserve_storage", fake_check_and_reserve_storage)
    monkeypatch.setattr("routers.files.save_upload_file_to_disk", fake_save_upload_file_to_disk)
    monkeypatch.setattr("routers.files.create_db_file", fake_create_db_file)
    monkeypatch.setattr(
        "routers.files._delete_item_and_release_storage", fake_delete_item_and_release_storage
    )
    monkeypatch.setattr("routers.files.delete_file_from_disk", fake_delete_file_from_disk)
    monkeypatch.setattr("routers.files.release_storage", fake_release_storage)

    with pytest.raises(RuntimeError):
        asyncio.run(
            upload_file(
                request,
                parent_id,
                response,
                conflict_policy="replace",
                file=upload,
                user_id_str=str(user_id),
            )
        )

    assert calls == [
        ("reserve", 10),
        ("save", "report.pdf"),
        ("create", "stored-report.pdf"),
        ("delete-replacement", replacement_id),
    ]


def test_copy_file_system_item_rejects_copy_into_own_subtree(monkeypatch) -> None:
    user_id = uuid.uuid4()
    item_id = uuid.uuid4()
    destination_folder_id = uuid.uuid4()
    pg_engine = object()
    calls: list[str] = []

    async def fake_is_item_in_subtree(engine, current_user_id, ancestor_id, nested_item_id):
        calls.append("subtree-check")
        return True

    async def fake_check_and_reserve_storage(*args, **kwargs):
        calls.append("reserve-storage")

    monkeypatch.setattr("services.files.is_item_in_subtree", fake_is_item_in_subtree)
    monkeypatch.setattr("services.files.check_and_reserve_storage", fake_check_and_reserve_storage)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            copy_file_system_item(
                pg_engine,
                user_id=user_id,
                item_id=item_id,
                destination_folder_id=destination_folder_id,
            )
        )

    assert exc_info.value.status_code == 400
    assert calls == ["subtree-check"]
