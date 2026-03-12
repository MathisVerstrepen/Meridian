import logging
from typing import Literal

from const.prompts import MERMAID_TOOL_SYSTEM_PROMPT
from pydantic import BaseModel, Field
from services.settings import get_user_settings

logger = logging.getLogger("uvicorn.error")

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

MERMAID_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_mermaid_diagram",
        "description": (
            "Generate Mermaid source code for diagrams when a visual explanation "
            "would improve the answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "instructions": {
                    "type": "string",
                    "description": (
                        "What the diagram should communicate and what details must "
                        "be emphasized."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "The relevant facts or source material to convert into a "
                        "Mermaid diagram."
                    ),
                },
                "diagram_type": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "flowchart",
                        "sequenceDiagram",
                        "gantt",
                        "erDiagram",
                        "stateDiagram-v2",
                        "classDiagram",
                    ],
                    "description": (
                        "Preferred Mermaid diagram family. Use auto when the best "
                        "type is unclear."
                    ),
                },
            },
            "required": ["instructions", "context"],
        },
    },
}


class MermaidToolResponse(BaseModel):
    mermaid: str = Field(..., min_length=1)
    diagram_type: (
        Literal[
            "flowchart",
            "sequenceDiagram",
            "gantt",
            "erDiagram",
            "stateDiagram-v2",
            "classDiagram",
        ]
        | None
    ) = None
    title: str | None = None


async def generate_mermaid_diagram(arguments: dict, req) -> dict:
    instructions = arguments.get("instructions", "").strip()
    context = arguments.get("context", "").strip()
    diagram_type = arguments.get("diagram_type", "auto")

    if not instructions:
        return {"error": "The 'instructions' field is required."}

    if not context:
        return {"error": "The 'context' field is required."}

    settings = await get_user_settings(req.pg_engine, req.user_id)
    model = settings.toolsMermaidGeneration.defaultModel or "anthropic/claude-haiku-4.5"
    system_prompt = settings.toolsMermaidGeneration.systemPrompt or MERMAID_TOOL_SYSTEM_PROMPT

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Generate Mermaid source code from the material below.\n\n"
                    f"Preferred diagram type: {diagram_type}\n\n"
                    f"Instructions:\n{instructions}\n\n"
                    f"Context:\n{context}"
                ),
            },
        ],
        "stream": False,
        "temperature": 0.2,
        "reasoning": {"enabled": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "mermaid_tool_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    **MermaidToolResponse.model_json_schema(),
                },
            },
        },
    }

    response = None
    try:
        response = await req.http_client.post(
            OPENROUTER_CHAT_URL,
            headers=req.headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = MermaidToolResponse.model_validate_json(content)
        return parsed.model_dump(exclude_none=True)
    except Exception as exc:
        logger.error(f"Mermaid generation tool failed: {exc}", exc_info=True)
        if response is not None:
            try:
                error_message = response.json().get("error", {}).get("message")
                if error_message:
                    return {"error": f"Mermaid generation failed: {error_message}"}
            except Exception:
                pass
        return {"error": f"Mermaid generation failed: {str(exc)}"}
