import json
import logging
import re
import uuid
from html import escape
from pathlib import PurePosixPath
from typing import Any, Literal

from const.prompts import (
    MERMAID_TOOL_SYSTEM_PROMPT,
    VISUALISE_HTML_TOOL_SYSTEM_PROMPT,
    VISUALISE_SVG_TOOL_SYSTEM_PROMPT,
)
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from fastapi import HTTPException
from pydantic import BaseModel, Field
from services.settings import get_user_settings
from services.tools.mermaid import (
    MermaidValidatorRuntimeError,
    generate_mermaid_with_retry,
    normalize_mermaid_retry_count,
)
from services.tools.persisted_artifacts import persist_generated_artifacts

logger = logging.getLogger("uvicorn.error")

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_VISUAL_CONTENT_LENGTH = 64 * 1024
VISUALISE_FOLDER_NAME = "Visualise"
VISUALISE_IFRAME_CSP = "; ".join(
    [
        "default-src 'none'",
        (
            "script-src 'unsafe-inline' https://cdnjs.cloudflare.com https://esm.sh "
            "https://cdn.jsdelivr.net https://unpkg.com https://cdn.tailwindcss.com"
        ),
        (
            "style-src 'unsafe-inline' https://cdnjs.cloudflare.com https://esm.sh "
            "https://cdn.jsdelivr.net https://unpkg.com https://cdn.tailwindcss.com"
        ),
        "img-src data: blob:",
        (
            "font-src data: https://cdnjs.cloudflare.com https://esm.sh "
            "https://cdn.jsdelivr.net https://unpkg.com https://cdn.tailwindcss.com"
        ),
        "connect-src 'none'",
        "media-src data: blob:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ]
)
FULL_DOCUMENT_TAG_PATTERN = re.compile(r"<\s*(?:!doctype|html|head|body)\b", re.IGNORECASE)
OUTER_FENCE_PATTERN = re.compile(
    r"^\s*```(?:visualizer|html|svg|xml|mermaid)?\s*\n(?P<body>[\s\S]*?)\n```\s*$",
    re.IGNORECASE,
)
MERMAID_BLOCK_PREFIXES = (
    "flowchart",
    "sequenceDiagram",
    "gantt",
    "erDiagram",
    "stateDiagram-v2",
    "classDiagram",
    "journey",
    "mindmap",
    "timeline",
    "pie",
    "gitGraph",
    "requirementDiagram",
    "quadrantChart",
    "sankey-beta",
    "architecture",
    "xychart-beta",
    "kanban",
    "block-beta",
    "packet-beta",
)

VISUALISE_TOOL = {
    "type": "function",
    "function": {
        "name": "visualise",
        "description": (
            "Generate Mermaid, SVG, or HTML visual output when a visual explanation "
            "would improve the response."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "instructions": {
                    "type": "string",
                    "description": (
                        "What the visual should communicate and what details should be emphasized."
                    ),
                },
                "title": {
                    "type": "string",
                    "description": (
                        "A short section title for the visual. "
                        "Use a concise label that fits well in chat activity UI."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "The relevant facts or source material to convert into a visual."
                        " Include all the information needed to create the visual. "
                        "There is no size limit for this field."
                    ),
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["svg", "html", "mermaid"],
                    "description": (
                        "Which type of visual artifact to generate.\n"
                        " - svg: for diagrams and compact static visuals\n"
                        " - html: for widgets, charts, or richer interactive visuals\n"
                        " - mermaid: for diagrams that should remain easy to edit after "
                        "generation and can benefit from Mermaid's automatic layout and styling"
                    ),
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["standard", "expert"],
                    "description": (
                        "How challenging the requested visual is.\n"
                        " - standard: for straightforward diagrams, charts, and explainers\n"
                        " - expert: for especially complex, dense, or high-stakes visuals that "
                        "need a more capable model\n"
                        "Ignored when output_mode is mermaid."
                    ),
                },
                "follow_up_interactivity": {
                    "type": "boolean",
                    "description": (
                        "Whether the visual should include clickable follow-up interactions "
                        "that trigger another AI message. "
                        "This is nice to use when the visual includes elements that the user might "
                        "want to click on for more information, and when you want to create a more "
                        "conversational experience. Ignored when output_mode is mermaid."
                    ),
                },
            },
            "required": ["instructions", "context", "output_mode"],
        },
    },
}


class VisualiseToolResponse(BaseModel):
    mode: Literal["mermaid", "svg", "html"] = Field(...)
    content: str = Field(..., min_length=1)
    title: str | None = None


class VisualiseModelRequestError(RuntimeError):
    def __init__(self, message: str, *, response: Any = None):
        super().__init__(message)
        self.response = response


def _strip_outer_fence(value: str) -> str:
    match = OUTER_FENCE_PATTERN.match(value)
    if match:
        return match.group("body").strip()
    return value.strip()


def _looks_like_html_fragment(value: str) -> bool:
    stripped = value.lstrip()
    return stripped.startswith("<") and ">" in stripped


def _looks_like_mermaid_fragment(value: str) -> bool:
    stripped = value.lstrip()
    return any(stripped.startswith(prefix) for prefix in MERMAID_BLOCK_PREFIXES)


def _parse_visualise_response(content: str, expected_mode: str) -> VisualiseToolResponse:
    normalized = _strip_outer_fence(content)

    try:
        return VisualiseToolResponse.model_validate_json(normalized)
    except Exception:
        if normalized.startswith("<svg"):
            return VisualiseToolResponse(mode="svg", content=normalized)

        if _looks_like_html_fragment(normalized):
            return VisualiseToolResponse(mode="html", content=normalized)

        if expected_mode == "mermaid" or _looks_like_mermaid_fragment(normalized):
            return VisualiseToolResponse(mode="mermaid", content=normalized)

        raise


def _validate_visual_fragment(mode: str, content: str) -> str:
    normalized = _strip_outer_fence(content)
    if not normalized:
        raise ValueError("The visual content was empty.")

    if "```" in normalized:
        raise ValueError("The visual content must not contain nested Markdown fences.")

    if len(normalized.encode("utf-8")) > MAX_VISUAL_CONTENT_LENGTH:
        raise ValueError("The visual content exceeded the maximum supported size.")

    if FULL_DOCUMENT_TAG_PATTERN.search(normalized):
        raise ValueError("The visual content must be a fragment, not a full HTML document.")

    if mode == "mermaid":
        if _looks_like_html_fragment(normalized):
            raise ValueError("Mermaid visuals must be Mermaid source, not HTML.")
        return normalized

    if mode == "svg":
        if not normalized.lstrip().startswith("<svg"):
            raise ValueError("SVG visuals must start with <svg.")
        return normalized

    if normalized.lstrip().startswith("<svg"):
        raise ValueError("HTML visuals must not be returned in SVG mode.")

    return normalized


def _normalize_visual_title(
    provided_title: str | None,
    generated_title: str | None,
    instructions: str,
) -> str | None:
    candidate = " ".join(str(provided_title or "").split()).strip()
    if not candidate:
        candidate = " ".join(str(generated_title or "").split()).strip()
    if not candidate:
        candidate = " ".join(instructions.split()).strip()
    if not candidate:
        return None
    return candidate[:120]


def _build_visualise_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "visualise_tool_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    **VisualiseToolResponse.model_json_schema(),
                },
            },
        },
    }


def _extract_model_error_message(response: Any) -> str | None:
    if response is None:
        return None

    try:
        error_message = response.json().get("error", {}).get("message")
        if error_message:
            return str(error_message)
    except Exception:
        return None

    return None


async def _request_visualise_model_content(req, payload: dict[str, Any]) -> str:
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
        if not isinstance(content, str) or not content.strip():
            raise ValueError("The visual generator returned empty content.")
        return content
    except Exception as exc:
        raise VisualiseModelRequestError(str(exc), response=response) from exc


def _escape_markdown_link_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _build_visualise_embed_code(title: str | None, artifact_id: str) -> str:
    label = _escape_markdown_link_label(title or "Interactive visual")
    return f"[{label}](visualise://{artifact_id})"


async def _get_node_visualise_mode_overrides(req) -> dict[str, bool]:
    if not all(
        [
            getattr(req, "pg_engine", None),
            getattr(req, "graph_id", None),
            getattr(req, "node_id", None),
        ]
    ):
        return {}

    try:
        nodes = await get_nodes_by_ids(
            pg_engine=req.pg_engine,
            graph_id=req.graph_id,
            node_ids=[req.node_id],
        )
    except Exception as exc:
        logger.warning("Failed to fetch node-specific visualise settings: %s", exc)
        return {}

    if not nodes or not isinstance(nodes[0].data, dict):
        return {}

    visualise_modes = nodes[0].data.get("visualiseModes")
    if not isinstance(visualise_modes, dict):
        return {}

    overrides: dict[str, bool] = {}
    if "enableMermaid" in visualise_modes:
        overrides["mermaid"] = bool(visualise_modes.get("enableMermaid"))
    if "enableSvg" in visualise_modes:
        overrides["svg"] = bool(visualise_modes.get("enableSvg"))
    if "enableHtml" in visualise_modes:
        overrides["html"] = bool(visualise_modes.get("enableHtml"))
    return overrides


def _build_visual_artifact_document(mode: str, content: str, title: str | None) -> str:
    host_padding = "0"
    min_height = "180px" if mode == "svg" else "220px"
    document_title = escape(title or "Interactive visual")
    aria_label = escape(title or ("SVG diagram" if mode == "svg" else "Interactive visual"))
    bridge_config_type = json.dumps("meridian:visualise-artifact:config")
    bridge_prompt_type = json.dumps("meridian:visualise-artifact:prompt")
    bridge_height_type = json.dumps("meridian:visualise-artifact:height")
    csp_value = escape(VISUALISE_IFRAME_CSP, quote=True)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{document_title}</title>
<meta http-equiv="Content-Security-Policy" content="{csp_value}">
<style id="meridian-host-vars"></style>
<style>
html,body{{margin:0;padding:0;background:transparent;color:var(--color-soft-silk,#f4efe7);font-family:Outfit,ui-sans-serif,system-ui,sans-serif}}
body{{min-height:{min_height};overflow:auto}}
html,body{{scrollbar-width:none;-ms-overflow-style:none}}
html::-webkit-scrollbar,body::-webkit-scrollbar{{display:none}}
*,*::before,*::after{{box-sizing:border-box}}
#host{{min-height:{min_height};padding:{host_padding};background:transparent}}
svg{{display:block;max-width:100%;height:auto}}
button,input,select,textarea{{font:inherit}}
</style>
</head>
<body>
<div id="host" aria-label="{aria_label}">{content}</div>
<script>
const hostVars = document.getElementById('meridian-host-vars');
const configType = {bridge_config_type};
const promptType = {bridge_prompt_type};
const heightType = {bridge_height_type};
const clampPrompt = (value) => value.trim().slice(0, 2000);
const applyThemeCssVars = (cssVars) => {{
    if (typeof cssVars !== 'string') return;
    hostVars.textContent = cssVars.trim() ? `:root{{${{cssVars}}}}` : '';
}};
const reportHeight = () => {{
    const nextHeight = Math.max(
        document.documentElement.scrollHeight,
        document.body.scrollHeight,
        120
    );
    parent.postMessage({{ type: heightType, height: nextHeight }}, '*');
}};
window.addEventListener('message', (event) => {{
    const payload = event.data;
    if (!payload || payload.type !== configType) return;
    applyThemeCssVars(payload.themeCssVars);
    reportHeight();
}});
window.sendPrompt = function(text) {{
    if (typeof text !== 'string') return;
    const trimmed = clampPrompt(text);
    if (!trimmed) return;
    parent.postMessage({{ type: promptType, text: trimmed }}, '*');
}};
window.addEventListener('load', reportHeight);
window.addEventListener('resize', reportHeight);
if (window.ResizeObserver) {{
    const observer = new ResizeObserver(reportHeight);
    observer.observe(document.documentElement);
    observer.observe(document.body);
}}
requestAnimationFrame(reportHeight);
setTimeout(reportHeight, 60);
</script>
</body>
</html>"""


async def _persist_visual_artifact(
    *,
    req,
    mode: str,
    content: str,
    title: str | None,
) -> list[dict[str, object]]:
    if not getattr(req, "user_id", None) or not getattr(req, "pg_engine", None):
        raise RuntimeError("Visual artifacts could not be persisted in this execution context.")

    parsed_user_id = uuid.UUID(str(req.user_id))
    visual_id = uuid.uuid4().hex
    document = _build_visual_artifact_document(mode, content, title)
    document_bytes = document.encode("utf-8")

    return await persist_generated_artifacts(
        req=req,
        user_id=parsed_user_id,
        artifacts=[
            {
                "relative_path": "index.html",
                "name": "index.html",
                "content_type": "text/html",
                "size": len(document_bytes),
                "bytes": document_bytes,
            }
        ],
        category_folder_name=VISUALISE_FOLDER_NAME,
        run_folder_name=f"Visual {visual_id[:8]}",
        disk_base_subdirectory=PurePosixPath("generated_files") / "visualise" / visual_id,
    )


async def visualise(arguments: dict, req) -> dict:
    instructions = str(arguments.get("instructions", "")).strip()
    title = str(arguments.get("title", "")).strip()
    context = str(arguments.get("context", "")).strip()
    output_mode = str(arguments.get("output_mode", "svg") or "svg").strip().lower()
    difficulty = str(arguments.get("difficulty", "standard") or "standard").strip().lower()
    follow_up_interactivity = bool(arguments.get("follow_up_interactivity", False))
    if output_mode not in {"mermaid", "svg", "html"}:
        output_mode = "svg"
    if difficulty not in {"standard", "expert"}:
        difficulty = "standard"

    if not instructions:
        return {"error": "The 'instructions' field is required."}

    if not context:
        return {"error": "The 'context' field is required."}

    settings = await get_user_settings(req.pg_engine, req.user_id)
    node_mode_overrides = await _get_node_visualise_mode_overrides(req)
    mode_enabled_map = {
        "mermaid": bool(settings.toolsVisualise.enableMermaid)
        and node_mode_overrides.get("mermaid", True),
        "svg": bool(settings.toolsVisualise.enableSvg) and node_mode_overrides.get("svg", True),
        "html": bool(settings.toolsVisualise.enableHtml) and node_mode_overrides.get("html", True),
    }
    if not mode_enabled_map.get(output_mode, False):
        return {"error": f"Visual generation failed: '{output_mode}' output mode is disabled."}

    if output_mode == "mermaid":
        model = settings.toolsVisualise.defaultModel or "anthropic/claude-haiku-4.5"
        system_prompt = MERMAID_TOOL_SYSTEM_PROMPT
    else:
        if difficulty == "expert":
            model = settings.toolsVisualise.expertModel or "anthropic/claude-sonnet-4.6"
        else:
            model = settings.toolsVisualise.standardModel or "google/gemini-3-flash-preview"
        system_prompt = (
            VISUALISE_SVG_TOOL_SYSTEM_PROMPT
            if output_mode == "svg"
            else VISUALISE_HTML_TOOL_SYSTEM_PROMPT
        )

    if output_mode != "mermaid":
        user_prompt = (
            "Follow-up interactivity using sendPrompt(text): "
            f"{'required' if follow_up_interactivity else 'not required'}\n\n"
            f"Title:\n{title or 'None provided'}\n\n"
            f"Instructions:\n{instructions}\n\n"
            f"Context:\n{context}"
        )
    try:
        if output_mode == "mermaid":
            return await generate_mermaid_with_retry(
                req=req,
                model=model,
                system_prompt=system_prompt,
                title=title,
                instructions=instructions,
                context=context,
                enable_retry=bool(settings.toolsVisualise.enableMermaidRetry),
                max_retry=normalize_mermaid_retry_count(settings.toolsVisualise.maxMermaidRetry),
                build_payload=_build_visualise_payload,
                request_content=_request_visualise_model_content,
                parse_response=_parse_visualise_response,
                validate_fragment=_validate_visual_fragment,
                normalize_title=_normalize_visual_title,
                strip_outer_fence=_strip_outer_fence,
                logger=logger,
            )

        content = await _request_visualise_model_content(
            req,
            _build_visualise_payload(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.5,
            ),
        )
        parsed = _parse_visualise_response(content, output_mode)
        if parsed.mode != output_mode:
            raise ValueError(
                f"The visual generator returned mode '{parsed.mode}' but '{output_mode}' "
                "was requested."
            )
        validated_content = _validate_visual_fragment(parsed.mode, parsed.content)
        normalized_title = _normalize_visual_title(title, parsed.title, instructions)
        persisted_artifacts = await _persist_visual_artifact(
            req=req,
            mode=parsed.mode,
            content=validated_content,
            title=normalized_title,
        )
        artifact_id = str(persisted_artifacts[0]["id"]) if persisted_artifacts else ""
        if not artifact_id:
            raise RuntimeError("Visual artifact persistence did not return an artifact id.")
        enriched_artifacts = []
        for artifact in persisted_artifacts:
            enriched_artifact = dict(artifact)
            next_artifact_id = str(enriched_artifact.get("id") or "").strip()
            if next_artifact_id:
                enriched_artifact["embed_code"] = _build_visualise_embed_code(
                    normalized_title,
                    next_artifact_id,
                )
            enriched_artifacts.append(enriched_artifact)
        return {
            "artifact_id": artifact_id,
            "artifacts": enriched_artifacts,
            **({"title": normalized_title} if normalized_title else {}),
        }
    except HTTPException as exc:
        logger.warning(
            "Visualise artifact persistence rejected for user %s: %s",
            req.user_id,
            exc.detail,
        )
        return {"error": f"Visual generation failed: {exc.detail}"}
    except VisualiseModelRequestError as exc:
        logger.error("Visualise tool failed: %s", exc, exc_info=True)
        error_message = _extract_model_error_message(exc.response)
        return {"error": f"Visual generation failed: {error_message or str(exc)}"}
    except MermaidValidatorRuntimeError as exc:
        logger.error("Visualise tool failed: %s", exc, exc_info=True)
        return {"error": f"Visual generation failed: {str(exc)}"}
    except Exception as exc:
        logger.error("Visualise tool failed: %s", exc, exc_info=True)
        return {"error": f"Visual generation failed: {str(exc)}"}
