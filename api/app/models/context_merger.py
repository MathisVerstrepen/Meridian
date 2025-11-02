from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

DEFAULT_LAST_N = 1


class ContextMergerMode(str, Enum):
    """Defines the merging strategies for the ContextMerger node."""

    FULL = "full"
    LAST_N = "last_n"
    SUMMARY = "summary"


class ContextMergerConfig(BaseModel):
    """A Pydantic model to hold the validated configuration for a ContextMerger node."""

    mode: ContextMergerMode = ContextMergerMode.FULL
    last_n: int = Field(default=DEFAULT_LAST_N, ge=1)
    branch_summaries: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_node_data(cls, data: Optional[dict]) -> "ContextMergerConfig":
        """Factory method to safely create a config object from raw node data."""
        if not isinstance(data, dict):
            return cls()

        return cls(
            mode=data.get("mode", ContextMergerMode.FULL),
            last_n=data.get("last_n", DEFAULT_LAST_N),
            branch_summaries=data.get("branch_summaries", {}),
        )
