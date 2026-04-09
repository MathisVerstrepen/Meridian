from typing import Any

from pydantic import BaseModel

_INTEGER_BOUND_KEYS = (
    ("minimum", "at least"),
    ("maximum", "at most"),
    ("exclusiveMinimum", "greater than"),
    ("exclusiveMaximum", "less than"),
)


def build_openrouter_response_format(
    schema: type[BaseModel], schema_name: str = "response"
) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": sanitize_openrouter_json_schema(
                {
                    "type": "object",
                    **schema.model_json_schema(),
                }
            ),
        },
    }


def sanitize_openrouter_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_schema_node(schema)
    if not isinstance(sanitized, dict):
        raise TypeError("OpenRouter schema root must remain a JSON object.")
    return sanitized


def _sanitize_schema_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_sanitize_schema_node(item) for item in node]

    if not isinstance(node, dict):
        return node

    sanitized = {key: _sanitize_schema_node(value) for key, value in node.items()}
    node_types = sanitized.get("type")
    type_names = (
        [node_types]
        if isinstance(node_types, str)
        else (
            [item for item in node_types if isinstance(item, str)]
            if isinstance(node_types, list)
            else []
        )
    )

    if "integer" not in type_names:
        return sanitized

    bound_notes: list[str] = []
    for key, label in _INTEGER_BOUND_KEYS:
        value = sanitized.pop(key, None)
        if value is not None:
            bound_notes.append(f"{label} {value}")

    if not bound_notes:
        return sanitized

    bounds_description = f"Integer value must be {' and '.join(bound_notes)}."
    existing_description = sanitized.get("description")
    if isinstance(existing_description, str) and existing_description.strip():
        sanitized["description"] = f"{existing_description.strip()} {bounds_description}"
    else:
        sanitized["description"] = bounds_description

    return sanitized
