import asyncio
import base64
import io
import os
import tarfile
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import SandboxSettings
from app.executor import HealthState, OutputAccumulator, SandboxExecutor
from app.main import create_app
from app.models import CodeExecutionResponse, ExecutionStatus, SandboxInputFile
from worker import bootstrap


class FakeExecutor:
    def __init__(
        self,
        health_state: HealthState | None = None,
        response: CodeExecutionResponse | None = None,
    ):
        self._health_state = health_state or HealthState(ready=True, message="ok")
        self._response = response or CodeExecutionResponse(
            execution_id="exec-1",
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="hello\n",
            stderr="",
            duration_ms=5,
            output_truncated=False,
        )
        self.cleaned = False
        self.closed = False
        self.runtime = None
        self.last_input_files: list[SandboxInputFile] = []

    def health_state(self) -> HealthState:
        return self._health_state

    def execute_python(
        self,
        code: str,
        input_files: list[SandboxInputFile] | None = None,
    ) -> CodeExecutionResponse:
        self.last_input_files = input_files or []
        return self._response

    def cleanup_stale_containers(self) -> None:
        self.cleaned = True

    def close(self) -> None:
        self.closed = True


class FakeContainer:
    def __init__(
        self,
        *,
        exit_code: int = 0,
        oom_killed: bool = False,
        wait_forever: bool = False,
        attach_stream: list[tuple[bytes | None, bytes | None]] | None = None,
        fallback_logs: bytes | str = b"",
        archive_bytes: bytes | None = None,
    ):
        self.id = "container-1"
        self.attrs = {
            "State": {
                "ExitCode": exit_code,
                "OOMKilled": oom_killed,
                "Running": False,
            }
        }
        self._wait_forever = wait_forever
        self._attach_stream = attach_stream or []
        self._fallback_logs = fallback_logs
        self._archive_bytes = archive_bytes or _build_tar_archive({})
        self.started = False
        self.killed = False
        self.removed = False
        self.logs_calls = 0
        self.put_archive_calls: list[tuple[str, bytes]] = []

    def start(self) -> None:
        self.started = True
        self.attrs["State"]["Running"] = True

    def attach(self, **kwargs: Any):
        return iter(self._attach_stream)

    def wait(self) -> dict[str, int]:
        if self._wait_forever:
            while not self.killed:
                time.sleep(0.005)
        self.attrs["State"]["Running"] = False
        return {"StatusCode": int(self.attrs["State"]["ExitCode"])}

    def reload(self) -> None:
        if self.killed:
            self.attrs["State"]["Running"] = False
            return

        if self._wait_forever:
            self.attrs["State"]["Running"] = True
            return

        self.attrs["State"]["Running"] = False

    def kill(self) -> None:
        self.killed = True
        self.attrs["State"]["Running"] = False
        if not self.attrs["State"]["OOMKilled"]:
            self.attrs["State"]["ExitCode"] = 137

    def logs(self, stdout: bool = False, stderr: bool = True):
        self.logs_calls += 1
        assert stdout is False
        assert stderr is True
        return self._fallback_logs

    def get_archive(self, path: str) -> tuple[list[bytes], dict[str, int]]:
        assert path == "/tmp/outputs"
        return [self._archive_bytes], {"size": len(self._archive_bytes)}

    def put_archive(self, path: str, data: bytes) -> bool:
        self.put_archive_calls.append((path, data))
        return True

    def remove(self, force: bool = False) -> None:
        self.removed = True
        if force:
            self.killed = True
            self.attrs["State"]["Running"] = False
            if not self.attrs["State"]["OOMKilled"]:
                self.attrs["State"]["ExitCode"] = 137


class FakeContainerManager:
    def __init__(self, containers: list[FakeContainer]):
        self._containers = containers
        self.created_kwargs: dict[str, Any] | None = None
        self.created_kwargs_history: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeContainer:
        self.created_kwargs = kwargs
        self.created_kwargs_history.append(kwargs)
        if not self._containers:
            raise AssertionError("No fake containers available for creation")
        if len(self._containers) == 1:
            return self._containers[0]
        return self._containers.pop(0)

    def list(self, **kwargs: Any) -> list[Any]:
        return []


class FakeVolume:
    def __init__(self, name: str):
        self.name = name
        self.removed = False

    def remove(self, force: bool = False) -> None:
        self.removed = True


class FakeVolumeManager:
    def __init__(self):
        self.created: list[tuple[str, dict[str, str]]] = []
        self.created_volumes: list[FakeVolume] = []

    def create(self, name: str, labels: dict[str, str]) -> FakeVolume:
        volume = FakeVolume(name)
        self.created.append((name, labels))
        self.created_volumes.append(volume)
        return volume

    def list(self, filters: dict[str, str] | None = None) -> list[FakeVolume]:
        return []


class FakeImages:
    def __init__(self, available: bool = True):
        self.available = available

    def get(self, image: str) -> None:
        if not self.available:
            from docker.errors import ImageNotFound

            raise ImageNotFound("missing")


class FakeDockerClient:
    def __init__(
        self,
        container: FakeContainer | None = None,
        *,
        containers: list[FakeContainer] | None = None,
        image_available: bool = True,
    ):
        resolved_containers = containers or [container or FakeContainer()]
        self.containers = FakeContainerManager(resolved_containers)
        self.volumes = FakeVolumeManager()
        self.images = FakeImages(available=image_available)
        self.pinged = False
        self.closed = False

    def ping(self) -> bool:
        self.pinged = True
        return True

    def info(self) -> dict[str, Any]:
        return {"Runtimes": {"runc": {"path": "runc"}}}

    def close(self) -> None:
        self.closed = True


def make_settings(**overrides: Any) -> SandboxSettings:
    base: dict[str, Any] = {
        "SANDBOX_MANAGER_PORT": 5000,
        "MAX_CONCURRENT_SANDBOXES": 1,
        "SANDBOX_QUEUE_WAIT_SECONDS": 0.01,
        "EXECUTION_TIMEOUT_SECONDS": 0.01,
        "SANDBOX_OUTPUT_LIMIT_BYTES": 8,
        "SANDBOX_CODE_MAX_BYTES": 100,
        "SANDBOX_MEMORY_LIMIT": "256m",
        "SANDBOX_CPU_NANO_CPUS": 500_000_000,
        "SANDBOX_PIDS_LIMIT": 64,
        "SANDBOX_TMPFS_SIZE": "50m",
        "SANDBOX_RUNTIME": "nsjail",
        "SANDBOX_ARTIFACT_MAX_FILES": 20,
        "SANDBOX_ARTIFACT_MAX_FILE_BYTES": 1024,
        "SANDBOX_ARTIFACT_MAX_TOTAL_BYTES": 4096,
        "SANDBOX_INPUT_MAX_FILES": 20,
        "SANDBOX_INPUT_MAX_FILE_BYTES": 1024,
        "SANDBOX_INPUT_MAX_TOTAL_BYTES": 4096,
        "SANDBOX_WORKER_IMAGE": "sandbox-python:test",
    }
    base.update(overrides)
    return SandboxSettings.model_validate(base)


def _build_tar_archive(
    files: dict[str, bytes],
    *,
    symlinks: dict[str, str] | None = None,
    extra_entries: list[tuple[str, bytes, int]] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        root = tarfile.TarInfo(name="tmp/outputs")
        root.type = tarfile.DIRTYPE
        root.mode = 0o755
        archive.addfile(root)

        for path, content in files.items():
            info = tarfile.TarInfo(name=f"tmp/outputs/{path}")
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))

        for path, target in (symlinks or {}).items():
            info = tarfile.TarInfo(name=f"tmp/outputs/{path}")
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)

        for name, content, mode in extra_entries or []:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.mode = mode
            archive.addfile(info, io.BytesIO(content))

    return buffer.getvalue()


def test_execute_endpoint_success() -> None:
    executor = FakeExecutor()
    app = create_app(settings=make_settings(), executor=executor)

    with TestClient(app) as client:
        response = client.post("/execute", json={"language": "python", "code": "print('hello')"})

    assert response.status_code == 200
    assert response.json()["stdout"] == "hello\n"
    assert executor.cleaned is True
    assert executor.closed is True


def test_execute_endpoint_forwards_input_files() -> None:
    executor = FakeExecutor()
    app = create_app(settings=make_settings(), executor=executor)

    with TestClient(app) as client:
        response = client.post(
            "/execute",
            json={
                "language": "python",
                "code": "print('hello')",
                "input_files": [
                    {
                        "relative_path": "data/example.txt",
                        "name": "example.txt",
                        "content_type": "text/plain",
                        "size": 2,
                        "content_b64": base64.b64encode(b"ok").decode("ascii"),
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert executor.last_input_files[0].relative_path == "data/example.txt"


def test_execute_endpoint_rejects_unsupported_language() -> None:
    app = create_app(settings=make_settings(), executor=FakeExecutor())

    with TestClient(app) as client:
        response = client.post(
            "/execute", json={"language": "javascript", "code": "console.log(1)"}
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only python is supported"


def test_execute_endpoint_rejects_large_payload() -> None:
    app = create_app(settings=make_settings(SANDBOX_CODE_MAX_BYTES=4), executor=FakeExecutor())

    with TestClient(app) as client:
        response = client.post("/execute", json={"language": "python", "code": "print('too big')"})

    assert response.status_code == 413


def test_execute_endpoint_returns_429_when_queue_is_full() -> None:
    app = create_app(settings=make_settings(), executor=FakeExecutor())

    with TestClient(app) as client:
        app.state.execution_semaphore = asyncio.Semaphore(0)
        response = client.post(
            "/execute",
            json={"language": "python", "code": "print('blocked')"},
        )

    assert response.status_code == 429


def test_health_endpoint_reports_unready_executor() -> None:
    app = create_app(
        settings=make_settings(),
        executor=FakeExecutor(health_state=HealthState(ready=False, message="missing image")),
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "missing image"


def test_executor_applies_required_container_isolation_flags() -> None:
    client = FakeDockerClient()
    settings = make_settings()
    executor = SandboxExecutor(settings=settings, client=client)

    kwargs = executor._build_container_kwargs(
        "exec-123",
        "print('hello')",
        "artifact-volume-1",
    )

    assert kwargs["command"][:2] == ["/bin/sh", "-lc"]
    assert "install -d -m 0777 /tmp/outputs" in kwargs["command"][2]
    assert "exec nsjail --mode o --quiet" in kwargs["command"][2]
    assert "/payload/bootstrap.py /tmp/execution.py" in kwargs["command"][2]
    assert kwargs["network_mode"] == "none"
    assert kwargs["read_only"] is True
    assert kwargs["mem_limit"] == "256m"
    assert kwargs["memswap_limit"] == "256m"
    assert kwargs["nano_cpus"] == 500_000_000
    assert kwargs["pids_limit"] == 64
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["cap_add"] == ["SYS_ADMIN", "SETUID", "SETGID", "SETPCAP"]
    assert kwargs["security_opt"] == [
        "no-new-privileges:true",
        "seccomp=unconfined",
        "apparmor=unconfined",
    ]
    assert kwargs["user"] == "root"
    assert "mode=1777" in kwargs["tmpfs"]["/tmp"]
    assert kwargs["volumes"] == {"artifact-volume-1": {"bind": "/tmp/outputs", "mode": "rw"}}
    assert kwargs["environment"]["SANDBOX_CODE_B64"] == base64.b64encode(b"print('hello')").decode(
        "ascii"
    )
    assert kwargs["environment"]["MERIDIAN_OUTPUT_DIR"] == "/tmp/outputs"
    assert kwargs["environment"]["MERIDIAN_SANDBOX_RUNTIME"] == "nsjail"
    assert kwargs["environment"]["MERIDIAN_MAX_FILE_SIZE_BYTES"] == "1024"


def test_executor_builds_nsjail_command_when_requested() -> None:
    client = FakeDockerClient()
    settings = make_settings(SANDBOX_ARTIFACT_MAX_FILE_BYTES=5 * 1024 * 1024)
    executor = SandboxExecutor(settings=settings, client=client)

    kwargs = executor._build_container_kwargs(
        "exec-123",
        "print('hello')",
        "artifact-volume-1",
    )

    shell_command = kwargs["command"][2]
    assert "nsjail --mode o --quiet" in shell_command
    assert "--chroot / --cwd /tmp" in shell_command
    assert "--disable_clone_newuser" in shell_command
    assert "--iface_no_lo" in shell_command
    assert shell_command.count("--env") == 3
    assert "SANDBOX_CODE_B64" in shell_command
    assert "MERIDIAN_OUTPUT_DIR" in shell_command
    assert "MERIDIAN_SANDBOX_RUNTIME" in shell_command
    assert "--time_limit" in shell_command
    assert "--rlimit_fsize 5" in shell_command
    assert "/usr/local/bin/python -I /payload/bootstrap.py /tmp/execution.py" in shell_command
    assert kwargs["environment"]["MERIDIAN_SANDBOX_RUNTIME"] == "nsjail"
    assert kwargs["user"] == "root"
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["cap_add"] == ["SYS_ADMIN", "SETUID", "SETGID", "SETPCAP"]
    assert kwargs["security_opt"] == [
        "no-new-privileges:true",
        "seccomp=unconfined",
        "apparmor=unconfined",
    ]
    assert "runtime" not in kwargs


def test_executor_mounts_read_only_input_volume_when_requested() -> None:
    client = FakeDockerClient()
    settings = make_settings()
    executor = SandboxExecutor(settings=settings, client=client)

    kwargs = executor._build_container_kwargs(
        "exec-123",
        "print('hello')",
        "artifact-volume-1",
        "input-volume-1",
    )

    assert kwargs["volumes"] == {
        "artifact-volume-1": {"bind": "/tmp/outputs", "mode": "rw"},
        "input-volume-1": {"bind": "/tmp/inputs", "mode": "ro"},
    }
    assert kwargs["environment"]["MERIDIAN_INPUT_DIR"] == "/tmp/inputs"
    assert "MERIDIAN_INPUT_DIR" in kwargs["command"][2]


def test_bootstrap_parses_max_file_size_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERIDIAN_MAX_FILE_SIZE_BYTES", "2048")

    assert bootstrap._get_max_file_size_bytes() == 2048


def test_bootstrap_prepares_writable_runtime_dirs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MPLBACKEND", raising=False)

    bootstrap._prepare_runtime_dirs()

    assert Path(bootstrap.SANDBOX_HOME_DIR).exists()
    assert Path(bootstrap.SANDBOX_CACHE_DIR).exists()
    assert Path(bootstrap.SANDBOX_CONFIG_DIR).exists()
    assert Path(bootstrap.SANDBOX_MPLCONFIGDIR).exists()
    assert os.environ["HOME"] == bootstrap.SANDBOX_HOME_DIR
    assert os.environ["XDG_CACHE_HOME"] == bootstrap.SANDBOX_CACHE_DIR
    assert os.environ["XDG_CONFIG_HOME"] == bootstrap.SANDBOX_CONFIG_DIR
    assert os.environ["MPLCONFIGDIR"] == bootstrap.SANDBOX_MPLCONFIGDIR
    assert os.environ["MPLBACKEND"] == "Agg"


def test_executor_rejects_non_nsjail_runtime() -> None:
    with pytest.raises(ValueError, match="Only SANDBOX_RUNTIME=nsjail is supported"):
        SandboxExecutor(
            settings=make_settings(SANDBOX_RUNTIME="runsc"),
            client=FakeDockerClient(),
        )


def test_health_endpoint_reports_nsjail_runtime() -> None:
    app = create_app(
        settings=make_settings(),
        executor=SandboxExecutor(
            settings=make_settings(),
            client=FakeDockerClient(),
        ),
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["runtime"] == "nsjail"


def test_output_accumulator_marks_truncation() -> None:
    accumulator = OutputAccumulator(limit_bytes=5)

    accumulator.add(b"hello", None)
    truncated = accumulator.add(b"world", None)

    assert truncated is True
    assert accumulator.stdout == "hello"


def test_execute_python_returns_timeout_status_and_cleans_up() -> None:
    container = FakeContainer(wait_forever=True)
    client = FakeDockerClient(container=container)
    executor = SandboxExecutor(settings=make_settings(), client=client)

    result = executor.execute_python("print('hello')")

    assert result.status == ExecutionStatus.TIMEOUT
    assert result.exit_code == 124
    assert container.killed is True
    assert container.removed is True
    assert client.containers.created_kwargs is not None
    assert client.volumes.created_volumes[0].removed is True
    assert client.containers.created_kwargs["environment"]["SANDBOX_CODE_B64"] == base64.b64encode(
        b"print('hello')"
    ).decode("ascii")


def test_execute_python_maps_oom_to_memory_limit_status() -> None:
    container = FakeContainer(exit_code=137, oom_killed=True)
    client = FakeDockerClient(container=container)
    executor = SandboxExecutor(
        settings=make_settings(EXECUTION_TIMEOUT_SECONDS=0.1),
        client=client,
    )

    result = executor.execute_python("print('hello')")

    assert result.status == ExecutionStatus.MEMORY_LIMIT_EXCEEDED


def test_execute_python_uses_fallback_stderr_logs_on_runtime_error() -> None:
    container = FakeContainer(
        exit_code=2,
        fallback_logs=b"SyntaxError: unterminated string literal\n",
    )
    client = FakeDockerClient(container=container)
    executor = SandboxExecutor(settings=make_settings(), client=client)

    result = executor.execute_python("print('hello')")

    assert result.status == ExecutionStatus.RUNTIME_ERROR
    assert result.stderr == "SyntaxError: unterminated string literal\n"
    assert container.logs_calls == 1


def test_execute_python_reports_diagnostic_when_runtime_error_has_no_logs() -> None:
    container = FakeContainer(exit_code=2, fallback_logs=b"")
    client = FakeDockerClient(container=container)
    executor = SandboxExecutor(settings=make_settings(), client=client)

    result = executor.execute_python("print('hello')")

    assert "Sandbox process exited with code 2 without stderr output." in result.stderr
    assert "NSJail startup or compatibility issue" in result.stderr
    assert container.logs_calls == 1


def test_execute_python_does_not_fetch_fallback_logs_when_stderr_was_streamed() -> None:
    container = FakeContainer(
        exit_code=2,
        attach_stream=[(None, b"streamed stderr\n")],
        fallback_logs=b"fallback stderr\n",
    )
    client = FakeDockerClient(container=container)
    executor = SandboxExecutor(
        settings=make_settings(SANDBOX_OUTPUT_LIMIT_BYTES=64),
        client=client,
    )

    result = executor.execute_python("print('hello')")

    assert result.stderr == "streamed stderr\n"
    assert container.logs_calls == 0


def test_execute_python_kills_on_output_limit() -> None:
    container = FakeContainer(wait_forever=True, attach_stream=[(b"0123456789", None)])
    client = FakeDockerClient(container=container)
    executor = SandboxExecutor(
        settings=make_settings(EXECUTION_TIMEOUT_SECONDS=0.1),
        client=client,
    )

    result = executor.execute_python("print('hello')")

    assert result.status == ExecutionStatus.OUTPUT_LIMIT_EXCEEDED
    assert result.output_truncated is True
    assert container.killed is True


def test_execute_python_stages_input_files_and_cleans_up() -> None:
    staging_container = FakeContainer()
    execution_container = FakeContainer()
    client = FakeDockerClient(containers=[staging_container, execution_container])
    executor = SandboxExecutor(settings=make_settings(), client=client)

    result = executor.execute_python(
        "print('hello')",
        [
            SandboxInputFile(
                relative_path="reports/input.txt",
                name="input.txt",
                content_type="text/plain",
                size=2,
                content_b64=base64.b64encode(b"ok").decode("ascii"),
            )
        ],
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert staging_container.put_archive_calls
    assert staging_container.put_archive_calls[0][0] == "/tmp/inputs"
    assert staging_container.removed is True
    assert execution_container.removed is True
    assert len(client.volumes.created_volumes) == 2
    assert all(volume.removed for volume in client.volumes.created_volumes)
    assert any(
        volume_config["bind"] == "/tmp/inputs" and volume_config["mode"] == "ro"
        for volume_config in client.containers.created_kwargs_history[-1]["volumes"].values()
    )


def test_execute_python_reports_invalid_input_path_as_warning() -> None:
    container = FakeContainer()
    client = FakeDockerClient(container=container)
    executor = SandboxExecutor(settings=make_settings(), client=client)

    result = executor.execute_python(
        "print('hello')",
        [
            SandboxInputFile(
                relative_path="../escape.txt",
                name="escape.txt",
                content_type="text/plain",
                size=1,
                content_b64=base64.b64encode(b"x").decode("ascii"),
            )
        ],
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert any("path was invalid" in warning for warning in result.input_warnings)
    assert len(client.volumes.created_volumes) == 1


def test_execute_python_treats_negative_input_size_limits_as_unlimited() -> None:
    staging_container = FakeContainer()
    execution_container = FakeContainer()
    client = FakeDockerClient(containers=[staging_container, execution_container])
    executor = SandboxExecutor(
        settings=make_settings(
            SANDBOX_INPUT_MAX_FILE_BYTES=-1,
            SANDBOX_INPUT_MAX_TOTAL_BYTES=-1,
        ),
        client=client,
    )

    large_payload = b"x" * 6000
    result = executor.execute_python(
        "print('hello')",
        [
            SandboxInputFile(
                relative_path="datasets/large.bin",
                name="large.bin",
                content_type="application/octet-stream",
                size=len(large_payload),
                content_b64=base64.b64encode(large_payload).decode("ascii"),
            )
        ],
    )

    assert result.status == ExecutionStatus.SUCCESS
    assert result.input_warnings == []
    assert staging_container.put_archive_calls


def test_collect_artifacts_recursively() -> None:
    executor = SandboxExecutor(
        settings=make_settings(),
        client=FakeDockerClient(),
    )

    artifacts, warnings = executor._collect_artifacts(
        FakeContainer(
            archive_bytes=_build_tar_archive(
                {
                    "plot.png": b"png-bytes",
                    "reports/table.csv": b"a,b\n1,2\n",
                }
            )
        )
    )

    assert [artifact.relative_path for artifact in artifacts] == [
        "plot.png",
        "reports/table.csv",
    ]
    assert [artifact.content_type for artifact in artifacts] == [
        "image/png",
        "text/csv",
    ]
    assert warnings == []


def test_collect_artifacts_skips_invalid_or_oversized_files() -> None:
    executor = SandboxExecutor(
        settings=make_settings(SANDBOX_ARTIFACT_MAX_FILE_BYTES=4),
        client=FakeDockerClient(),
    )

    artifacts, warnings = executor._collect_artifacts(
        FakeContainer(
            archive_bytes=_build_tar_archive(
                {
                    "large.bin": b"12345",
                    "safe.txt": b"ok",
                },
                symlinks={"linked.txt": "safe.txt"},
                extra_entries=[("tmp/outputs/../escape.txt", b"x", 0o644)],
            )
        )
    )

    assert [artifact.relative_path for artifact in artifacts] == ["safe.txt"]
    assert any("large.bin" in warning for warning in warnings)
    assert any("linked.txt" in warning for warning in warnings)
    assert any("invalid path" in warning for warning in warnings)
