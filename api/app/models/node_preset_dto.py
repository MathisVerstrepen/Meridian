import json
import math
import re
import unicodedata
import uuid
from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias, Union

from models.context_merger import ContextMergerMode
from models.message import ToolEnum
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_serializer,
    model_validator,
)

NODE_PRESET_SCHEMA_VERSION = 1
MAX_NODE_PRESETS = 8
MAX_PRESET_NODES = 20
MAX_PRESET_EDGES = 40
MAX_NODE_PRESETS_UTF8_BYTES = 524_288
DEFAULT_PRESET_ACCENT_COLOR = "#eb5e28"
PRESET_ACCENT_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}")


class StrictPresetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_serializer(mode="wrap")
    def _omit_absent_optional_fields(self, serializer: Any) -> dict[str, Any]:
        return {
            key: value
            for key, value in serializer(self).items()
            if value is not None or key in self.model_fields_set
        }


def _uuid_string(value: str) -> str:
    try:
        uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("must be a UUID string") from exc
    return value


UuidString: TypeAlias = Annotated[str, StringConstraints(strict=True), AfterValidator(_uuid_string)]
String64: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=64)]
String128: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=128)]
NonEmptyString128: TypeAlias = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=128)
]
String255: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=255)]
String256: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=256)]
String512: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=512)]
String2048: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=2_048)]
String4000: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=4_000)]
String4096: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=4_096)]
String20000: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=20_000)]
String100000: TypeAlias = Annotated[str, StringConstraints(strict=True, max_length=100_000)]
FiniteCoordinate: TypeAlias = Annotated[
    float, Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False)
]
FiniteDimension: TypeAlias = Annotated[float, Field(le=4_000, allow_inf_nan=False)]
ToolEnumValue: TypeAlias = Annotated[ToolEnum, Field(strict=False)]
ContextMergerModeValue: TypeAlias = Annotated[ContextMergerMode, Field(strict=False)]


def _reject_disallowed_controls(value: str) -> str:
    if any(
        unicodedata.category(character).startswith("C") and not character.isspace()
        for character in value
    ):
        raise ValueError("must not contain control characters")
    return value


class NodePresetPositionDTO(StrictPresetModel):
    x: FiniteCoordinate
    y: FiniteCoordinate


class NodePresetVisualiseModesDTO(StrictPresetModel):
    enableMermaid: bool | None = None
    enableSvg: bool | None = None
    enableHtml: bool | None = None


class NodePresetPromptDataDTO(StrictPresetModel):
    prompt: String100000
    templateId: String256 | None = None
    templateVariables: dict[NonEmptyString128, String20000] = Field(max_length=100)


class NodePresetFileReferenceDTO(StrictPresetModel):
    id: UuidString
    name: String255
    path: String2048 | None = None
    type: Literal["file", "folder"]
    size: Annotated[int, Field(ge=0, le=10**15)] | None = None
    content_type: String255 | None = None
    created_at: String64
    updated_at: String64
    cached: bool


class NodePresetFilePromptDataDTO(StrictPresetModel):
    files: list[NodePresetFileReferenceDTO] = Field(max_length=50)


class UniqueToolsMixin:
    @field_validator("selectedTools")
    @classmethod
    def _selected_tools_are_unique(cls, value: list[ToolEnum]) -> list[ToolEnum]:
        if len(value) != len(set(value)):
            raise ValueError("selectedTools must be unique")
        return value


class NodePresetTextToTextDataDTO(UniqueToolsMixin, StrictPresetModel):
    model: String256
    selectedTools: list[ToolEnumValue]
    autoSelectTools: bool | None = None
    imageModel: String256 | None = None
    videoModel: String256 | None = None
    visualiseModes: NodePresetVisualiseModesDTO | None = None


class NodePresetParallelModelDTO(StrictPresetModel):
    model: String256


class NodePresetParallelAggregatorDTO(StrictPresetModel):
    prompt: String100000
    model: String256


class NodePresetParallelizationDataDTO(StrictPresetModel):
    models: list[NodePresetParallelModelDTO] = Field(max_length=16)
    aggregator: NodePresetParallelAggregatorDTO
    defaultModel: String256


class NodePresetRoutingDataDTO(UniqueToolsMixin, StrictPresetModel):
    routeGroupId: String256
    selectedTools: list[ToolEnumValue]
    autoSelectTools: bool | None = None
    imageModel: String256 | None = None
    videoModel: String256 | None = None
    visualiseModes: NodePresetVisualiseModesDTO | None = None


class NodePresetRepositoryDTO(StrictPresetModel):
    provider: String255
    encoded_provider: String255
    full_name: String255
    description: String4096 | None
    clone_url_ssh: String4096
    clone_url_https: String4096
    default_branch: String255
    stargazers_count: Annotated[int, Field(ge=0)] | None = None


class NodePresetGithubFileDTO(StrictPresetModel):
    name: String255
    type: Literal["file", "directory"]
    path: String4096


class GithubIssueState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


GithubIssueStateValue: TypeAlias = Annotated[GithubIssueState, Field(strict=False)]


class NodePresetGithubIssueDTO(StrictPresetModel):
    id: Annotated[int, Field(ge=0)]
    number: Annotated[int, Field(ge=0)]
    title: String512
    body: String100000 | None
    state: GithubIssueStateValue
    html_url: String4096
    is_pull_request: bool
    user_login: String255
    user_avatar: String4096 | None
    created_at: String255
    updated_at: String255


class NodePresetGithubDataDTO(StrictPresetModel):
    repo: NodePresetRepositoryDTO | None = None
    files: list[NodePresetGithubFileDTO] = Field(max_length=200)
    selectedIssues: list[NodePresetGithubIssueDTO] = Field(max_length=50)
    branch: String255 | None = None


class NodePresetContextMergerDataDTO(StrictPresetModel):
    mode: ContextMergerModeValue
    last_n: Annotated[int, Field(ge=1, le=1_000)] | None = None
    include_user_messages: bool


class NodePresetGroupDataDTO(StrictPresetModel):
    title: String128
    comment: String4000
    colorIndex: Annotated[int, Field(ge=0, le=10)]

    @field_validator("title")
    @classmethod
    def _title_has_no_controls(cls, value: str) -> str:
        return _reject_disallowed_controls(value)


NodePresetDataDTO: TypeAlias = Union[
    NodePresetPromptDataDTO,
    NodePresetFilePromptDataDTO,
    NodePresetTextToTextDataDTO,
    NodePresetParallelizationDataDTO,
    NodePresetRoutingDataDTO,
    NodePresetGithubDataDTO,
    NodePresetContextMergerDataDTO,
    NodePresetGroupDataDTO,
]

NodePresetNodeType: TypeAlias = Literal[
    "prompt",
    "filePrompt",
    "textToText",
    "parallelization",
    "routing",
    "github",
    "contextMerger",
    "group",
]

NODE_DATA_MODELS: dict[str, type[StrictPresetModel]] = {
    "prompt": NodePresetPromptDataDTO,
    "filePrompt": NodePresetFilePromptDataDTO,
    "textToText": NodePresetTextToTextDataDTO,
    "parallelization": NodePresetParallelizationDataDTO,
    "routing": NodePresetRoutingDataDTO,
    "github": NodePresetGithubDataDTO,
    "contextMerger": NodePresetContextMergerDataDTO,
    "group": NodePresetGroupDataDTO,
}

MINIMUM_NODE_DIMENSIONS: dict[str, tuple[float, float]] = {
    "prompt": (500, 200),
    "filePrompt": (500, 275),
    "textToText": (600, 300),
    "parallelization": (660, 450),
    "routing": (600, 300),
    "github": (500, 250),
    "contextMerger": (285, 135),
    "group": (40, 40),
}


class NodePresetNodeDTO(StrictPresetModel):
    id: UuidString
    type: NodePresetNodeType
    position: NodePresetPositionDTO
    width: FiniteDimension
    height: FiniteDimension
    parentId: UuidString | None = None
    data: NodePresetDataDTO

    @model_validator(mode="before")
    @classmethod
    def _parse_data_for_node_type(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        node_type = value.get("type")
        if not isinstance(node_type, str):
            return value
        data_model = NODE_DATA_MODELS.get(node_type)
        if data_model is None or "data" not in value:
            return value
        parsed = dict(value)
        parsed["data"] = data_model.model_validate(value["data"])
        return parsed

    @model_validator(mode="after")
    def _validate_type_geometry_and_parent(self) -> "NodePresetNodeDTO":
        expected_data_model = NODE_DATA_MODELS[self.type]
        if not isinstance(self.data, expected_data_model):
            raise ValueError(f"data does not match node type {self.type}")

        minimum_width, minimum_height = MINIMUM_NODE_DIMENSIONS[self.type]
        if not math.isfinite(self.width) or self.width < minimum_width:
            raise ValueError(f"width must be at least {minimum_width:g} for {self.type}")
        if not math.isfinite(self.height) or self.height < minimum_height:
            raise ValueError(f"height must be at least {minimum_height:g} for {self.type}")
        if self.type == "group" and self.parentId is not None:
            raise ValueError("group nodes cannot have a parentId")
        return self


class NodePresetEdgeDTO(StrictPresetModel):
    id: UuidString
    source: UuidString
    target: UuidString
    category: Literal["prompt", "context", "attachment"]


EDGE_TYPE_RULES: dict[str, tuple[set[str], set[str]]] = {
    "prompt": (
        {"prompt"},
        {"prompt", "textToText", "parallelization", "routing"},
    ),
    "context": (
        {"textToText", "parallelization", "routing", "contextMerger"},
        {"textToText", "parallelization", "routing", "contextMerger"},
    ),
    "attachment": (
        {"filePrompt", "github"},
        {"textToText", "parallelization", "routing"},
    ),
}


class NodePresetDTO(StrictPresetModel):
    id: UuidString
    name: str
    accentColor: str = DEFAULT_PRESET_ACCENT_COLOR
    nodes: list[NodePresetNodeDTO] = Field(max_length=MAX_PRESET_NODES)
    edges: list[NodePresetEdgeDTO] = Field(max_length=MAX_PRESET_EDGES)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        if len(value) > 64:
            raise ValueError("name must contain at most 64 Unicode code points")
        return _reject_disallowed_controls(value)

    @field_validator("accentColor")
    @classmethod
    def _normalize_accent_color(cls, value: str) -> str:
        if not PRESET_ACCENT_COLOR_PATTERN.fullmatch(value):
            raise ValueError("accentColor must be a six-digit CSS hex color")
        return value.lower()

    @model_validator(mode="after")
    def _validate_topology(self) -> "NodePresetDTO":
        nodes_by_id: dict[str, NodePresetNodeDTO] = {}
        for node in self.nodes:
            if node.id in nodes_by_id:
                raise ValueError("node IDs must be unique within a preset")
            nodes_by_id[node.id] = node

        edge_ids: set[str] = set()
        edge_tuples: set[tuple[str, str, str]] = set()
        prompt_targets: set[str] = set()
        for edge in self.edges:
            if edge.id in edge_ids:
                raise ValueError("edge IDs must be unique within a preset")
            edge_ids.add(edge.id)
            if edge.source == edge.target:
                raise ValueError("edges cannot connect a node to itself")
            source = nodes_by_id.get(edge.source)
            target = nodes_by_id.get(edge.target)
            if source is None or target is None:
                raise ValueError("edge endpoints must reference nodes in the same preset")
            if source.type == "group" or target.type == "group":
                raise ValueError("edges cannot connect group nodes")

            allowed_sources, allowed_targets = EDGE_TYPE_RULES[edge.category]
            if source.type not in allowed_sources or target.type not in allowed_targets:
                raise ValueError(f"invalid {edge.category} edge node types")

            edge_tuple = (edge.source, edge.target, edge.category)
            if edge_tuple in edge_tuples:
                raise ValueError("duplicate source, target, and category edge")
            edge_tuples.add(edge_tuple)
            if edge.category == "prompt":
                if edge.target in prompt_targets:
                    raise ValueError("a node may have only one incoming prompt edge")
                prompt_targets.add(edge.target)

        group_ids = {node.id for node in self.nodes if node.type == "group"}
        child_count = {group_id: 0 for group_id in group_ids}
        for node in self.nodes:
            if node.parentId is None:
                continue
            if node.type == "group" or node.parentId not in group_ids:
                raise ValueError("parentId must reference a group in the same preset")
            child_count[node.parentId] += 1
        if any(count == 0 for count in child_count.values()):
            raise ValueError("every group must have at least one direct child")
        return self


class NodePresetSettingsDTO(StrictPresetModel):
    schemaVersion: Literal[1]
    presets: list[NodePresetDTO] = Field(max_length=MAX_NODE_PRESETS)

    @field_validator("schemaVersion", mode="before")
    @classmethod
    def _schema_version_is_integer_literal_one(cls, value: Any) -> Any:
        if type(value) is not int or value != NODE_PRESET_SCHEMA_VERSION:
            raise ValueError(f"schemaVersion must be integer {NODE_PRESET_SCHEMA_VERSION}")
        return value

    @model_validator(mode="after")
    def _validate_collection(self) -> "NodePresetSettingsDTO":
        preset_ids: set[str] = set()
        name_keys: set[str] = set()
        for preset in self.presets:
            if preset.id in preset_ids:
                raise ValueError("preset IDs must be unique")
            preset_ids.add(preset.id)

            name_key = unicodedata.normalize("NFKC", preset.name).casefold()
            if name_key in name_keys:
                raise ValueError("preset names must be unique")
            name_keys.add(name_key)

        compact_json = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(compact_json.encode("utf-8")) > MAX_NODE_PRESETS_UTF8_BYTES:
            raise ValueError(
                f"nodePresets must be at most {MAX_NODE_PRESETS_UTF8_BYTES} UTF-8 bytes"
            )
        return self


def default_node_preset_settings() -> NodePresetSettingsDTO:
    return NodePresetSettingsDTO(schemaVersion=1, presets=[])
