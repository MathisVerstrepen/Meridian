import asyncio
import contextlib
import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger("uvicorn.error")

RUNTIME_HEARTBEAT_FILENAME = ".meridian-runtime-active"
RUNTIME_HEARTBEAT_INTERVAL_SECONDS = 60.0
RUNTIME_CLEANUP_INTERVAL_SECONDS = 300.0

_RUNTIME_CLEANUP_CONFIGS: dict[tuple[str, str], tuple[Path, str, float, str]] = {}
_RUNTIME_CLEANUP_TASK: asyncio.Task[None] | None = None


def touch_runtime_heartbeat(root_dir: Path) -> None:
    heartbeat_path = root_dir / RUNTIME_HEARTBEAT_FILENAME
    heartbeat_path.touch(exist_ok=True)


def get_runtime_activity_mtime(runtime_dir: Path) -> float:
    heartbeat_path = runtime_dir / RUNTIME_HEARTBEAT_FILENAME
    stat_target = heartbeat_path if heartbeat_path.is_file() else runtime_dir
    return stat_target.stat().st_mtime


def is_runtime_dir_stale(runtime_dir: Path, *, now: float, ttl_seconds: float) -> bool:
    return (now - get_runtime_activity_mtime(runtime_dir)) > ttl_seconds


def _cleanup_stale_runtime_dirs_once(
    root_dir: Path,
    *,
    prefix: str,
    ttl_seconds: float,
    provider_label: str,
) -> None:
    now = time.time()
    for runtime_dir in root_dir.glob(f"{prefix}*"):
        try:
            if not runtime_dir.is_dir():
                continue
            if is_runtime_dir_stale(runtime_dir, now=now, ttl_seconds=ttl_seconds):
                shutil.rmtree(runtime_dir, ignore_errors=True)
        except Exception:
            logger.warning(
                "Failed to clean stale %s runtime dir %s",
                provider_label,
                runtime_dir,
                exc_info=True,
            )


async def _runtime_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(RUNTIME_CLEANUP_INTERVAL_SECONDS)
        for root_dir, prefix, ttl_seconds, provider_label in tuple(
            _RUNTIME_CLEANUP_CONFIGS.values()
        ):
            _cleanup_stale_runtime_dirs_once(
                root_dir,
                prefix=prefix,
                ttl_seconds=ttl_seconds,
                provider_label=provider_label,
            )


def ensure_runtime_cleanup_registered(
    root_dir: Path,
    *,
    prefix: str,
    ttl_seconds: float,
    provider_label: str,
) -> None:
    global _RUNTIME_CLEANUP_TASK

    cache_key = (str(root_dir), prefix)
    if cache_key not in _RUNTIME_CLEANUP_CONFIGS:
        _RUNTIME_CLEANUP_CONFIGS[cache_key] = (root_dir, prefix, ttl_seconds, provider_label)
        _cleanup_stale_runtime_dirs_once(
            root_dir,
            prefix=prefix,
            ttl_seconds=ttl_seconds,
            provider_label=provider_label,
        )

    if _RUNTIME_CLEANUP_TASK is not None and not _RUNTIME_CLEANUP_TASK.done():
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    _RUNTIME_CLEANUP_TASK = loop.create_task(_runtime_cleanup_loop())


async def _heartbeat_runtime_dir(root_dir: Path, interval_seconds: float) -> None:
    while True:
        try:
            touch_runtime_heartbeat(root_dir)
        except FileNotFoundError:
            return
        except Exception:
            logger.warning(
                "Failed to touch runtime heartbeat for %s",
                root_dir,
                exc_info=True,
            )
            return

        await asyncio.sleep(interval_seconds)


def start_runtime_heartbeat(root_dir: Path) -> asyncio.Task[None]:
    touch_runtime_heartbeat(root_dir)
    return asyncio.create_task(_heartbeat_runtime_dir(root_dir, RUNTIME_HEARTBEAT_INTERVAL_SECONDS))


async def stop_runtime_heartbeat(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return

    if not task.done():
        task.cancel()

    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task
