from enum import StrEnum

from pydantic import BaseModel, Field


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"


class SandboxInputFile(BaseModel):
    relative_path: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    size: int = Field(ge=0)
    content_b64: str = Field(min_length=1)


class CodeExecutionRequest(BaseModel):
    language: str = Field(min_length=1)
    code: str = Field(min_length=1)
    input_files: list[SandboxInputFile] = Field(default_factory=list)


class SandboxArtifact(BaseModel):
    relative_path: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    size: int = Field(ge=0)
    content_b64: str = Field(min_length=1)


class CodeExecutionResponse(BaseModel):
    execution_id: str
    status: ExecutionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int
    output_truncated: bool = False
    artifacts: list[SandboxArtifact] = Field(default_factory=list)
    artifact_warnings: list[str] = Field(default_factory=list)
    input_warnings: list[str] = Field(default_factory=list)
