import base64
import logging
import math
import mimetypes
import shlex
import tempfile
import tarfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound, NotFound
from requests import RequestException  # type: ignore[import-untyped]

from app.config import SandboxSettings
from app.models import CodeExecutionResponse, ExecutionStatus, SandboxArtifact

logger = logging.getLogger("uvicorn.error")

SANDBOX_LABEL_KEY = "meridian.sandbox"
SANDBOX_CODE_ENV_VAR = "SANDBOX_CODE_B64"
SANDBOX_OUTPUT_DIR_ENV_VAR = "MERIDIAN_OUTPUT_DIR"
SANDBOX_RUNTIME_ENV_VAR = "MERIDIAN_SANDBOX_RUNTIME"
SANDBOX_MAX_FILE_SIZE_ENV_VAR = "MERIDIAN_MAX_FILE_SIZE_BYTES"
SANDBOX_OUTPUT_DIR = "/tmp/outputs"
NSJAIL_RUNTIME = "nsjail"
SANDBOX_ARTIFACT_VOLUME_LABEL_KEY = "meridian.sandbox.artifact_volume"
SANDBOX_USER_ID = 1000
SANDBOX_GROUP_ID = 1000
WORKER_BOOTSTRAP_PATH = "/payload/bootstrap.py"
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
        if configured_runtime != NSJAIL_RUNTIME:
            raise ValueError("Only SANDBOX_RUNTIME=nsjail is supported for sandbox execution")
        return NSJAIL_RUNTIME

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

        try:
            volumes = self.client.volumes.list(
                filters={"label": f"{SANDBOX_ARTIFACT_VOLUME_LABEL_KEY}=true"}
            )
        except DockerException as exc:
            logger.warning("Failed to list stale sandbox artifact volumes: %s", exc)
            return

        for volume in volumes:
            try:
                volume.remove(force=True)
            except DockerException as exc:
                logger.warning(
                    "Failed to remove stale sandbox artifact volume %s: %s",
                    getattr(volume, "name", "<unknown>"),
                    exc,
                )

    def execute_python(self, code: str) -> CodeExecutionResponse:
        execution_id = uuid.uuid4().hex
        started_at = time.perf_counter()
        container = None
        artifact_volume = None
        output = OutputAccumulator(self.settings.sandbox_output_limit_bytes)
        output_limit_reached = threading.Event()

        try:
            artifact_volume = self._create_artifact_volume(execution_id)
            container_kwargs = self._build_container_kwargs(
                execution_id,
                code,
                artifact_volume.name,
            )
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

            artifacts, artifact_warnings = self._collect_artifacts(container)

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
            if artifact_volume is not None:
                try:
                    artifact_volume.remove(force=True)
                except (DockerException, NotFound):
                    pass

    def _create_artifact_volume(self, execution_id: str) -> Any:
        return self.client.volumes.create(
            name=f"meridian-sandbox-artifacts-{execution_id}",
            labels={
                SANDBOX_ARTIFACT_VOLUME_LABEL_KEY: "true",
                "meridian.execution_id": execution_id,
            },
        )

    def _build_container_kwargs(
        self,
        execution_id: str,
        code: str,
        artifact_volume_name: str,
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
                SANDBOX_MAX_FILE_SIZE_ENV_VAR: str(
                    self.settings.sandbox_artifact_max_file_bytes
                ),
            },
            "volumes": {
                artifact_volume_name: {
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
            "user": "root",
            "labels": {
                SANDBOX_LABEL_KEY: "true",
                "meridian.execution_id": execution_id,
            },
        }

        kwargs["cap_add"] = NSJAIL_OUTER_CONTAINER_CAPABILITIES
        kwargs["security_opt"] = [
            "no-new-privileges:true",
            "seccomp=unconfined",
            "apparmor=unconfined",
        ]

        return kwargs

    def _build_worker_command(self) -> list[str]:
        nsjail_file_size_limit_mb = max(
            1,
            math.ceil(self.settings.sandbox_artifact_max_file_bytes / (1024 * 1024)),
        )
        python_command = [
            NSJAIL_PYTHON_EXECUTABLE,
            "-I",
            WORKER_BOOTSTRAP_PATH,
            "/tmp/execution.py",
        ]
        nsjail_command = [
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
        worker_setup = (
            f"install -d -m 0777 {shlex.quote(SANDBOX_OUTPUT_DIR)} && "
            f"exec {shlex.join(nsjail_command)}"
        )
        return [
            "/bin/sh",
            "-lc",
            worker_setup,
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

        runtime_name = self.runtime or NSJAIL_RUNTIME
        diagnostic = f"Sandbox process exited with code {exit_code} without stderr output."
        if runtime_name == NSJAIL_RUNTIME:
            diagnostic += (
                " This can indicate an NSJail startup or compatibility issue inside the worker "
                "image."
            )
        return diagnostic

    def _collect_artifacts(self, container: Any) -> tuple[list[SandboxArtifact], list[str]]:
        warnings: list[str] = []
        try:
            archive_stream, _ = container.get_archive(SANDBOX_OUTPUT_DIR)
        except NotFound:
            return [], warnings
        except (DockerException, OSError, RequestException) as exc:
            logger.warning(
                "Failed to fetch sandbox artifacts from container %s: %s",
                container.id,
                exc,
            )
            return [], ["Failed to collect sandbox artifacts from the execution container."]

        artifacts: list[SandboxArtifact] = []
        total_size = 0
        file_count = 0
        with tempfile.SpooledTemporaryFile() as archive_file:
            for chunk in archive_stream:
                archive_file.write(chunk)
            archive_file.seek(0)

            try:
                with tarfile.open(fileobj=archive_file, mode="r:*") as archive:
                    for member in archive:
                        relative_path = self._normalize_artifact_path(member.name)
                        if relative_path == "":
                            continue

                        if relative_path is None:
                            if member.name.strip("./"):
                                warnings.append(
                                    "Skipped sandbox artifact with invalid path "
                                    f"'{member.name}'."
                                )
                            continue

                        if member.isdir():
                            continue

                        if not member.isreg():
                            warnings.append(
                                f"Skipped non-regular sandbox artifact '{relative_path}'."
                            )
                            continue

                        if file_count >= self.settings.sandbox_artifact_max_files:
                            warnings.append(
                                "Skipped sandbox artifacts because the file count limit "
                                "was reached."
                            )
                            break

                        member_size = member.size
                        if member_size > self.settings.sandbox_artifact_max_file_bytes:
                            warnings.append(
                                "Skipped sandbox artifact "
                                f"'{relative_path}' because it exceeded the per-file size limit."
                            )
                            continue

                        if (
                            total_size + member_size
                            > self.settings.sandbox_artifact_max_total_bytes
                        ):
                            warnings.append(
                                "Skipped sandbox artifacts because the total artifact size "
                                "limit was reached."
                            )
                            break

                        member_file = archive.extractfile(member)
                        if member_file is None:
                            warnings.append(
                                f"Skipped unreadable sandbox artifact '{relative_path}'."
                            )
                            continue

                        content = member_file.read()
                        content_type = (
                            mimetypes.guess_type(relative_path)[0] or "application/octet-stream"
                        )
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
            except tarfile.TarError as exc:
                logger.warning(
                    "Failed to decode sandbox artifacts from container %s: %s",
                    container.id,
                    exc,
                )
                return [], ["Failed to decode sandbox artifacts from the execution container."]

        return artifacts, warnings

    def _normalize_artifact_path(self, member_name: str) -> str | None:
        raw_path = member_name.lstrip("/")
        if not raw_path:
            return None

        parts = [part for part in PurePosixPath(raw_path).parts if part not in ("", ".")]
        if not parts:
            return None

        output_parts = PurePosixPath(SANDBOX_OUTPUT_DIR.lstrip("/")).parts
        output_name = PurePosixPath(SANDBOX_OUTPUT_DIR).name
        if len(parts) >= len(output_parts) and tuple(parts[: len(output_parts)]) == output_parts:
            parts = parts[len(output_parts):]
        elif parts[0] == output_name:
            parts = parts[1:]

        if not parts:
            return ""

        if any(part == ".." for part in parts):
            return None

        return PurePosixPath(*parts).as_posix()

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
