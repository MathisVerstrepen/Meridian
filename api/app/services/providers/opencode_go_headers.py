"""Client identity and conversation routing for OpenCode Go requests."""

import json
import uuid


def build_opencode_go_session_headers(
    *, user_id: str | None = None, graph_id: str | None = None
) -> dict[str, str]:
    # Keep routing stable across turns, models, title generation, and tool rounds.
    # Hash the local identifiers so we don't send user or graph IDs to the provider.
    if user_id and graph_id:
        session_id = uuid.uuid5(
            uuid.NAMESPACE_URL, json.dumps(["meridian", "opencode-go", user_id, graph_id])
        )
    else:
        # Validation and requests without a graph each get their own session.
        session_id = uuid.uuid4()
    return {"User-Agent": "Meridian/1.0", "x-opencode-session": str(session_id)}
