from database.pg.prompt_improver_ops import PromptImproverReviewPayload
from fastapi import APIRouter, Depends, HTTPException, Request
from models.prompt_improver import (
    PromptImproverDraftRequest,
    PromptImproverDraftResponse,
    PromptImproverFeedbackRequest,
    PromptImproverImproveRequest,
    PromptImproverNodeHistoryResponse,
    PromptImproverQuestionAnswerRequest,
    PromptImproverReviewRequest,
    PromptImproverRunRead,
    PromptImproverTaxonomyResponse,
)
from services.auth import get_current_user_id
from services.prompt_improver import (
    answer_prompt_improver_question,
    create_prompt_improver_draft,
    feedback_prompt_improver_run,
    get_prompt_improver_history,
    get_prompt_improver_taxonomy,
    improve_prompt_improver_run,
    review_prompt_improver_run,
)

router = APIRouter(prefix="/prompt-improver", tags=["prompt-improver"])


@router.get("/taxonomy", response_model=PromptImproverTaxonomyResponse)
async def get_taxonomy():
    return get_prompt_improver_taxonomy()


@router.post("/draft", response_model=PromptImproverDraftResponse)
async def create_draft(
    request: Request,
    payload: PromptImproverDraftRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        available_models = getattr(request.app.state.available_models, "data", None)
        return await create_prompt_improver_draft(
            pg_engine=request.app.state.pg_engine,
            neo4j_driver=request.app.state.neo4j_driver,
            graph_id=payload.graph_id,
            node_id=payload.node_id,
            target_id=payload.target_id,
            optimizer_model_id=payload.optimizer_model_id,
            user_id=user_id,
            available_models=available_models,
            http_client=request.app.state.http_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/improve", response_model=PromptImproverRunRead)
async def improve_run(
    run_id: str,
    request: Request,
    payload: PromptImproverImproveRequest,
    user_id: str = Depends(get_current_user_id),
):
    available_models = getattr(request.app.state.available_models, "data", None)
    return await improve_prompt_improver_run(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        run_id=run_id,
        user_id=user_id,
        selected_dimension_ids=payload.selected_dimension_ids,
        optimizer_model_id=payload.optimizer_model_id,
        available_models=available_models,
        http_client=request.app.state.http_client,
    )


@router.post("/runs/{run_id}/review", response_model=PromptImproverRunRead)
async def review_run(
    run_id: str,
    request: Request,
    payload: PromptImproverReviewRequest,
    user_id: str = Depends(get_current_user_id),
):
    review_changes: list[PromptImproverReviewPayload] = [
        {
            "change_id": str(change.change_id),
            "review_status": change.review_status,
        }
        for change in payload.changes
    ]
    return await review_prompt_improver_run(
        pg_engine=request.app.state.pg_engine,
        run_id=run_id,
        user_id=user_id,
        changes=review_changes,
        mark_applied=payload.mark_applied,
    )


@router.post("/runs/{run_id}/answer-question", response_model=PromptImproverRunRead)
async def answer_question(
    run_id: str,
    request: Request,
    payload: PromptImproverQuestionAnswerRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        available_models = getattr(request.app.state.available_models, "data", None)
        return await answer_prompt_improver_question(
            pg_engine=request.app.state.pg_engine,
            neo4j_driver=request.app.state.neo4j_driver,
            run_id=run_id,
            user_id=user_id,
            tool_call_id=payload.tool_call_id,
            answer=payload.answer,
            optimizer_model_id=payload.optimizer_model_id,
            available_models=available_models,
            http_client=request.app.state.http_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/feedback", response_model=PromptImproverRunRead)
async def feedback_run(
    run_id: str,
    request: Request,
    payload: PromptImproverFeedbackRequest,
    user_id: str = Depends(get_current_user_id),
):
    available_models = getattr(request.app.state.available_models, "data", None)
    return await feedback_prompt_improver_run(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        run_id=run_id,
        user_id=user_id,
        feedback=payload.feedback,
        selected_dimension_ids=payload.selected_dimension_ids,
        optimizer_model_id=payload.optimizer_model_id,
        available_models=available_models,
        http_client=request.app.state.http_client,
    )


@router.get("/node/{graph_id}/{node_id}", response_model=PromptImproverNodeHistoryResponse)
async def get_node_history(
    graph_id: str,
    node_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    available_models = getattr(request.app.state.available_models, "data", None)
    return await get_prompt_improver_history(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        user_id=user_id,
        available_models=available_models,
    )
