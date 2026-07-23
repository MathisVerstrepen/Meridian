import os
from collections.abc import Callable

MIB_IN_BYTES = 1024 * 1024

_PLAN_LIMIT_FIELDS = (
    ("free", "web_search", "PLAN_FREE_WEB_SEARCH_LIMIT", 0, 1),
    ("free", "link_extraction", "PLAN_FREE_LINK_EXTRACTION_LIMIT", 0, 1),
    ("free", "storage", "PLAN_FREE_STORAGE_LIMIT_MIB", 50, MIB_IN_BYTES),
    ("premium", "web_search", "PLAN_PREMIUM_WEB_SEARCH_LIMIT", 200, 1),
    ("premium", "link_extraction", "PLAN_PREMIUM_LINK_EXTRACTION_LIMIT", 1000, 1),
    ("premium", "storage", "PLAN_PREMIUM_STORAGE_LIMIT_MIB", 5120, MIB_IN_BYTES),
)

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {
        "web_search": 0,
        "link_extraction": 0,
        "storage": 50 * MIB_IN_BYTES,
    },
    "premium": {
        "web_search": 200,
        "link_extraction": 1000,
        "storage": 5120 * MIB_IN_BYTES,
    },
}


def load_plan_limits(
    getenv: Callable[[str], str | None] = os.getenv,
) -> dict[str, dict[str, int]]:
    """Load and validate plan limits without changing process-wide state."""
    limits: dict[str, dict[str, int]] = {"free": {}, "premium": {}}

    for plan, resource, field, default, multiplier in _PLAN_LIMIT_FIELDS:
        raw_value = getenv(field)
        if raw_value is None:
            value = default
        else:
            stripped_value = raw_value.strip()
            try:
                value = int(stripped_value)
            except ValueError as exc:
                raise ValueError(f"{field} must be a non-negative integer") from exc

            if not stripped_value or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")

        limits[plan][resource] = value * multiplier

    return limits


def configure_plan_limits(getenv: Callable[[str], str | None] = os.getenv) -> None:
    """Atomically validate and apply plan limits while preserving mapping identity."""
    configured_limits = load_plan_limits(getenv)
    PLAN_LIMITS.update(configured_limits)
