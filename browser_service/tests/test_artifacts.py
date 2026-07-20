import hashlib
from pathlib import Path

import pytest

from browser_service.app.artifacts import (
    HASH_CHUNK_SIZE,
    build_cache_manifest,
    verify_cache_manifest,
)
from browser_service.app.camoufox_runtime import _CamoufoxLaunchError


def test_complete_cache_manifest_streams_and_detects_mutation(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    payload = root / "browser.bin"
    payload_bytes = b"a" * (HASH_CHUNK_SIZE * 2 + 17)
    payload.write_bytes(payload_bytes)
    second = root / "addon.txt"
    second.write_bytes(b"addon")
    requested_sizes = []
    original_open = Path.open

    class BoundedReader:
        def __init__(self, source) -> None:
            self.source = source

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.source.close()

        def read(self, size=-1):
            assert 0 < size <= HASH_CHUNK_SIZE
            requested_sizes.append(size)
            return self.source.read(size)

    def instrumented_open(path, mode="r", *args, **kwargs):
        source = original_open(path, mode, *args, **kwargs)
        return BoundedReader(source) if path == payload and mode == "rb" else source

    monkeypatch.setattr(Path, "open", instrumented_open)
    entries = build_cache_manifest(root)
    expected_digest = hashlib.sha256(payload_bytes).hexdigest()
    assert entries == [
        f"{hashlib.sha256(b'addon').hexdigest()}  addon.txt  5",
        f"{expected_digest}  browser.bin  {len(payload_bytes)}",
    ]
    assert len(requested_sizes) >= 4
    assert set(requested_sizes) == {HASH_CHUNK_SIZE}
    manifest = tmp_path / "manifest"
    manifest.write_text("\n".join(entries) + "\n")
    verify_cache_manifest(root, manifest)
    payload.write_bytes(b"mutated")
    with pytest.raises(_CamoufoxLaunchError):
        verify_cache_manifest(root, manifest)
