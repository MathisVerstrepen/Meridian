import asyncio
import contextlib
import logging
from pathlib import Path

logger = logging.getLogger("uvicorn.error")

RUNTIME_HEARTBEAT_FILENAME = ".meridian-runtime-active"
RUNTIME_HEARTBEAT_INTERVAL_SECONDS = 60.0


def touch_runtime_heartbeat(root_dir: Path) -> None:
    heartbeat_path = root_dir / RUNTIME_HEARTBEAT_FILENAME
    heartbeat_path.touch(exist_ok=True)


def get_runtime_activity_mtime(runtime_dir: Path) -> float:
    heartbeat_path = runtime_dir / RUNTIME_HEARTBEAT_FILENAME
    stat_target = heartbeat_path if heartbeat_path.is_file() else runtime_dir
    return stat_target.stat().st_mtime


def is_runtime_dir_stale(runtime_dir: Path, *, now: float, ttl_seconds: float) -> bool:
    return (now - get_runtime_activity_mtime(runtime_dir)) > ttl_seconds


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
