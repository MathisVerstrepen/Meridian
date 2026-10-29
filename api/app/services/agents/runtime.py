"""Task-local policy: child tasks get their own policy, never their parent's tools."""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from models.message import ToolEnum


@dataclass
class AgentPolicy:
    execution_id: str
    run_id: str
    agent_id: str | None
    version: int | None
    tools: list[ToolEnum]
    delegate: Callable[[dict, Any], Awaitable[Any]] | None = None
    record_tool: Callable[..., Awaitable[None]] | None = None
    paused: bool = False


current_policy: ContextVar[AgentPolicy | None] = ContextVar("agent_policy", default=None)

RUNTIME_PERMISSIONS = {
    "web_search": ToolEnum.WEB_SEARCH,
    "fetch_page_content": ToolEnum.LINK_EXTRACTION,
    "generate_image": ToolEnum.IMAGE_GENERATION,
    "edit_image": ToolEnum.IMAGE_GENERATION,
    "generate_video": ToolEnum.IMAGE_GENERATION,
    "inspect_image": ToolEnum.IMAGE_GENERATION,
    "execute_code": ToolEnum.EXECUTE_CODE,
    "visualise": ToolEnum.VISUALISE,
    "ask_user": ToolEnum.ASK_USER,
}


def permitted_tools(tools):
    """Dependencies may restrict availability, but cannot grant another permission."""
    return [
        tool for tool in tools if tool != ToolEnum.WEB_SEARCH or ToolEnum.LINK_EXTRACTION in tools
    ]


def guard_handler(name, handler):
    async def guarded(arguments, req):
        policy = current_policy.get()
        if policy and RUNTIME_PERMISSIONS.get(name) not in permitted_tools(policy.tools):
            if policy.record_tool:
                await policy.record_tool(
                    name, arguments, {"error": "Agent tool permission denied."}
                )
            raise PermissionError(
                f"{name} is not allowed by this Agent's current tool permissions."
            )
        try:
            result = await handler(arguments, req)
        except Exception as exc:
            if policy and policy.record_tool:
                await policy.record_tool(name, arguments, {"error": str(exc)})
            raise
        if policy and policy.record_tool:
            from services.tools.runtime_results import unwrap_tool_execution_result

            stored_result, _ = unwrap_tool_execution_result(result)
            await policy.record_tool(name, arguments, stored_result)
        return result

    return guarded


async def delegate_handler(arguments, req):
    policy = current_policy.get()
    if policy is None or policy.delegate is None:
        raise PermissionError(
            "Delegation is only available to the main model with authorized subagents."
        )
    return await policy.delegate(arguments, req)


def delegation_tool() -> list[dict[str, Any]]:
    policy = current_policy.get()
    if policy is None or policy.delegate is None:
        return []
    return [
        {
            "type": "function",
            "function": {
                "name": "delegate_agents",
                "description": "Delegate explicit tasks to eligible Team members. Put "
                "independent calls "
                "in one batch to run them in parallel. Use successive rounds for dependent "
                "work. You may answer directly without delegation. Synthesize their results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "calls": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 16,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {"type": "string"},
                                    "instructions": {"type": "string"},
                                },
                                "required": ["agent_id", "instructions"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["calls"],
                    "additionalProperties": False,
                },
            },
        }
    ]
