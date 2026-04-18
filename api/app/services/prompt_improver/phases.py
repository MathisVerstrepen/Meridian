import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, cast

from database.pg.chat_ops import get_tool_call_by_id, update_tool_call_by_id
from database.pg.models import PromptImproverRun, PromptImproverRunStatusEnum, ToolCallStatusEnum
from database.pg.prompt_improver_ops import (
    PromptImproverChangePayload,
    get_prompt_improver_run_by_id,
    replace_prompt_improver_changes,
    update_prompt_improver_run,
)
from database.redis.redis_ops import RedisManager
from models.message import MessageRoleEnum, NodeTypeEnum, ToolEnum
from models.prompt_improver import PromptImproverAudit, PromptImproverRunRead
from models.tool_question import AskUserArguments
from services.graph_service import get_effective_graph_config
from services.inference_requests import build_inference_request, stream_inference_response
from services.tools.ask_user import build_ask_user_answer_result, normalize_ask_user_answers
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

from .context import (
    apply_optimizer_profile,
    build_user_message_content,
    resolve_run_execution_context,
)
from .llm import run_structured_prompt
from .mapping import load_clarification_rounds, map_run_to_read
from .prompt_builders import (
    analyzer_system_prompt,
    build_analyzer_user_prompt,
    build_draft_clarification_prompt,
    build_explainer_user_prompt,
    build_generator_user_prompt,
    build_improve_clarification_prompt,
    build_issue_detector_user_prompt,
    clarification_system_prompt,
    explainer_system_prompt,
    format_clarification_context,
    generator_system_prompt,
    issue_detector_system_prompt,
)
from .review import build_diff_clusters, normalize_explanations
from .schemas import (
    AnalyzerResponseSchema,
    ChangeExplanationResponseSchema,
    ImprovementResponseSchema,
    IssueDetectorResponseSchema,
    PromptImproverClarificationDecision,
)
from .taxonomy import normalize_audit, sanitize_dimension_ids

logger = logging.getLogger("uvicorn.error")


def _extract_stream_error(chunks: list[str]) -> str | None:
    payload = "".join(chunks)
    start_index = payload.find("[ERROR]")
    if start_index < 0:
        return None

    end_index = payload.find("[!ERROR]", start_index)
    if end_index < 0:
        return None

    return payload[start_index + len("[ERROR]") : end_index].strip() or None


async def run_prompt_improver_clarification_round(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    run: PromptImproverRun,
    user_id: str,
    model_id: str,
    tools_support: bool,
    phase: str,
    user_prompt: str,
    attachment_contents: list[dict[str, Any]],
    redis_manager: RedisManager | None,
    http_client,
) -> PromptImproverClarificationDecision:
    if not tools_support:
        return PromptImproverClarificationDecision(pending_tool_call_id=None)

    if redis_manager is None:
        raise ValueError("Prompt improver clarification requires Redis continuation state.")

    graph_config, _, inference_credentials = await get_effective_graph_config(
        pg_engine=pg_engine,
        graph_id=str(run.graph_id),
        user_id=user_id,
    )
    messages: list[dict[str, Any]] = [
        {"role": MessageRoleEnum.system.value, "content": clarification_system_prompt(phase)},
        {
            "role": MessageRoleEnum.user.value,
            "content": build_user_message_content(user_prompt, attachment_contents),
        },
    ]

    req = build_inference_request(
        credentials=inference_credentials,
        model=model_id,
        messages=messages,
        config=graph_config,
        user_id=user_id,
        pg_engine=pg_engine,
        graph_id=str(run.graph_id),
        node_id=run.node_id,
        node_type=NodeTypeEnum.TEXT_TO_TEXT,
        http_client=http_client,
        selected_tools=[ToolEnum.ASK_USER],
    )

    final_data_container: dict[str, Any] = {}
    streamed_chunks: list[str] = []
    async for chunk in stream_inference_response(
        req, pg_engine, redis_manager, final_data_container
    ):
        streamed_chunks.append(chunk)

    if stream_error := _extract_stream_error(streamed_chunks):
        raise ValueError(stream_error)

    pending_tool_call_id = (
        str(final_data_container.get("pending_tool_call_id") or "").strip() or None
    )
    if not pending_tool_call_id:
        return PromptImproverClarificationDecision(pending_tool_call_id=None)

    clarification_tool_call_ids = [
        tool_call_id
        for tool_call_id in (run.clarification_tool_call_ids or [])
        if isinstance(tool_call_id, str)
    ]
    if pending_tool_call_id not in clarification_tool_call_ids:
        clarification_tool_call_ids.append(pending_tool_call_id)

    await update_prompt_improver_run(
        pg_engine,
        run_id=str(run.id),
        user_id=user_id,
        status=PromptImproverRunStatusEnum.PENDING_USER_INPUT.value,
        active_phase=phase,
        active_tool_call_id=pending_tool_call_id,
        clarification_tool_call_ids=clarification_tool_call_ids,
    )
    return PromptImproverClarificationDecision(pending_tool_call_id=pending_tool_call_id)


async def generate_prompt_improvement(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    user_id: str,
    model_id: str,
    source_prompt: str,
    selected_dimensions: list[str],
    audit: PromptImproverAudit,
    target_snapshot: dict[str, Any],
    sibling_context_text: str,
    attachment_contents: list[dict[str, Any]],
    issue_detector: IssueDetectorResponseSchema,
    feedback: str | None,
    clarification_context_text: str,
    http_client,
) -> tuple[str, list[PromptImproverChangePayload]]:
    improved = cast(
        ImprovementResponseSchema,
        await run_structured_prompt(
            pg_engine=pg_engine,
            graph_id=graph_id,
            user_id=user_id,
            model_id=model_id,
            schema=ImprovementResponseSchema,
            system_prompt=generator_system_prompt(),
            user_prompt=build_user_message_content(
                build_generator_user_prompt(
                    source_prompt=source_prompt,
                    selected_dimensions=selected_dimensions,
                    audit=audit,
                    target_snapshot=target_snapshot,
                    sibling_context_text=sibling_context_text,
                    issue_detector=issue_detector,
                    feedback=feedback,
                    clarification_context_text=clarification_context_text,
                ),
                attachment_contents,
            ),
            http_client=http_client,
        ),
    )

    diff_clusters = build_diff_clusters(source_prompt, improved.improved_prompt)
    explained_changes: list[PromptImproverChangePayload] = []
    if diff_clusters:
        explanations = cast(
            ChangeExplanationResponseSchema,
            await run_structured_prompt(
                pg_engine=pg_engine,
                graph_id=graph_id,
                user_id=user_id,
                model_id=model_id,
                schema=ChangeExplanationResponseSchema,
                system_prompt=explainer_system_prompt(),
                user_prompt=build_explainer_user_prompt(
                    source_prompt=source_prompt,
                    improved_prompt=improved.improved_prompt,
                    changes=diff_clusters,
                    selected_dimensions=selected_dimensions,
                ),
                http_client=http_client,
            ),
        )
        explained_changes = normalize_explanations(
            explanations,
            diff_clusters,
            selected_dimensions,
        )

    return improved.improved_prompt, explained_changes


async def run_draft_phase(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run: PromptImproverRun,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
    redis_manager: RedisManager | None,
    http_client,
) -> PromptImproverRunRead:
    _, target_snapshot, context_bundle, optimizer_model, optimizer_tools_support = (
        await resolve_run_execution_context(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            run=run,
            user_id=user_id,
            available_models=available_models,
            http_client=http_client,
        )
    )
    clarification_context_text = format_clarification_context(
        await load_clarification_rounds(pg_engine, run)
    )
    clarification = await run_prompt_improver_clarification_round(
        pg_engine=pg_engine,
        run=run,
        user_id=user_id,
        model_id=optimizer_model,
        tools_support=optimizer_tools_support,
        phase="draft",
        user_prompt=build_draft_clarification_prompt(
            source_prompt=run.source_prompt,
            target_snapshot=target_snapshot,
            sibling_context_text=context_bundle.sibling_context_text,
            template_snapshot=cast(Optional[dict[str, Any]], run.source_template_snapshot),
            clarification_context_text=clarification_context_text,
        ),
        attachment_contents=context_bundle.attachment_contents,
        redis_manager=redis_manager,
        http_client=http_client,
    )
    if clarification.pending_tool_call_id:
        pending_run = await get_prompt_improver_run_by_id(
            pg_engine,
            run_id=str(run.id),
            user_id=user_id,
        )
        return await map_run_to_read(pg_engine, pending_run)

    analyzer_result, issue_detector_result = cast(
        tuple[AnalyzerResponseSchema, IssueDetectorResponseSchema],
        await asyncio.gather(
            run_structured_prompt(
                pg_engine=pg_engine,
                graph_id=str(run.graph_id),
                user_id=user_id,
                model_id=optimizer_model,
                schema=AnalyzerResponseSchema,
                system_prompt=analyzer_system_prompt(),
                user_prompt=build_user_message_content(
                    build_analyzer_user_prompt(
                        source_prompt=run.source_prompt,
                        target_snapshot=target_snapshot,
                        sibling_context_text=context_bundle.sibling_context_text,
                        template_snapshot=cast(
                            Optional[dict[str, Any]], run.source_template_snapshot
                        ),
                        clarification_context_text=clarification_context_text,
                    ),
                    context_bundle.attachment_contents,
                ),
                http_client=http_client,
            ),
            run_structured_prompt(
                pg_engine=pg_engine,
                graph_id=str(run.graph_id),
                user_id=user_id,
                model_id=optimizer_model,
                schema=IssueDetectorResponseSchema,
                system_prompt=issue_detector_system_prompt(),
                user_prompt=build_user_message_content(
                    build_issue_detector_user_prompt(
                        source_prompt=run.source_prompt,
                        target_snapshot=target_snapshot,
                        sibling_context_text=context_bundle.sibling_context_text,
                        clarification_context_text=clarification_context_text,
                    ),
                    context_bundle.attachment_contents,
                ),
                http_client=http_client,
            ),
        ),
    )
    audit, recommended_dimension_ids = normalize_audit(analyzer_result, issue_detector_result)
    updated_run = await update_prompt_improver_run(
        pg_engine,
        run_id=str(run.id),
        user_id=user_id,
        recommended_dimension_ids=recommended_dimension_ids,
        audit=audit.model_dump(mode="json"),
        status=PromptImproverRunStatusEnum.DRAFT.value,
        active_phase=None,
        active_tool_call_id=None,
    )
    return await map_run_to_read(pg_engine, updated_run)


async def run_improve_phase(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run: PromptImproverRun,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
    redis_manager: RedisManager | None,
    http_client,
) -> PromptImproverRunRead:
    _, target_snapshot, context_bundle, optimizer_model, optimizer_tools_support = (
        await resolve_run_execution_context(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            run=run,
            user_id=user_id,
            available_models=available_models,
            http_client=http_client,
        )
    )
    audit = PromptImproverAudit.model_validate(run.audit) if run.audit else None
    if not audit:
        raise ValueError("Prompt improver run has no audit to improve from")

    selected_dimensions = sanitize_dimension_ids(run.selected_dimension_ids) or (
        run.recommended_dimension_ids or []
    )
    clarification_context_text = format_clarification_context(
        await load_clarification_rounds(pg_engine, run)
    )
    clarification = await run_prompt_improver_clarification_round(
        pg_engine=pg_engine,
        run=run,
        user_id=user_id,
        model_id=optimizer_model,
        tools_support=optimizer_tools_support,
        phase="improve",
        user_prompt=build_improve_clarification_prompt(
            source_prompt=run.source_prompt,
            selected_dimensions=selected_dimensions,
            target_snapshot=target_snapshot,
            sibling_context_text=context_bundle.sibling_context_text,
            audit=audit,
            feedback=run.feedback,
            clarification_context_text=clarification_context_text,
        ),
        attachment_contents=context_bundle.attachment_contents,
        redis_manager=redis_manager,
        http_client=http_client,
    )
    if clarification.pending_tool_call_id:
        pending_run = await get_prompt_improver_run_by_id(
            pg_engine,
            run_id=str(run.id),
            user_id=user_id,
        )
        return await map_run_to_read(pg_engine, pending_run)

    issue_detector = IssueDetectorResponseSchema(
        priority_notes=[issue.description for issue in audit.detected_issues]
    )
    improved_prompt, explained_changes = await generate_prompt_improvement(
        pg_engine=pg_engine,
        graph_id=str(run.graph_id),
        user_id=user_id,
        model_id=optimizer_model,
        source_prompt=run.source_prompt,
        selected_dimensions=selected_dimensions,
        audit=audit,
        target_snapshot=target_snapshot,
        sibling_context_text=context_bundle.sibling_context_text,
        attachment_contents=context_bundle.attachment_contents,
        issue_detector=issue_detector,
        feedback=run.feedback,
        clarification_context_text=clarification_context_text,
        http_client=http_client,
    )
    await replace_prompt_improver_changes(
        pg_engine,
        run_id=str(run.id),
        changes=explained_changes,
    )
    updated_run = await update_prompt_improver_run(
        pg_engine,
        run_id=str(run.id),
        user_id=user_id,
        selected_dimension_ids=selected_dimensions,
        improved_prompt=improved_prompt,
        status=PromptImproverRunStatusEnum.IMPROVED.value,
        active_phase=None,
        active_tool_call_id=None,
    )
    return await map_run_to_read(pg_engine, updated_run)


async def run_feedback_phase(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run: PromptImproverRun,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
    redis_manager: RedisManager | None,
    http_client,
) -> PromptImproverRunRead:
    _, target_snapshot, context_bundle, optimizer_model, optimizer_tools_support = (
        await resolve_run_execution_context(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            run=run,
            user_id=user_id,
            available_models=available_models,
            http_client=http_client,
        )
    )
    clarification_context_text = format_clarification_context(
        await load_clarification_rounds(pg_engine, run)
    )
    clarification = await run_prompt_improver_clarification_round(
        pg_engine=pg_engine,
        run=run,
        user_id=user_id,
        model_id=optimizer_model,
        tools_support=optimizer_tools_support,
        phase="feedback",
        user_prompt=build_improve_clarification_prompt(
            source_prompt=run.source_prompt,
            selected_dimensions=run.selected_dimension_ids or run.recommended_dimension_ids or [],
            target_snapshot=target_snapshot,
            sibling_context_text=context_bundle.sibling_context_text,
            audit=PromptImproverAudit.model_validate(run.audit) if run.audit else None,
            feedback=run.feedback,
            clarification_context_text=clarification_context_text,
        ),
        attachment_contents=context_bundle.attachment_contents,
        redis_manager=redis_manager,
        http_client=http_client,
    )
    if clarification.pending_tool_call_id:
        pending_run = await get_prompt_improver_run_by_id(
            pg_engine,
            run_id=str(run.id),
            user_id=user_id,
        )
        return await map_run_to_read(pg_engine, pending_run)

    analyzer_result, issue_detector_result = cast(
        tuple[AnalyzerResponseSchema, IssueDetectorResponseSchema],
        await asyncio.gather(
            run_structured_prompt(
                pg_engine=pg_engine,
                graph_id=str(run.graph_id),
                user_id=user_id,
                model_id=optimizer_model,
                schema=AnalyzerResponseSchema,
                system_prompt=analyzer_system_prompt(),
                user_prompt=build_user_message_content(
                    build_analyzer_user_prompt(
                        source_prompt=run.source_prompt,
                        target_snapshot=target_snapshot,
                        sibling_context_text=context_bundle.sibling_context_text,
                        template_snapshot=cast(
                            Optional[dict[str, Any]], run.source_template_snapshot
                        ),
                        clarification_context_text=clarification_context_text,
                    ),
                    context_bundle.attachment_contents,
                ),
                http_client=http_client,
            ),
            run_structured_prompt(
                pg_engine=pg_engine,
                graph_id=str(run.graph_id),
                user_id=user_id,
                model_id=optimizer_model,
                schema=IssueDetectorResponseSchema,
                system_prompt=issue_detector_system_prompt(),
                user_prompt=build_user_message_content(
                    build_issue_detector_user_prompt(
                        source_prompt=run.source_prompt,
                        target_snapshot=target_snapshot,
                        sibling_context_text=context_bundle.sibling_context_text,
                        clarification_context_text=clarification_context_text,
                    ),
                    context_bundle.attachment_contents,
                ),
                http_client=http_client,
            ),
        ),
    )
    audit, recommended_dimension_ids = normalize_audit(analyzer_result, issue_detector_result)
    selected_dimensions = sanitize_dimension_ids(run.selected_dimension_ids) or (
        recommended_dimension_ids or []
    )
    improved_prompt, explained_changes = await generate_prompt_improvement(
        pg_engine=pg_engine,
        graph_id=str(run.graph_id),
        user_id=user_id,
        model_id=optimizer_model,
        source_prompt=run.source_prompt,
        selected_dimensions=selected_dimensions,
        audit=audit,
        target_snapshot=target_snapshot,
        sibling_context_text=context_bundle.sibling_context_text,
        attachment_contents=context_bundle.attachment_contents,
        issue_detector=issue_detector_result,
        feedback=run.feedback,
        clarification_context_text=clarification_context_text,
        http_client=http_client,
    )
    await replace_prompt_improver_changes(
        pg_engine,
        run_id=str(run.id),
        changes=explained_changes,
    )
    updated_run = await update_prompt_improver_run(
        pg_engine,
        run_id=str(run.id),
        user_id=user_id,
        selected_dimension_ids=selected_dimensions,
        recommended_dimension_ids=recommended_dimension_ids,
        audit=audit.model_dump(mode="json"),
        improved_prompt=improved_prompt,
        status=PromptImproverRunStatusEnum.IMPROVED.value,
        active_phase=None,
        active_tool_call_id=None,
    )
    return await map_run_to_read(pg_engine, updated_run)


async def continue_prompt_improver_run(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run: PromptImproverRun,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
    redis_manager: RedisManager | None,
    http_client,
) -> PromptImproverRunRead:
    if run.active_phase == "draft":
        return await run_draft_phase(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            run=run,
            user_id=user_id,
            available_models=available_models,
            redis_manager=redis_manager,
            http_client=http_client,
        )
    if run.active_phase == "improve":
        return await run_improve_phase(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            run=run,
            user_id=user_id,
            available_models=available_models,
            redis_manager=redis_manager,
            http_client=http_client,
        )
    if run.active_phase == "feedback":
        return await run_feedback_phase(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            run=run,
            user_id=user_id,
            available_models=available_models,
            redis_manager=redis_manager,
            http_client=http_client,
        )
    raise ValueError("Prompt improver run does not have a resumable active phase")


async def answer_prompt_improver_question(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    run_id: str,
    user_id: str,
    tool_call_id: str,
    answer: Any,
    optimizer_model_id: str | None,
    available_models: list[dict[str, Any]] | None,
    redis_manager: RedisManager | None,
    http_client,
) -> PromptImproverRunRead:
    run = await get_prompt_improver_run_by_id(pg_engine, run_id=run_id, user_id=user_id)
    if run.status != PromptImproverRunStatusEnum.PENDING_USER_INPUT:
        raise ValueError("Prompt improver run is not waiting for user input")
    if not run.active_tool_call_id or run.active_tool_call_id != tool_call_id:
        raise ValueError("Prompt improver question is no longer active")

    tool_call = await get_tool_call_by_id(
        pg_engine,
        tool_call_id=tool_call_id,
        user_id=user_id,
    )
    if tool_call.status != ToolCallStatusEnum.PENDING_USER_INPUT:
        raise ValueError("Prompt improver question has already been answered")

    arguments = AskUserArguments.model_validate(tool_call.arguments)
    answer_payloads = normalize_ask_user_answers(arguments, answer)
    result_payload = build_ask_user_answer_result(
        arguments,
        answer_payloads,
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )
    await update_tool_call_by_id(
        pg_engine,
        tool_call_id=tool_call_id,
        user_id=user_id,
        status=ToolCallStatusEnum.SUCCESS,
        result=result_payload,
        model_context_payload=json.dumps(result_payload, separators=(",", ":")),
    )
    if redis_manager is not None:
        await redis_manager.delete_pending_tool_continuation(tool_call_id)

    updates: dict[str, Any] = {"active_tool_call_id": None}
    if optimizer_model_id is not None:
        target_snapshot = cast(dict[str, Any], run.target_snapshot)
        updates["target_snapshot"] = apply_optimizer_profile(
            target_snapshot,
            optimizer_model_id=optimizer_model_id,
            available_models=available_models,
        )

    resumed_run = await update_prompt_improver_run(
        pg_engine,
        run_id=str(run.id),
        user_id=user_id,
        **updates,
    )
    try:
        return await continue_prompt_improver_run(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            run=resumed_run,
            user_id=user_id,
            available_models=available_models,
            redis_manager=redis_manager,
            http_client=http_client,
        )
    except Exception:
        await update_prompt_improver_run(
            pg_engine,
            run_id=str(run.id),
            user_id=user_id,
            status=PromptImproverRunStatusEnum.FAILED.value,
            active_phase=None,
            active_tool_call_id=None,
        )
        raise
