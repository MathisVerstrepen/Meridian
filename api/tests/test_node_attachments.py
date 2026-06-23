import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "app"

os.chdir(APP_DIR)
sys.path.append(str(APP_DIR))

from models.message import MessageContentTypeEnum
from services import node


def test_create_message_content_from_text_file_includes_materialized_content(
    monkeypatch, tmp_path
) -> None:
    file_id = uuid.uuid4()
    user_id = uuid.uuid4()
    materialized_path = tmp_path / "drive-doc.md"
    materialized_path.write_text("# Drive document\n\nFull content.", encoding="utf-8")

    async def fake_materialize_attachment_file(pg_engine, http_client, current_user_id, file_info):
        assert current_user_id == user_id
        assert file_info == {"id": str(file_id), "source": "google_drive"}
        return SimpleNamespace(
            content_type="text/markdown",
            path=materialized_path,
            content_hash="hash-1",
            name="drive-doc.md",
            file_id=str(file_id),
        )

    monkeypatch.setattr(node, "materialize_attachment_file", fake_materialize_attachment_file)

    content = asyncio.run(
        node.create_message_content_from_file(
            object(),
            str(user_id),
            {"id": str(file_id), "source": "google_drive"},
            True,
            http_client=object(),
        )
    )

    assert content is not None
    assert content.type == MessageContentTypeEnum.text
    assert content.text is not None
    assert "# Drive document" in content.text
    assert "Full content." in content.text
    assert "[Content omitted]" not in content.text


def test_create_message_content_from_text_file_omits_when_content_disabled(
    monkeypatch, tmp_path
) -> None:
    file_id = uuid.uuid4()
    user_id = uuid.uuid4()
    materialized_path = tmp_path / "drive-doc.md"
    materialized_path.write_text("# Drive document\n\nFull content.", encoding="utf-8")

    async def fake_materialize_attachment_file(*_args):
        return SimpleNamespace(
            content_type="text/markdown",
            path=materialized_path,
            content_hash="hash-1",
            name="drive-doc.md",
            file_id=str(file_id),
        )

    monkeypatch.setattr(node, "materialize_attachment_file", fake_materialize_attachment_file)

    content = asyncio.run(
        node.create_message_content_from_file(
            object(),
            str(user_id),
            {"id": str(file_id), "source": "google_drive"},
            False,
            http_client=object(),
        )
    )

    assert content is not None
    assert content.text is not None
    assert "[Content omitted]" in content.text
    assert "# Drive document" not in content.text


def test_create_message_content_from_image_file_includes_data_uri_even_in_reduced_view(
    monkeypatch, tmp_path
) -> None:
    file_id = uuid.uuid4()
    user_id = uuid.uuid4()
    materialized_path = tmp_path / "drive-image.png"
    materialized_path.write_bytes(b"fake-png-bytes")

    async def fake_materialize_attachment_file(pg_engine, http_client, current_user_id, file_info):
        assert current_user_id == user_id
        assert file_info == {"id": str(file_id), "source": "google_drive"}
        return SimpleNamespace(
            content_type="image/png",
            path=materialized_path,
            content_hash="hash-1",
            name="drive-image.png",
            file_id=str(file_id),
        )

    monkeypatch.setattr(node, "materialize_attachment_file", fake_materialize_attachment_file)

    content = asyncio.run(
        node.create_message_content_from_file(
            object(),
            str(user_id),
            {"id": str(file_id), "source": "google_drive"},
            False,
            http_client=object(),
        )
    )

    assert content is not None
    assert content.type == MessageContentTypeEnum.image_url
    assert content.image_url is not None
    assert content.image_url.id == str(file_id)
    assert content.image_url.url.startswith("data:image/png;base64,")


def test_create_message_content_from_cached_image_normalizes_content_type(
    monkeypatch, tmp_path
) -> None:
    file_id = uuid.uuid4()
    user_id = uuid.uuid4()
    materialized_path = tmp_path / "cached-drive-image.png"
    materialized_path.write_bytes(b"fake-png-bytes")

    async def fake_materialize_attachment_file(*_args):
        return SimpleNamespace(
            content_type="image/png; charset=binary",
            path=materialized_path,
            content_hash="hash-1",
            name="cached-drive-image.png",
            file_id=str(file_id),
        )

    monkeypatch.setattr(node, "materialize_attachment_file", fake_materialize_attachment_file)

    content = asyncio.run(
        node.create_message_content_from_file(
            object(),
            str(user_id),
            {"id": str(file_id), "source": "google_drive"},
            False,
            http_client=object(),
        )
    )

    assert content is not None
    assert content.type == MessageContentTypeEnum.image_url
    assert content.image_url is not None
    assert content.image_url.url.startswith("data:image/png;base64,")
