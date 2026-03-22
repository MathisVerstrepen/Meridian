from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SandboxSettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    sandbox_manager_port: int = Field(default=5000, alias="SANDBOX_MANAGER_PORT")
    max_concurrent_sandboxes: int = Field(default=10, alias="MAX_CONCURRENT_SANDBOXES")
    sandbox_queue_wait_seconds: float = Field(default=5.0, alias="SANDBOX_QUEUE_WAIT_SECONDS")
    execution_timeout_seconds: float = Field(default=10.0, alias="EXECUTION_TIMEOUT_SECONDS")
    sandbox_output_limit_bytes: int = Field(default=50 * 1024, alias="SANDBOX_OUTPUT_LIMIT_BYTES")
    sandbox_code_max_bytes: int = Field(default=100 * 1024, alias="SANDBOX_CODE_MAX_BYTES")
    sandbox_memory_limit: str = Field(default="256m", alias="SANDBOX_MEMORY_LIMIT")
    sandbox_cpu_nano_cpus: int = Field(default=500_000_000, alias="SANDBOX_CPU_NANO_CPUS")
    sandbox_pids_limit: int = Field(default=64, alias="SANDBOX_PIDS_LIMIT")
    sandbox_tmpfs_size: str = Field(default="50m", alias="SANDBOX_TMPFS_SIZE")
    sandbox_runtime: str | None = Field(default=None, alias="SANDBOX_RUNTIME")
    sandbox_host_output_root: str = Field(
        default="/tmp/meridian-sandbox-outputs",
        alias="SANDBOX_HOST_OUTPUT_ROOT",
    )
    sandbox_artifact_max_files: int = Field(default=20, alias="SANDBOX_ARTIFACT_MAX_FILES")
    sandbox_artifact_max_file_bytes: int = Field(
        default=5 * 1024 * 1024,
        alias="SANDBOX_ARTIFACT_MAX_FILE_BYTES",
    )
    sandbox_artifact_max_total_bytes: int = Field(
        default=10 * 1024 * 1024,
        alias="SANDBOX_ARTIFACT_MAX_TOTAL_BYTES",
    )
    sandbox_worker_image: str = Field(
        default="meridian-sandbox-python:local",
        alias="SANDBOX_WORKER_IMAGE",
    )


@lru_cache
def get_settings() -> SandboxSettings:
    return SandboxSettings()
