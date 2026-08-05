import asyncio
import logging
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable

logger = logging.getLogger("uvicorn.error")

GITHUB_COPILOT_SCOPE_ENV = "MERIDIAN_GITHUB_COPILOT_SCOPE"
SESSION_DISCONNECT_TIMEOUT_SECONDS = 5.0
CLIENT_STOP_TIMEOUT_SECONDS = 25.0
CLIENT_FORCE_STOP_TIMEOUT_SECONDS = 5.0
PROCESS_TERM_GRACE_SECONDS = 1.0
PROCESS_KILL_GRACE_SECONDS = 1.0
PROCESS_POLL_INTERVAL_SECONDS = 0.05
_PROC_ROOT = Path("/proc")


@dataclass(frozen=True)
class CopilotProcessIdentity:
    pid: int
    start_time_ticks: int


def build_scoped_copilot_env(env: dict[str, str], scope_id: str) -> dict[str, str]:
    scoped_env = env.copy()
    scoped_env[GITHUB_COPILOT_SCOPE_ENV] = scope_id
    return scoped_env


def _read_process_start_time(pid: int, proc_root: Path = _PROC_ROOT) -> int | None:
    try:
        stat = (proc_root / str(pid) / "stat").read_text()
    except (OSError, UnicodeError):
        return None

    closing_paren = stat.rfind(")")
    if closing_paren < 0:
        return None
    fields_after_command = stat[closing_paren + 1 :].split()
    try:
        return int(fields_after_command[19])
    except (IndexError, ValueError):
        return None


def _process_has_scope(pid: int, scope_id: str, proc_root: Path = _PROC_ROOT) -> bool:
    expected_entry = f"{GITHUB_COPILOT_SCOPE_ENV}={scope_id}".encode()
    try:
        environ = (proc_root / str(pid) / "environ").read_bytes()
    except OSError:
        return False
    return expected_entry in environ.split(b"\0")


def _find_scoped_processes(
    scope_id: str,
    proc_root: Path = _PROC_ROOT,
) -> set[CopilotProcessIdentity]:
    identities: set[CopilotProcessIdentity] = set()
    try:
        process_entries = list(proc_root.iterdir())
    except OSError as exc:
        logger.warning("GitHub Copilot scoped process scan unavailable: %s", exc)
        return identities

    current_pid = os.getpid()
    for entry in process_entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == current_pid or not _process_has_scope(pid, scope_id, proc_root):
            continue
        start_time = _read_process_start_time(pid, proc_root)
        if start_time is not None:
            identities.add(CopilotProcessIdentity(pid=pid, start_time_ticks=start_time))
    return identities


def _identity_is_current(
    identity: CopilotProcessIdentity,
    proc_root: Path = _PROC_ROOT,
) -> bool:
    return _read_process_start_time(identity.pid, proc_root) == identity.start_time_ticks


def _signal_process(
    identity: CopilotProcessIdentity,
    process_signal: signal.Signals,
    proc_root: Path,
) -> None:
    if not _identity_is_current(identity, proc_root):
        return
    try:
        os.kill(identity.pid, process_signal)
    except (ProcessLookupError, PermissionError):
        return


def _reap_process(identity: CopilotProcessIdentity, proc_root: Path) -> None:
    if not _identity_is_current(identity, proc_root):
        return
    try:
        os.waitpid(identity.pid, os.WNOHANG)
    except (ChildProcessError, ProcessLookupError):
        return


def _current_identities(
    identities: set[CopilotProcessIdentity],
    proc_root: Path,
) -> set[CopilotProcessIdentity]:
    return {identity for identity in identities if _identity_is_current(identity, proc_root)}


def _terminate_scoped_processes(
    scope_id: str,
    initial_identities: set[CopilotProcessIdentity] | None = None,
    *,
    proc_root: Path = _PROC_ROOT,
) -> set[CopilotProcessIdentity]:
    tracked = set(initial_identities or ())
    discovered = _find_scoped_processes(scope_id, proc_root)
    tracked.update(discovered)
    if not tracked:
        return set()

    term_signalled: set[CopilotProcessIdentity] = set()
    term_deadline = time.monotonic() + PROCESS_TERM_GRACE_SECONDS
    while True:
        discovered = _find_scoped_processes(scope_id, proc_root)
        tracked.update(discovered)
        active = _current_identities(tracked, proc_root)
        for identity in active - term_signalled:
            _signal_process(identity, signal.SIGTERM, proc_root)
            term_signalled.add(identity)
        for identity in tracked:
            _reap_process(identity, proc_root)
        if time.monotonic() >= term_deadline:
            break
        time.sleep(PROCESS_POLL_INTERVAL_SECONDS)

    kill_signalled: set[CopilotProcessIdentity] = set()
    tracked.update(_find_scoped_processes(scope_id, proc_root))
    survivors = _current_identities(tracked, proc_root)
    kill_deadline = time.monotonic() + PROCESS_KILL_GRACE_SECONDS
    while True:
        for identity in survivors - kill_signalled:
            _signal_process(identity, signal.SIGKILL, proc_root)
            kill_signalled.add(identity)
        for identity in tracked:
            _reap_process(identity, proc_root)
        if time.monotonic() >= kill_deadline:
            break
        time.sleep(PROCESS_POLL_INTERVAL_SECONDS)
        tracked.update(_find_scoped_processes(scope_id, proc_root))
        survivors = _current_identities(tracked, proc_root)

    tracked.update(_find_scoped_processes(scope_id, proc_root))
    survivors = _current_identities(tracked, proc_root)
    for identity in tracked:
        _reap_process(identity, proc_root)
    if survivors:
        logger.warning(
            "GitHub Copilot scoped cleanup left %d process(es): %s",
            len(survivors),
            sorted(identity.pid for identity in survivors),
        )
    return survivors


async def _run_bounded_cleanup(
    operation: Awaitable[Any],
    *,
    label: str,
    timeout: float,
) -> bool:
    try:
        await asyncio.wait_for(operation, timeout=timeout)
        return True
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        logger.warning("GitHub Copilot %s timed out after %.1f seconds", label, timeout)
    except Exception as exc:
        logger.warning("GitHub Copilot %s failed: %s", label, exc)
    return False


async def shutdown_copilot_runtime(
    client: Any | None,
    session: Any | None,
    scope_id: str,
) -> None:
    current_task = asyncio.current_task()
    initial_cancellation_count = current_task.cancelling() if current_task is not None else 0
    cancelled_during_cleanup = False

    def _record_new_cancellation() -> None:
        nonlocal cancelled_during_cleanup
        if current_task is not None and current_task.cancelling() > initial_cancellation_count:
            cancelled_during_cleanup = True

    try:
        initial_identities = await asyncio.to_thread(_find_scoped_processes, scope_id)
    except asyncio.CancelledError:
        _record_new_cancellation()
        initial_identities = set()
    except Exception as exc:
        logger.warning("GitHub Copilot initial scoped process scan failed: %s", exc)
        initial_identities = set()

    if session is not None:
        try:
            await _run_bounded_cleanup(
                session.disconnect(),
                label="session disconnect",
                timeout=SESSION_DISCONNECT_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            _record_new_cancellation()
        except Exception as exc:
            logger.warning("GitHub Copilot session disconnect failed: %s", exc)

    stopped = client is None
    if client is not None:
        try:
            stopped = await _run_bounded_cleanup(
                client.stop(),
                label="client stop",
                timeout=CLIENT_STOP_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            _record_new_cancellation()
            stopped = False
        except Exception as exc:
            logger.warning("GitHub Copilot client stop failed: %s", exc)
            stopped = False
        if not stopped:
            try:
                await _run_bounded_cleanup(
                    client.force_stop(),
                    label="client force stop",
                    timeout=CLIENT_FORCE_STOP_TIMEOUT_SECONDS,
                )
            except asyncio.CancelledError:
                _record_new_cancellation()
            except Exception as exc:
                logger.warning("GitHub Copilot client force stop failed: %s", exc)

    try:
        await asyncio.to_thread(
            _terminate_scoped_processes,
            scope_id,
            initial_identities,
        )
    except asyncio.CancelledError:
        _record_new_cancellation()
    except Exception as exc:
        logger.warning("GitHub Copilot scoped process cleanup failed: %s", exc)

    if cancelled_during_cleanup:
        raise asyncio.CancelledError
