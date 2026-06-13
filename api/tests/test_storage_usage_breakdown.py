import os
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"

os.chdir(APP_DIR)
sys.path.append(str(APP_DIR))

from database.pg.user_ops.storage_crud import _classify_storage_usage_item


def test_classify_storage_usage_generated_images() -> None:
    assert _classify_storage_usage_item("generated_images/image.png", "image/png") == "generated_images"


def test_classify_storage_usage_generated_videos() -> None:
    assert _classify_storage_usage_item("generated_videos/video.mov", "video/quicktime") == "generated_videos"


def test_classify_storage_usage_artifacts() -> None:
    assert _classify_storage_usage_item("generated_files/code_execution/run/output.html", "text/html") == "artifacts"


def test_classify_storage_usage_regular_video() -> None:
    assert _classify_storage_usage_item("upload.webm", "video/webm; charset=binary") == "videos"


def test_classify_storage_usage_regular_image() -> None:
    assert _classify_storage_usage_item("upload.webp", "image/webp") == "images"


def test_classify_storage_usage_document() -> None:
    assert _classify_storage_usage_item("notes.txt", "text/plain") == "documents"


def test_classify_storage_usage_upload_fallback() -> None:
    assert _classify_storage_usage_item("archive.bin", "application/octet-stream") == "uploads"
