from enum import Enum
from pydantic import BaseModel

from models.message import NodeTypeEnum


class NodeSearchDirection(Enum):
    upstream = "upstream"
    downstream = "downstream"


class NodeSearchRequest(BaseModel):
    source_node_id: str
    direction: NodeSearchDirection
    node_type: list[NodeTypeEnum]