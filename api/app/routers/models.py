from fastapi import APIRouter, Depends, Request
from services.auth import get_current_user_id
from services.openrouter import OpenRouterReq, ResponseModel, list_available_models

router = APIRouter()


@router.get("/models")
async def get_models(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> ResponseModel:
    """
    Retrieves the available models from the OpenRouter API.

    This endpoint fetches the list of models from the OpenRouter API and returns them.

    Returns:
        list[str]: A list of model names.
    """

    if request.app.state.available_models is not None:
        return ResponseModel.model_validate(request.app.state.available_models)

    openRouterReq = OpenRouterReq(
        api_key=request.app.state.master_open_router_api_key,
    )

    models = await list_available_models(openRouterReq)

    request.app.state.available_models = models

    return models


@router.post("/models/refresh")
async def refresh_models(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> ResponseModel:
    """
    Refreshes the list of available models from the OpenRouter API.

    This endpoint forces a refresh of the available models by fetching them again from the OpenRouter API.

    Returns:
        list[str]: A refreshed list of model names.
    """

    openRouterReq = OpenRouterReq(
        api_key=request.app.state.master_open_router_api_key,
    )

    models = await list_available_models(openRouterReq)

    request.app.state.available_models = models

    return models
