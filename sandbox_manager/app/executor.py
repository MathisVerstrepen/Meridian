import base64
import logging
import math
import mimetypes
import os
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound, NotFound
from requests import RequestException  # type: ignore[import-untyped]

from app.config import SandboxSettings
from app.models import CodeExecutionResponse, ExecutionStatus, SandboxArtifact
from worker.bootstrap import render_worker_bootstrap

logger = logging.getLogger("uvicorn.error")

SANDBOX_LABEL_KEY = "meridian.sandbox"
SANDBOX_CODE_ENV_VAR = "SANDBOX_CODE_B64"
SANDBOX_OUTPUT_DIR_ENV_VAR = "MERIDIAN_OUTPUT_DIR"
SANDBOX_RUNTIME_ENV_VAR = "MERIDIAN_SANDBOX_RUNTIME"
SANDBOX_OUTPUT_DIR = "/tmp/outputs"
NSJAIL_RUNTIME = "nsjail"
RUNSC_RUNTIME = "runsc"
SANDBOX_USER_NAME = "sandboxuser"
SANDBOX_USER_ID = 1000
SANDBOX_GROUP_ID = 1000
NSJAIL_OUTER_CONTAINER_CAPABILITIES = ["SYS_ADMIN", "SETUID", "SETGID", "SETPCAP"]
NSJAIL_PYTHON_EXECUTABLE = "/usr/local/bin/python"
WAIT_POLL_INTERVAL_SECONDS = 0.1
POST_TERMINATION_GRACE_SECONDS = 2.0
FALLBACK_TERMINATION_EXIT_CODE = 137


@dataclass
class HealthState:
    ready: bool
    message: str


class OutputAccumulator:
    def __init__(self, limit_bytes: int):
        self.limit_bytes = limit_bytes
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._captured = 0
        self.truncated = False
        self._lock = threading.Lock()

    def add(self, stdout_chunk: bytes | None, stderr_chunk: bytes | None) -> bool:
        with self._lock:
            if stdout_chunk:
                self._append(self._stdout, stdout_chunk)
            if stderr_chunk:
                self._append(self._stderr, stderr_chunk)
            return self.truncated

    def _append(self, buffer: bytearray, chunk: bytes) -> None:
        remaining = self.limit_bytes - self._captured
        if remaining <= 0:
            self.truncated = True
            return

        if len(chunk) > remaining:
            buffer.extend(chunk[:remaining])
            self._captured += remaining
            self.truncated = True
            return

        buffer.extend(chunk)
        self._captured += len(chunk)

    @property
    def stdout(self) -> str:
        return self._stdout.decode("utf-8", errors="replace")

    @property
    def stderr(self) -> str:
        return self._stderr.decode("utf-8", errors="replace")


class SandboxExecutor:
    def __init__(self, settings: SandboxSettings, client: Any | None = None):
        self.settings = settings
        self.client = client or docker.from_env()  # type: ignore[attr-defined]
        self.runtime = self._resolve_runtime()

    def close(self) -> None:
        self.client.close()

    def _resolve_runtime(self) -> str | None:
        configured_runtime = (self.settings.sandbox_runtime or "").strip().lower()
        if configured_runtime:
            return configured_runtime

        try:
            info = self.client.info()
        except (AttributeError, DockerException):
            return None

        runtimes = info.get("Runtimes")
        if isinstance(runtimes, dict) and RUNSC_RUNTIME in runtimes:
            return RUNSC_RUNTIME

        return None

    def health_state(self) -> HealthState:
        try:
            self.client.ping()
            self.client.images.get(self.settings.sandbox_worker_image)
        except ImageNotFound:
            return HealthState(
                ready=False,
                message=f"Worker image '{self.settings.sandbox_worker_image}' is not available",
            )
        except DockerException as exc:
            return HealthState(ready=False, message=f"Docker is unavailable: {exc}")

        return HealthState(ready=True, message="ok")

    def cleanup_stale_containers(self) -> None:
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"label": f"{SANDBOX_LABEL_KEY}=true"},
            )
        except DockerException as exc:
            logger.warning("Failed to list stale sandbox containers: %s", exc)
            return

        for container in containers:
            try:
                container.remove(force=True)
            except DockerException as exc:
                logger.warning("Failed to remove stale sandbox container %s: %s", container.id, exc)

    def execute_python(self, code: str) -> CodeExecutionResponse:
        execution_id = uuid.uuid4().hex
        started_at = time.perf_counter()
        container = None
        host_output_dir = self._create_host_output_dir(execution_id)
        output = OutputAccumulator(self.settings.sandbox_output_limit_bytes)
        output_limit_reached = threading.Event()

        try:
            container_kwargs = self._build_container_kwargs(execution_id, code, host_output_dir)
            container = self.client.containers.create(**container_kwargs)
            container.start()

            log_thread = threading.Thread(
                target=self._consume_logs,
                args=(container, output, output_limit_reached),
                daemon=True,
            )
            log_thread.start()

            timed_out, state = self._wait_for_completion(
                container,
                output_limit_reached,
            )
            log_thread.join(timeout=POST_TERMINATION_GRACE_SECONDS)
            exit_code = state.get("ExitCode")
            stderr = self._resolve_stderr(container, output.stderr, exit_code)
            status = self._resolve_status(
                exit_code=exit_code,
                oom_killed=bool(state.get("OOMKilled")),
                timed_out=timed_out,
                output_limit_reached=output_limit_reached.is_set(),
            )
            duration_ms = int((time.perf_counter() - started_at) * 1000)

            logger.info(
                "Sandbox execution %s finished status=%s exit_code=%s duration_ms=%s",
                execution_id,
                status.value,
                exit_code,
                duration_ms,
            )

            artifacts, artifact_warnings = self._collect_artifacts(host_output_dir)

            if timed_out:
                exit_code = 124
            elif output_limit_reached.is_set() and exit_code in (None, 0):
                exit_code = FALLBACK_TERMINATION_EXIT_CODE

            return CodeExecutionResponse(
                execution_id=execution_id,
                status=status,
                exit_code=exit_code,
                stdout=output.stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                output_truncated=output.truncated,
                artifacts=artifacts,
                artifact_warnings=artifact_warnings,
            )
        except (DockerException, OSError, RequestException, ValueError) as exc:
            logger.exception("Sandbox execution %s failed", execution_id)
            raise RuntimeError(f"Sandbox execution failed: {exc}") from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except (DockerException, NotFound):
                    pass
            shutil.rmtree(host_output_dir, ignore_errors=True)

    def _create_host_output_dir(self, execution_id: str) -> Path:
        host_output_root = Path(self.settings.sandbox_host_output_root)
        host_output_root.mkdir(parents=True, exist_ok=True)
        host_output_dir = Path(
            tempfile.mkdtemp(
                prefix=f"meridian-sandbox-{execution_id}-",
                dir=str(host_output_root),
            )
        )
        os.chmod(host_output_dir, 0o777)
        return host_output_dir

    def _build_container_kwargs(
        self,
        execution_id: str,
        code: str,
        host_output_dir: Path,
    ) -> dict[str, Any]:
        encoded_code = base64.b64encode(code.encode("utf-8")).decode("ascii")
        command = self._build_worker_command()
        kwargs: dict[str, Any] = {
            "image": self.settings.sandbox_worker_image,
            "command": command,
            "detach": True,
            "working_dir": "/tmp",
            "environment": {
                SANDBOX_CODE_ENV_VAR: encoded_code,
                SANDBOX_OUTPUT_DIR_ENV_VAR: SANDBOX_OUTPUT_DIR,
                SANDBOX_RUNTIME_ENV_VAR: self.runtime or "",
            },
            "volumes": {
                str(host_output_dir): {
                    "bind": SANDBOX_OUTPUT_DIR,
                    "mode": "rw",
                }
            },
            "network_mode": "none",
            "mem_limit": self.settings.sandbox_memory_limit,
            "memswap_limit": self.settings.sandbox_memory_limit,
            "nano_cpus": self.settings.sandbox_cpu_nano_cpus,
            "pids_limit": self.settings.sandbox_pids_limit,
            "read_only": True,
            "tmpfs": {
                "/tmp": (
                    f"rw,noexec,nosuid,nodev,mode=1777,size={self.settings.sandbox_tmpfs_size}"
                ),
            },
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "user": "root" if self.runtime == NSJAIL_RUNTIME else SANDBOX_USER_NAME,
            "labels": {
                SANDBOX_LABEL_KEY: "true",
                "meridian.execution_id": execution_id,
            },
        }

        if self.runtime == NSJAIL_RUNTIME:
            kwargs["cap_add"] = NSJAIL_OUTER_CONTAINER_CAPABILITIES
            kwargs["security_opt"] = [
                "no-new-privileges:true",
                "seccomp=unconfined",
                "apparmor=unconfined",
            ]

        if self.runtime and self.runtime != NSJAIL_RUNTIME:
            kwargs["runtime"] = self.runtime

        return kwargs

    def _build_worker_command(self) -> list[str]:
        nsjail_file_size_limit_mb = max(
            1,
            math.ceil(self.settings.sandbox_artifact_max_file_bytes / (1024 * 1024)),
        )
        python_command = [
            NSJAIL_PYTHON_EXECUTABLE if self.runtime == NSJAIL_RUNTIME else "python",
            "-I",
            "-c",
            render_worker_bootstrap(
                self.settings.sandbox_pids_limit,
                self.settings.sandbox_artifact_max_file_bytes,
            ),
            "/tmp/execution.py",
        ]
        if self.runtime != NSJAIL_RUNTIME:
            return python_command

        return [
            "nsjail",
            "--mode",
            "o",
            "--quiet",
            "--chroot",
            "/",
            "--cwd",
            "/tmp",
            "--disable_proc",
            "--disable_clone_newuser",
            "--iface_no_lo",
            "--user",
            str(SANDBOX_USER_ID),
            "--group",
            str(SANDBOX_GROUP_ID),
            "--env",
            SANDBOX_CODE_ENV_VAR,
            "--env",
            SANDBOX_OUTPUT_DIR_ENV_VAR,
            "--env",
            SANDBOX_RUNTIME_ENV_VAR,
            "--time_limit",
            str(max(1, int(self.settings.execution_timeout_seconds) + 1)),
            "--rlimit_fsize",
            str(nsjail_file_size_limit_mb),
            "--",
            *python_command,
        ]

    def _wait_for_completion(
        self,
        container: Any,
        output_limit_reached: threading.Event,
    ) -> tuple[bool, dict[str, Any]]:
        deadline = time.monotonic() + self.settings.execution_timeout_seconds
        wait_result: dict[str, Any] = {}
        wait_error: dict[str, BaseException] = {}
        wait_finished = threading.Event()

        def wait_for_exit() -> None:
            try:
                wait_result.update(container.wait())
            except BaseException as exc:  # pragma: no cover - propagated to caller
                wait_error["exception"] = exc
            finally:
                wait_finished.set()

        threading.Thread(target=wait_for_exit, daemon=True).start()

        while True:
            if wait_finished.wait(timeout=WAIT_POLL_INTERVAL_SECONDS):
                if "exception" in wait_error:
                    raise wait_error["exception"]

                status_code = wait_result.get("StatusCode")
                try:
                    container.reload()
                    state = container.attrs.get("State", {})
                except NotFound:
                    state = self._terminated_state({"ExitCode": status_code})

                if status_code is not None and state.get("ExitCode") is None:
                    state["ExitCode"] = status_code
                return False, state

            if output_limit_reached.is_set():
                return False, self._terminate_running_container(
                    container,
                    wait_finished,
                    wait_result,
                    wait_error,
                )

            if time.monotonic() >= deadline:
                return True, self._terminate_running_container(
                    container,
                    wait_finished,
                    wait_result,
                    wait_error,
                )

    def _terminate_running_container(
        self,
        container: Any,
        wait_finished: threading.Event,
        wait_result: dict[str, Any],
        wait_error: dict[str, BaseException],
    ) -> dict[str, Any]:
        try:
            container.kill()
        except NotFound:
            return self._terminated_state(wait_result)
        except (DockerException, OSError, RequestException) as exc:
            logger.warning("Failed to stop sandbox container %s cleanly: %s", container.id, exc)
            return self._terminated_state(wait_result)

        if wait_finished.wait(timeout=POST_TERMINATION_GRACE_SECONDS):
            if "exception" in wait_error:
                raise wait_error["exception"]

        try:
            container.reload()
            state = container.attrs.get("State", {})
        except NotFound:
            state = self._terminated_state(wait_result)

        status_code = wait_result.get("StatusCode")
        if status_code is not None and state.get("ExitCode") is None:
            state["ExitCode"] = status_code
        return self._terminated_state(state)

    def _terminated_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "ExitCode": state.get("ExitCode", FALLBACK_TERMINATION_EXIT_CODE),
            "OOMKilled": bool(state.get("OOMKilled", False)),
            "Running": False,
        }

    def _consume_logs(
        self,
        container: Any,
        output: OutputAccumulator,
        output_limit_reached: threading.Event,
    ) -> None:
        try:
            log_stream = container.attach(
                stream=True,
                stdout=True,
                stderr=True,
                logs=True,
                demux=True,
            )
            for stdout_chunk, stderr_chunk in log_stream:
                if output.add(stdout_chunk, stderr_chunk):
                    output_limit_reached.set()
                    break
        except (DockerException, OSError, RequestException) as exc:
            logger.warning("Failed to stream sandbox logs: %s", exc)

    def _resolve_stderr(
        self,
        container: Any,
        streamed_stderr: str,
        exit_code: int | None,
    ) -> str:
        if streamed_stderr.strip() or exit_code in (None, 0):
            return streamed_stderr

        try:
            raw_logs = container.logs(stdout=False, stderr=True)
        except (DockerException, OSError, RequestException) as exc:
            logger.warning(
                "Failed to fetch fallback stderr logs for sandbox container %s: %s",
                container.id,
                exc,
            )
            return streamed_stderr

        if isinstance(raw_logs, bytes):
            fallback_stderr = raw_logs.decode("utf-8", errors="replace")
        else:
            fallback_stderr = str(raw_logs)

        if fallback_stderr.strip():
            return fallback_stderr

        runtime_name = self.runtime or "default"
        diagnostic = f"Sandbox process exited with code {exit_code} without stderr output."
        if runtime_name == RUNSC_RUNTIME:
            diagnostic += (
                " This often indicates a runsc/gVisor compatibility issue with native-extension "
                "Python packages such as numpy or matplotlib."
            )
        elif runtime_name == NSJAIL_RUNTIME:
            diagnostic += (
                " This can indicate an NSJail startup or compatibility issue inside the worker "
                "image."
            )
        return diagnostic

    def _collect_artifacts(self, host_output_dir: Path) -> tuple[list[SandboxArtifact], list[str]]:
        warnings: list[str] = []

        artifacts: list[SandboxArtifact] = []
        total_size = 0
        file_count = 0
        for artifact_path in sorted(host_output_dir.rglob("*")):
            if artifact_path.is_dir():
                continue

            try:
                relative_path = artifact_path.relative_to(host_output_dir).as_posix()
            except ValueError:
                continue

            if artifact_path.is_symlink() or not artifact_path.is_file():
                warnings.append(f"Skipped non-regular sandbox artifact '{relative_path}'.")
                continue

            if file_count >= self.settings.sandbox_artifact_max_files:
                warnings.append(
                    "Skipped sandbox artifacts because the file count limit was reached."
                )
                break

            member_size = artifact_path.stat().st_size
            if member_size > self.settings.sandbox_artifact_max_file_bytes:
                warnings.append(
                    "Skipped sandbox artifact "
                    f"'{relative_path}' because it exceeded the per-file size limit."
                )
                continue

            if total_size + member_size > self.settings.sandbox_artifact_max_total_bytes:
                warnings.append(
                    "Skipped sandbox artifacts because the total artifact size "
                    "limit was reached."
                )
                break

            content = artifact_path.read_bytes()
            content_type = mimetypes.guess_type(relative_path)[0] or "application/octet-stream"

            artifacts.append(
                SandboxArtifact(
                    relative_path=relative_path,
                    name=PurePosixPath(relative_path).name,
                    content_type=content_type,
                    size=len(content),
                    content_b64=base64.b64encode(content).decode("ascii"),
                )
            )
            total_size += len(content)
            file_count += 1

        return artifacts, warnings

    def _resolve_status(
        self,
        *,
        exit_code: int | None,
        oom_killed: bool,
        timed_out: bool,
        output_limit_reached: bool,
    ) -> ExecutionStatus:
        if timed_out:
            return ExecutionStatus.TIMEOUT
        if output_limit_reached:
            return ExecutionStatus.OUTPUT_LIMIT_EXCEEDED
        if oom_killed:
            return ExecutionStatus.MEMORY_LIMIT_EXCEEDED
        if exit_code == 0:
            return ExecutionStatus.SUCCESS
        return ExecutionStatus.RUNTIME_ERROR
