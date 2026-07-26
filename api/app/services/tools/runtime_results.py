from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TransientImageContent:
    file_id: str
    data_uri: str


@dataclass(frozen=True)
class ToolExecutionEnvelope:
    """Separates auditable JSON from request-local binary-derived content."""

    persisted_result: dict[str, Any]
    transient_images: tuple[TransientImageContent, ...] = ()


def unwrap_tool_execution_result(
    result: Any,
) -> tuple[Any, tuple[TransientImageContent, ...]]:
    if isinstance(result, ToolExecutionEnvelope):
        return result.persisted_result, result.transient_images
    return result, ()
