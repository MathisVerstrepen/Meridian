import asyncio
import base64
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import SandboxSettings
from app.executor import HealthState, OutputAccumulator, SandboxExecutor
from app.main import create_app
from app.models import CodeExecutionResponse, ExecutionStatus
from worker.bootstrap import render_worker_bootstrap


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

    def health_state(self) -> HealthState:
        return self._health_state

    def execute_python(self, code: str) -> CodeExecutionResponse:
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
        self.started = False
        self.killed = False
        self.removed = False
        self.logs_calls = 0

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

    def remove(self, force: bool = False) -> None:
        self.removed = True
        if force:
            self.killed = True
            self.attrs["State"]["Running"] = False
            if not self.attrs["State"]["OOMKilled"]:
                self.attrs["State"]["ExitCode"] = 137


class FakeContainerManager:
    def __init__(self, container: FakeContainer):
        self._container = container
        self.created_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> FakeContainer:
        self.created_kwargs = kwargs
        return self._container

    def list(self, **kwargs: Any) -> list[Any]:
        return []

    def get(self, container_id: str) -> FakeContainer:
        assert container_id == self._container.id
        return self._container


class FakeImages:
    def __init__(self, available: bool = True):
        self.available = available

    def get(self, image: str) -> None:
        if not self.available:
            from docker.errors import ImageNotFound

            raise ImageNotFound("missing")


class FakeDockerClient:
    def __init__(self, container: FakeContainer | None = None, image_available: bool = True):
        self.containers = FakeContainerManager(container or FakeContainer())
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
        "SANDBOX_HOST_OUTPUT_ROOT": "/tmp/meridian-sandbox-shared",
        "SANDBOX_ARTIFACT_MAX_FILES": 20,
        "SANDBOX_ARTIFACT_MAX_FILE_BYTES": 1024,
        "SANDBOX_ARTIFACT_MAX_TOTAL_BYTES": 4096,
        "SANDBOX_WORKER_IMAGE": "sandbox-python:test",
    }
    base.update(overrides)
    return SandboxSettings.model_validate(base)


def test_execute_endpoint_success() -> None:
    executor = FakeExecutor()
    app = create_app(settings=make_settings(), executor=executor)

    with TestClient(app) as client:
        response = client.post("/execute", json={"language": "python", "code": "print('hello')"})

    assert response.status_code == 200
    assert response.json()["stdout"] == "hello\n"
    assert executor.cleaned is True
    assert executor.closed is True


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
    settings = make_settings(SANDBOX_RUNTIME="runsc")
    executor = SandboxExecutor(settings=settings, client=client)

    kwargs = executor._build_container_kwargs(
        "exec-123",
        "print('hello')",
        Path("/tmp/test-output"),
    )

    assert kwargs["command"][:3] == ["python", "-I", "-c"]
    assert "run_payload.py" not in kwargs["command"][3]
    assert "os.environ.pop(CODE_ENV_VAR, None)" in kwargs["command"][3]
    assert 'os.environ["HOME"] = SANDBOX_HOME_DIR' in kwargs["command"][3]
    assert 'os.environ["MPLCONFIGDIR"] = SANDBOX_MPLCONFIGDIR' in kwargs["command"][3]
    assert 'os.environ.setdefault("MPLBACKEND", "Agg")' in kwargs["command"][3]
    assert kwargs["network_mode"] == "none"
    assert kwargs["read_only"] is True
    assert kwargs["mem_limit"] == "256m"
    assert kwargs["memswap_limit"] == "256m"
    assert kwargs["nano_cpus"] == 500_000_000
    assert kwargs["pids_limit"] == 64
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["security_opt"] == ["no-new-privileges:true"]
    assert kwargs["runtime"] == "runsc"
    assert kwargs["user"] == "sandboxuser"
    assert "mode=1777" in kwargs["tmpfs"]["/tmp"]
    assert kwargs["volumes"] == {"/tmp/test-output": {"bind": "/tmp/outputs", "mode": "rw"}}
    assert kwargs["environment"]["SANDBOX_CODE_B64"] == base64.b64encode(b"print('hello')").decode(
        "ascii"
    )
    assert kwargs["environment"]["MERIDIAN_OUTPUT_DIR"] == "/tmp/outputs"
    assert kwargs["environment"]["MERIDIAN_SANDBOX_RUNTIME"] == "runsc"


def test_executor_builds_nsjail_command_when_requested() -> None:
    client = FakeDockerClient()
    settings = make_settings(SANDBOX_RUNTIME="nsjail")
    executor = SandboxExecutor(settings=settings, client=client)

    kwargs = executor._build_container_kwargs(
        "exec-123",
        "print('hello')",
        Path("/tmp/test-output"),
    )

    assert kwargs["command"][:4] == ["nsjail", "--mode", "o", "--quiet"]
    assert "--chroot" in kwargs["command"]
    assert "--disable_clone_newuser" in kwargs["command"]
    assert "--iface_no_lo" in kwargs["command"]
    assert kwargs["command"].count("--env") == 3
    assert "SANDBOX_CODE_B64" in kwargs["command"]
    assert "MERIDIAN_OUTPUT_DIR" in kwargs["command"]
    assert "MERIDIAN_SANDBOX_RUNTIME" in kwargs["command"]
    assert "--time_limit" in kwargs["command"]
    assert kwargs["command"][-5:-1] == ["/usr/local/bin/python", "-I", "-c", kwargs["command"][-2]]
    assert kwargs["command"][-1] == "/tmp/execution.py"
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


def test_render_worker_bootstrap_uses_requested_process_limit() -> None:
    bootstrap = render_worker_bootstrap(17)

    assert "MAX_PROCESS_LIMIT = 17" in bootstrap


def test_render_worker_bootstrap_does_not_apply_rlimit_nproc() -> None:
    bootstrap = render_worker_bootstrap(64)

    assert "resource.setrlimit(" not in bootstrap
    assert "resource.RLIMIT_NPROC" not in bootstrap


def test_render_worker_bootstrap_prepares_writable_runtime_dirs() -> None:
    bootstrap = render_worker_bootstrap(64)

    assert 'os.environ["HOME"] = SANDBOX_HOME_DIR' in bootstrap
    assert 'os.environ["XDG_CACHE_HOME"] = SANDBOX_CACHE_DIR' in bootstrap
    assert 'os.environ["XDG_CONFIG_HOME"] = SANDBOX_CONFIG_DIR' in bootstrap
    assert 'os.environ["MPLCONFIGDIR"] = SANDBOX_MPLCONFIGDIR' in bootstrap
    assert 'os.environ.setdefault("MPLBACKEND", "Agg")' in bootstrap


def test_render_worker_bootstrap_skips_pyseccomp_on_runsc() -> None:
    bootstrap = render_worker_bootstrap(64)

    assert "if os.environ.get(RUNTIME_ENV_VAR) in ('runsc', 'nsjail'):" in bootstrap


def test_render_worker_bootstrap_skips_pyseccomp_on_nsjail() -> None:
    bootstrap = render_worker_bootstrap(64)

    assert "if os.environ.get(RUNTIME_ENV_VAR) in ('runsc', 'nsjail'):" in bootstrap


def test_executor_creates_world_writable_host_output_dir() -> None:
    executor = SandboxExecutor(settings=make_settings(), client=FakeDockerClient())

    host_output_dir = executor._create_host_output_dir("exec-123")

    try:
        assert host_output_dir.exists()
        assert host_output_dir.parent == Path("/tmp/meridian-sandbox-shared")
        assert oct(host_output_dir.stat().st_mode & 0o777) == "0o777"
    finally:
        host_output_dir.rmdir()


def test_executor_auto_detects_runsc_when_available() -> None:
    class RunscDockerClient(FakeDockerClient):
        def info(self) -> dict[str, Any]:
            return {"Runtimes": {"runc": {"path": "runc"}, "runsc": {"path": "runsc"}}}

    executor = SandboxExecutor(
        settings=make_settings(SANDBOX_RUNTIME=""),
        client=RunscDockerClient(),
    )

    kwargs = executor._build_container_kwargs(
        "exec-123",
        "print('hello')",
        Path("/tmp/test-output"),
    )

    assert executor.runtime == "runsc"
    assert kwargs["runtime"] == "runsc"


def test_health_endpoint_reports_resolved_runtime() -> None:
    class RunscDockerClient(FakeDockerClient):
        def info(self) -> dict[str, Any]:
            return {"Runtimes": {"runc": {"path": "runc"}, "runsc": {"path": "runsc"}}}

    app = create_app(
        settings=make_settings(SANDBOX_RUNTIME=""),
        executor=SandboxExecutor(
            settings=make_settings(SANDBOX_RUNTIME=""),
            client=RunscDockerClient(),
        ),
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["runtime"] == "runsc"


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
    executor = SandboxExecutor(
        settings=make_settings(SANDBOX_RUNTIME="runsc"),
        client=client,
    )

    result = executor.execute_python("print('hello')")

    assert "Sandbox process exited with code 2 without stderr output." in result.stderr
    assert "runsc/gVisor compatibility issue" in result.stderr
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


def test_collect_artifacts_recursively(tmp_path: Path) -> None:
    (tmp_path / "plot.png").write_bytes(b"png-bytes")
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "table.csv").write_bytes(b"a,b\n1,2\n")

    executor = SandboxExecutor(
        settings=make_settings(),
        client=FakeDockerClient(),
    )

    artifacts, warnings = executor._collect_artifacts(tmp_path)

    assert [artifact.relative_path for artifact in artifacts] == [
        "plot.png",
        "reports/table.csv",
    ]
    assert [artifact.content_type for artifact in artifacts] == [
        "image/png",
        "text/csv",
    ]
    assert warnings == []


def test_collect_artifacts_skips_invalid_or_oversized_files(tmp_path: Path) -> None:
    (tmp_path / "large.bin").write_bytes(b"12345")
    (tmp_path / "safe.txt").write_bytes(b"ok")
    (tmp_path / "linked.txt").symlink_to(tmp_path / "safe.txt")

    executor = SandboxExecutor(
        settings=make_settings(SANDBOX_ARTIFACT_MAX_FILE_BYTES=4),
        client=FakeDockerClient(),
    )

    artifacts, warnings = executor._collect_artifacts(tmp_path)

    assert [artifact.relative_path for artifact in artifacts] == ["safe.txt"]
    assert any("large.bin" in warning for warning in warnings)
    assert any("linked.txt" in warning for warning in warnings)
