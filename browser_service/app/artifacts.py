import hashlib
from pathlib import Path

from .camoufox_runtime import _CamoufoxLaunchError

CACHE_ROOT = Path.home() / ".cache" / "camoufox"
CACHE_MANIFEST = Path(__file__).with_name("camoufox_cache_manifest.sha256")
HASH_CHUNK_SIZE = 1024 * 1024


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def build_cache_manifest(root: Path = CACHE_ROOT) -> list[str]:
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = _sha256_file(path)
        entries.append(f"{digest}  {path.relative_to(root).as_posix()}  {path.stat().st_size}")
    return entries


def verify_cache_manifest(root: Path = CACHE_ROOT, manifest: Path = CACHE_MANIFEST) -> None:
    try:
        expected = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line]
    except OSError:
        raise _CamoufoxLaunchError("Camoufox cache manifest is unavailable") from None
    if not expected or build_cache_manifest(root) != expected:
        raise _CamoufoxLaunchError("Camoufox cache manifest verification failed")
