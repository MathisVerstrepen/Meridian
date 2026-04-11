import json
from typing import Any


def extract_bridge_json_payload(stdout_text: str) -> dict[str, Any] | None:
    stripped_stdout = stdout_text.strip()
    if not stripped_stdout:
        return {}

    try:
        parsed = json.loads(stripped_stdout)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(parsed, dict):
            return parsed
        raise RuntimeError("Gemini CLI bridge returned an invalid response payload.")

    decoder = json.JSONDecoder()
    last_payload: dict[str, Any] | None = None
    for index, char in enumerate(stripped_stdout):
        if char != "{":
            continue
        try:
            candidate, end_index = decoder.raw_decode(stripped_stdout[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(candidate, dict):
            continue
        if stripped_stdout[index + end_index :].strip():
            last_payload = candidate
            continue
        return candidate

    return last_payload
