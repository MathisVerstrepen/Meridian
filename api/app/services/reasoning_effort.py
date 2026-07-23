from collections.abc import Iterable, Mapping
from typing import Any

from models.chatDTO import EffortEnum

CANONICAL_REASONING_EFFORTS = (
    EffortEnum.MAX,
    EffortEnum.XHIGH,
    EffortEnum.HIGH,
    EffortEnum.MEDIUM,
    EffortEnum.LOW,
    EffortEnum.MINIMAL,
    EffortEnum.NONE,
)
ALL_REASONING_EFFORTS_MASK = (1 << len(CANONICAL_REASONING_EFFORTS)) - 1
UNKNOWN_REASONING_EFFORTS_MASK = -1

_EFFORT_BITS = {
    effort.value: 1 << index for index, effort in enumerate(CANONICAL_REASONING_EFFORTS)
}
_EFFORT_INDEXES = {effort.value: index for index, effort in enumerate(CANONICAL_REASONING_EFFORTS)}


def supported_efforts_mask(value: object, *, present: bool) -> int:
    """Convert an OpenRouter supported-efforts field to Meridian's compact mask."""
    if not present:
        return 0
    if value is None:
        return ALL_REASONING_EFFORTS_MASK
    if not isinstance(value, list):
        return UNKNOWN_REASONING_EFFORTS_MASK
    if not value:
        return 0

    mask = 0
    for effort in value:
        if isinstance(effort, str):
            mask |= _EFFORT_BITS.get(effort, 0)
    return mask if mask else UNKNOWN_REASONING_EFFORTS_MASK


def reasoning_efforts_mask_from_catalog(
    reasoning: object,
    supported_efforts_field: str,
) -> int:
    """Read a documented OpenRouter reasoning object without exposing its source shape."""
    if reasoning is None:
        return 0
    if not isinstance(reasoning, Mapping):
        return UNKNOWN_REASONING_EFFORTS_MASK
    return supported_efforts_mask(
        reasoning.get(supported_efforts_field),
        present=supported_efforts_field in reasoning,
    )


def resolve_reasoning_effort(
    configured_effort: EffortEnum | str | None,
    reasoning_efforts: int,
    *,
    prefer_higher: bool,
) -> EffortEnum | str | None:
    """Return the exact or nearest OpenRouter-supported effort for one request."""
    if type(reasoning_efforts) is int and reasoning_efforts == 0:
        return None
    if (
        type(reasoning_efforts) is not int
        or reasoning_efforts < 1
        or reasoning_efforts > ALL_REASONING_EFFORTS_MASK
        or configured_effort is None
    ):
        return configured_effort

    configured_value = (
        configured_effort.value if isinstance(configured_effort, EffortEnum) else configured_effort
    )
    configured_index = _EFFORT_INDEXES.get(configured_value)
    if configured_index is None:
        return configured_effort
    if reasoning_efforts & _EFFORT_BITS[configured_value]:
        return configured_effort

    supported_indexes = [
        index
        for index, effort in enumerate(CANONICAL_REASONING_EFFORTS)
        if reasoning_efforts & _EFFORT_BITS[effort.value]
    ]
    if not supported_indexes:
        return configured_effort

    nearest_index = min(
        supported_indexes,
        key=lambda index: (abs(index - configured_index), index if prefer_higher else -index),
    )
    return CANONICAL_REASONING_EFFORTS[nearest_index]


def get_model_reasoning_efforts(
    model_id: str | None,
    available_models: Iterable[object] | None,
) -> int:
    """Get an exact model's trustworthy capability mask, preserving unknown as -1."""
    if not model_id or not available_models:
        return UNKNOWN_REASONING_EFFORTS_MASK

    for model in available_models:
        if isinstance(model, Mapping):
            if model.get("id") != model_id:
                continue
            value: Any = model.get("reasoningEfforts", UNKNOWN_REASONING_EFFORTS_MASK)
        else:
            if getattr(model, "id", None) != model_id:
                continue
            value = getattr(model, "reasoningEfforts", UNKNOWN_REASONING_EFFORTS_MASK)
        if type(value) is int and -1 <= value <= ALL_REASONING_EFFORTS_MASK:
            return value
        return UNKNOWN_REASONING_EFFORTS_MASK
    return UNKNOWN_REASONING_EFFORTS_MASK
