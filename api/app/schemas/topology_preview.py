from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TOPOLOGY_PREVIEW_WIDTH = 1000
TOPOLOGY_PREVIEW_HEIGHT = 600
TOPOLOGY_PREVIEW_MAX_NODES = 64
TOPOLOGY_PREVIEW_MAX_EDGES = 128


class TopologyPreviewNodeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    x: int = Field(ge=0, le=TOPOLOGY_PREVIEW_WIDTH)
    y: int = Field(ge=0, le=TOPOLOGY_PREVIEW_HEIGHT)
    width: int = Field(gt=0, le=TOPOLOGY_PREVIEW_WIDTH)
    height: int = Field(gt=0, le=TOPOLOGY_PREVIEW_HEIGHT)

    @model_validator(mode="after")
    def validate_rectangle_containment(self) -> "TopologyPreviewNodeV1":
        if self.x + self.width > TOPOLOGY_PREVIEW_WIDTH:
            raise ValueError("node rectangle exceeds preview width")
        if self.y + self.height > TOPOLOGY_PREVIEW_HEIGHT:
            raise ValueError("node rectangle exceeds preview height")
        return self


class TopologyPreviewEdgeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    x1: int = Field(ge=0, le=TOPOLOGY_PREVIEW_WIDTH)
    y1: int = Field(ge=0, le=TOPOLOGY_PREVIEW_HEIGHT)
    x2: int = Field(ge=0, le=TOPOLOGY_PREVIEW_WIDTH)
    y2: int = Field(ge=0, le=TOPOLOGY_PREVIEW_HEIGHT)


class TopologyPreviewV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1] = 1
    width: Literal[1000] = 1000
    height: Literal[600] = 600
    nodes: list[TopologyPreviewNodeV1] = Field(
        default_factory=list,
        max_length=TOPOLOGY_PREVIEW_MAX_NODES,
    )
    edges: list[TopologyPreviewEdgeV1] = Field(
        default_factory=list,
        max_length=TOPOLOGY_PREVIEW_MAX_EDGES,
    )


def empty_topology_preview_v1() -> dict[str, Any]:
    return TopologyPreviewV1().model_dump(mode="json")
