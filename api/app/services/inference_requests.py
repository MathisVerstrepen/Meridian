from typing import Any, TypeAlias

from database.redis.redis_ops import RedisManager
from models.inference import InferenceCredentials, InferenceProviderEnum
from services.claude_agent import (
    ClaudeAgentReqChat,
    make_claude_agent_request_non_streaming,
    stream_claude_agent_response,
)
from services.gemini_cli import (
    GeminiCliReqChat,
    make_gemini_cli_request_non_streaming,
    stream_gemini_cli_response,
)
from services.github_copilot import (
    GitHubCopilotReqChat,
    make_github_copilot_request_non_streaming,
    stream_github_copilot_response,
)
from services.inference import resolve_model_provider
from services.openai_codex import (
    OpenAICodexReqChat,
    make_openai_codex_request_non_streaming,
    stream_openai_codex_response,
)
from services.openrouter import (
    OpenRouterReqChat,
    make_openrouter_request_non_streaming,
    stream_openrouter_response,
)
from services.z_ai_coding_plan import (
    ZAiCodingPlanReqChat,
    make_z_ai_coding_plan_request_non_streaming,
    stream_z_ai_coding_plan_response,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

InferenceRequest: TypeAlias = (
    OpenRouterReqChat
    | ClaudeAgentReqChat
    | GitHubCopilotReqChat
    | ZAiCodingPlanReqChat
    | GeminiCliReqChat
    | OpenAICodexReqChat
)


def build_inference_request(
    *,
    credentials: InferenceCredentials,
    model: str,
    messages,
    config,
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
    model_id: str | None = None,
    node_id: str | None = None,
    graph_id: str | None = None,
    is_title_generation: bool = False,
    node_type,
    schema=None,
    stream: bool = True,
    http_client=None,
    file_uuids: list[str] | None = None,
    file_hashes: dict[str, str] | None = None,
    pdf_engine: str = "default",
    selected_tools=None,
    sandbox_input_files=None,
    sandbox_input_warnings=None,
) -> InferenceRequest:
    provider = resolve_model_provider(model)

    common_kwargs: dict[str, Any] = {
        "model": model,
        "model_id": model_id,
        "messages": messages,
        "config": config,
        "user_id": user_id,
        "pg_engine": pg_engine,
        "node_id": node_id,
        "graph_id": graph_id,
        "is_title_generation": is_title_generation,
        "node_type": node_type,
        "schema": schema,
        "stream": stream,
        "file_uuids": file_uuids,
        "file_hashes": file_hashes,
        "pdf_engine": pdf_engine,
        "selected_tools": selected_tools,
        "sandbox_input_files": sandbox_input_files,
        "sandbox_input_warnings": sandbox_input_warnings,
    }

    if provider == InferenceProviderEnum.CLAUDE_AGENT:
        if not credentials.claude_agent_oauth_token:
            raise ValueError("Claude Agent is not connected for this account.")
        return ClaudeAgentReqChat(
            oauth_token=credentials.claude_agent_oauth_token,
            http_client=http_client,
            **common_kwargs,
        )
    if provider == InferenceProviderEnum.Z_AI_CODING_PLAN:
        if not credentials.z_ai_coding_plan_api_key:
            raise ValueError("Z.AI Coding Plan is not connected for this account.")
        return ZAiCodingPlanReqChat(
            api_key=credentials.z_ai_coding_plan_api_key,
            http_client=http_client,
            **common_kwargs,
        )
    if provider == InferenceProviderEnum.GITHUB_COPILOT:
        if not credentials.github_copilot_github_token:
            raise ValueError("GitHub Copilot is not connected for this account.")
        return GitHubCopilotReqChat(
            github_token=credentials.github_copilot_github_token,
            http_client=http_client,
            **common_kwargs,
        )
    if provider == InferenceProviderEnum.GEMINI_CLI:
        if not credentials.gemini_cli_oauth_creds_json:
            raise ValueError("Gemini CLI is not connected for this account.")
        return GeminiCliReqChat(
            oauth_creds_json=credentials.gemini_cli_oauth_creds_json,
            http_client=http_client,
            **common_kwargs,
        )
    if provider == InferenceProviderEnum.OPENAI_CODEX:
        if not credentials.openai_codex_auth_json:
            raise ValueError("OpenAI Codex is not connected for this account.")
        return OpenAICodexReqChat(
            auth_json=credentials.openai_codex_auth_json,
            http_client=http_client,
            **common_kwargs,
        )

    if not credentials.openrouter_api_key:
        raise ValueError("Invalid OpenRouter API key.")

    return OpenRouterReqChat(
        api_key=credentials.openrouter_api_key,
        http_client=http_client,
        **common_kwargs,
    )


async def make_inference_request_non_streaming(
    req: InferenceRequest,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    if isinstance(req, ClaudeAgentReqChat):
        return await make_claude_agent_request_non_streaming(req, pg_engine)
    if isinstance(req, GitHubCopilotReqChat):
        return await make_github_copilot_request_non_streaming(req, pg_engine)
    if isinstance(req, ZAiCodingPlanReqChat):
        return await make_z_ai_coding_plan_request_non_streaming(req, pg_engine)
    if isinstance(req, GeminiCliReqChat):
        return await make_gemini_cli_request_non_streaming(req, pg_engine)
    if isinstance(req, OpenAICodexReqChat):
        return await make_openai_codex_request_non_streaming(req, pg_engine)
    return await make_openrouter_request_non_streaming(req, pg_engine)


async def stream_inference_response(
    req: InferenceRequest,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: dict | None = None,
):
    if isinstance(req, ClaudeAgentReqChat):
        async for chunk in stream_claude_agent_response(
            req, pg_engine, redis_manager, final_data_container
        ):
            yield chunk
        return
    if isinstance(req, GitHubCopilotReqChat):
        async for chunk in stream_github_copilot_response(
            req, pg_engine, redis_manager, final_data_container
        ):
            yield chunk
        return
    if isinstance(req, ZAiCodingPlanReqChat):
        async for chunk in stream_z_ai_coding_plan_response(
            req, pg_engine, redis_manager, final_data_container
        ):
            yield chunk
        return
    if isinstance(req, GeminiCliReqChat):
        async for chunk in stream_gemini_cli_response(
            req, pg_engine, redis_manager, final_data_container
        ):
            yield chunk
        return
    if isinstance(req, OpenAICodexReqChat):
        async for chunk in stream_openai_codex_response(
            req, pg_engine, redis_manager, final_data_container
        ):
            yield chunk
        return

    async for chunk in stream_openrouter_response(
        req, pg_engine, redis_manager, final_data_container
    ):
        yield chunk
