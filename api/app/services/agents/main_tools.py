"""Resolve main-model tools independently of every subagent's profile permissions."""

from types import SimpleNamespace

from models.message import NodeTypeEnum
from services.settings import get_user_settings


async def resolve_main_tools(execution):
    from services.stream import _get_auto_tool_candidates, _resolve_auto_selected_tools

    config = execution.node_config
    if not config.autoSelectTools:
        return config.selectedTools

    # Use the persisted node/model, never tool policy supplied in a generation request.
    nodes = [SimpleNamespace(data=execution.node_data)]
    if "auto_selected_tools" not in execution.state:
        selected = await _resolve_auto_selected_tools(
            pg_engine=execution.engine,
            neo4j_driver=execution.neo4j_driver,
            request_data=execution.request.model_copy(update={"model": config.model}),
            user_id=str(execution.user_id),
            http_client=execution.http_client,
            graph_config=execution.config,
            inference_credentials=execution.credentials,
            node=nodes,
            node_type_enum=NodeTypeEnum.AGENT,
            available_models=execution.available_models,
        )
        execution.state["auto_selected_tools"] = [tool.value for tool in selected]

    # Keep the initial selection on resume, filtered by current settings/capabilities.
    settings = await get_user_settings(execution.engine, str(execution.user_id))
    candidates = _get_auto_tool_candidates(NodeTypeEnum.AGENT, nodes, settings, config.model)
    return [tool for tool in candidates if tool.value in execution.state["auto_selected_tools"]]
