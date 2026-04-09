import uuid
from typing import Any, Optional, cast

from database.pg.graph_ops.graph_crud import assert_graph_access
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from database.pg.models import PromptImproverRunStatusEnum, PromptTemplate
from database.pg.prompt_improver_ops import (
    PromptImproverReviewPayload,
    create_prompt_improver_run,
    get_prompt_improver_run_by_id,
    list_prompt_improver_changes_for_run,
    list_prompt_improver_runs_for_node,
    update_prompt_improver_change_statuses,
    update_prompt_improver_run,
)
from database.pg.prompt_template_ops.prompt_template_crud import get_prompt_template_by_id
from models.message import NodeTypeEnum
from models.prompt_improver import (
    PromptImproverDraftResponse,
    PromptImproverRunRead,
    PromptImproverTarget,
    PromptImproverTemplateSnapshot,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

from .context import (
    apply_optimizer_profile,
    build_target_snapshot,
    resolve_targets,
    validate_target_selection,
)
from .mapping import map_run_to_read, merge_history_runs
from .phases import run_draft_phase, run_feedback_phase, run_improve_phase
from .review import compose_prompt
from .taxonomy import sanitize_dimension_ids


async def create_prompt_improver_draft(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    graph_id: str,
    node_id: str,
    target_id: str | None,
    optimizer_model_id: str | None,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
    http_client,
) -> PromptImproverDraftResponse:
    await assert_graph_access(pg_engine, graph_id, user_id)
    prompt_nodes = await get_nodes_by_ids(pg_engine, graph_id, [node_id])
    if not prompt_nodes:
        raise ValueError("Prompt node not found")
    prompt_node = prompt_nodes[0]
    if prompt_node.type != NodeTypeEnum.PROMPT:
        raise ValueError("Prompt improver can only be used on prompt nodes")
    if not isinstance(prompt_node.data, dict):
        raise ValueError("Prompt node data is invalid")

    current_prompt = str(prompt_node.data.get("prompt") or "")
    template_snapshot = None
    template_id = prompt_node.data.get("templateId")
    if isinstance(template_id, str) and template_id:
        template = await get_prompt_template_by_id(pg_engine, uuid.UUID(template_id))
        if isinstance(template, PromptTemplate):
            template_snapshot = PromptImproverTemplateSnapshot(
                id=str(template.id),
                name=template.name,
                description=template.description,
                template_text=template.template_text,
            )

    targets = await resolve_targets(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        user_id=user_id,
        available_models=available_models,
    )
    selected_target = validate_target_selection(targets, target_id)
    history = await list_prompt_improver_runs_for_node(
        pg_engine,
        user_id=user_id,
        graph_id=graph_id,
        node_id=node_id,
    )

    if not selected_target:
        return PromptImproverDraftResponse(
            requires_target_selection=True,
            current_prompt=current_prompt,
            targets=targets,
            active_run=None,
            history=[await map_run_to_read(pg_engine, run) for run in history],
        )

    target_snapshot = apply_optimizer_profile(
        build_target_snapshot(selected_target),
        optimizer_model_id=optimizer_model_id,
        available_models=available_models,
    )
    run = await create_prompt_improver_run(
        pg_engine,
        user_id=user_id,
        graph_id=graph_id,
        node_id=node_id,
        parent_run_id=None,
        target_id=selected_target.id,
        target_node_id=selected_target.node_id,
        target_snapshot=target_snapshot,
        source_prompt=current_prompt,
        source_template_snapshot=(
            template_snapshot.model_dump(mode="json") if template_snapshot else None
        ),
        selected_dimension_ids=[],
        recommended_dimension_ids=[],
        audit=None,
        improved_prompt=None,
        feedback=None,
        active_phase=None,
        active_tool_call_id=None,
        clarification_tool_call_ids=[],
        status=PromptImproverRunStatusEnum.DRAFT.value,
    )
    active_run = await run_draft_phase(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        run=run,
        user_id=user_id,
        available_models=available_models,
        http_client=http_client,
    )
    mapped_history = [await map_run_to_read(pg_engine, stored_run) for stored_run in history]
    return PromptImproverDraftResponse(
        requires_target_selection=False,
        current_prompt=current_prompt,
        targets=targets,
        active_run=active_run,
        history=merge_history_runs(active_run, mapped_history),
    )


async def improve_prompt_improver_run(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run_id: str,
    user_id: str,
    selected_dimension_ids: list[str],
    optimizer_model_id: str | None,
    available_models: list[dict[str, Any]] | None,
    http_client,
) -> PromptImproverRunRead:
    run = await get_prompt_improver_run_by_id(pg_engine, run_id=run_id, user_id=user_id)
    selected_dimensions = sanitize_dimension_ids(selected_dimension_ids) or (
        run.recommended_dimension_ids or []
    )
    updates: dict[str, Any] = {
        "selected_dimension_ids": selected_dimensions,
        "active_phase": "improve",
    }
    if optimizer_model_id is not None:
        updates["target_snapshot"] = apply_optimizer_profile(
            cast(dict[str, Any], run.target_snapshot),
            optimizer_model_id=optimizer_model_id,
            available_models=available_models,
        )

    updated_run = await update_prompt_improver_run(
        pg_engine,
        run_id=str(run.id),
        user_id=user_id,
        **updates,
    )
    return await run_improve_phase(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        run=updated_run,
        user_id=user_id,
        available_models=available_models,
        http_client=http_client,
    )


async def review_prompt_improver_run(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    run_id: str,
    user_id: str,
    changes: list[PromptImproverReviewPayload],
    mark_applied: bool,
) -> PromptImproverRunRead:
    await update_prompt_improver_change_statuses(
        pg_engine,
        run_id=run_id,
        changes=changes,
    )
    updates: dict[str, Any] = {}
    if mark_applied:
        updates["status"] = PromptImproverRunStatusEnum.APPLIED.value
    if updates:
        await update_prompt_improver_run(
            pg_engine,
            run_id=run_id,
            user_id=user_id,
            **updates,
        )
    run = await get_prompt_improver_run_by_id(pg_engine, run_id=run_id, user_id=user_id)
    return await map_run_to_read(pg_engine, run)


async def feedback_prompt_improver_run(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run_id: str,
    user_id: str,
    feedback: str,
    selected_dimension_ids: list[str],
    optimizer_model_id: str | None,
    available_models: list[dict[str, Any]] | None,
    http_client,
) -> PromptImproverRunRead:
    parent_run = await get_prompt_improver_run_by_id(pg_engine, run_id=run_id, user_id=user_id)
    parent_changes = await list_prompt_improver_changes_for_run(pg_engine, run_id=run_id)
    composed_prompt = compose_prompt(parent_run.source_prompt, parent_changes)
    selected_dimensions = sanitize_dimension_ids(selected_dimension_ids) or (
        parent_run.selected_dimension_ids or parent_run.recommended_dimension_ids or []
    )
    target = PromptImproverTarget.model_validate(parent_run.target_snapshot)
    parent_target_snapshot = cast(dict[str, Any], parent_run.target_snapshot)
    target_snapshot = apply_optimizer_profile(
        build_target_snapshot(target),
        optimizer_model_id=(
            optimizer_model_id
            if optimizer_model_id is not None
            else cast(Optional[str], parent_target_snapshot.get("optimizer_model_id"))
        ),
        available_models=available_models,
    )
    child_run = await create_prompt_improver_run(
        pg_engine,
        user_id=user_id,
        graph_id=str(parent_run.graph_id),
        node_id=parent_run.node_id,
        parent_run_id=str(parent_run.id),
        target_id=target.id,
        target_node_id=target.node_id,
        target_snapshot=target_snapshot,
        source_prompt=composed_prompt,
        source_template_snapshot=cast(
            Optional[dict[str, Any]], parent_run.source_template_snapshot
        ),
        selected_dimension_ids=selected_dimensions,
        recommended_dimension_ids=[],
        audit=None,
        improved_prompt=None,
        feedback=feedback,
        active_phase="feedback",
        active_tool_call_id=None,
        clarification_tool_call_ids=[],
        status=PromptImproverRunStatusEnum.DRAFT.value,
    )
    return await run_feedback_phase(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        run=child_run,
        user_id=user_id,
        available_models=available_models,
        http_client=http_client,
    )
