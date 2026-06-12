import os
import sys
import uuid
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"

os.chdir(APP_DIR)
sys.path.append(str(APP_DIR))

from database.pg.models import Files
from routers.files import _build_id_download_filename


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
