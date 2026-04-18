from __future__ import annotations

from typing import Any


def _merge_int_map(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, int]:
    merged: dict[str, int] = {}
    for source in (left or {}, right or {}):
        for key, value in source.items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return merged


def _merge_float_map(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, float]:
    merged: dict[str, float] = {}
    for source in (left or {}, right or {}):
        for key, value in source.items():
            merged[str(key)] = merged.get(str(key), 0.0) + float(value or 0.0)
    return merged


def normalize_usage_payload(usage_data: dict[str, Any] | None) -> dict[str, Any]:
    usage = dict(usage_data or {})
    return {
        "cost": float(usage.get("cost", 0.0) or 0.0),
        "is_byok": bool(usage.get("is_byok", True)),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "prompt_tokens_details": _merge_int_map(usage.get("prompt_tokens_details"), None),
        "cost_details": _merge_float_map(usage.get("cost_details"), None),
        "completion_tokens_details": _merge_int_map(
            usage.get("completion_tokens_details"),
            None,
        ),
    }


def merge_usage_data(
    existing_usage: dict[str, Any] | None,
    new_usage: dict[str, Any] | None,
) -> dict[str, Any]:
    existing = normalize_usage_payload(existing_usage)
    new = normalize_usage_payload(new_usage)
    requests = list(existing_usage.get("requests", []) if isinstance(existing_usage, dict) else [])
    if isinstance(new_usage, dict):
        requests.extend(list(new_usage.get("requests", []) or []))

    return {
        "cost": existing["cost"] + new["cost"],
        "is_byok": existing["is_byok"] and new["is_byok"],
        "total_tokens": existing["total_tokens"] + new["total_tokens"],
        "prompt_tokens": existing["prompt_tokens"] + new["prompt_tokens"],
        "completion_tokens": existing["completion_tokens"] + new["completion_tokens"],
        "prompt_tokens_details": _merge_int_map(
            existing["prompt_tokens_details"],
            new["prompt_tokens_details"],
        ),
        "cost_details": _merge_float_map(existing["cost_details"], new["cost_details"]),
        "completion_tokens_details": _merge_int_map(
            existing["completion_tokens_details"],
            new["completion_tokens_details"],
        ),
        "requests": requests,
    }


def build_usage_request_breakdown(
    *,
    usage_data: dict[str, Any],
    index: int,
    model: str,
    finish_reason: str | None,
    native_finish_reason: str | None = None,
    request_id: str | None = None,
    tool_names: list[str] | None = None,
) -> dict[str, Any]:
    normalized_usage = normalize_usage_payload(usage_data)
    normalized_tool_names = [name for name in (tool_names or []) if name]
    return {
        **normalized_usage,
        "index": index,
        "model": model,
        "finish_reason": finish_reason,
        "native_finish_reason": native_finish_reason,
        "request_id": request_id,
        "tool_call_count": len(normalized_tool_names),
        "tool_names": normalized_tool_names,
    }


def append_usage_request_breakdown(
    usage_total: dict[str, Any] | None,
    request_breakdown: dict[str, Any],
) -> dict[str, Any]:
    return merge_usage_data(
        usage_total,
        {
            **normalize_usage_payload(request_breakdown),
            "requests": [request_breakdown],
        },
    )


def finalize_usage_data(usage_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if usage_data is None:
        return None

    finalized_usage = merge_usage_data(usage_data, None)
    requests = list(finalized_usage.get("requests", []) or [])
    has_visible_tool_loop = len(requests) > 1 or any(
        int(request.get("tool_call_count", 0) or 0) > 0 for request in requests
    )
    if not has_visible_tool_loop:
        finalized_usage["requests"] = []
    return finalized_usage


def extract_tool_names(tool_calls: list[dict[str, Any]] | None) -> list[str]:
    tool_names: list[str] = []
    for tool_call in tool_calls or []:
        if not isinstance(tool_call, dict):
            continue
        function_name = str(tool_call.get("function", {}).get("name") or "").strip()
        if function_name:
            tool_names.append(function_name)
    return tool_names
