from fastapi import APIRouter, Depends, Request
from models.inference import ResponseModel
from services.auth import get_current_user_id
from services.inference import get_available_models_for_user
from services.openrouter import OpenRouterReq, list_available_models

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

    cached_models = getattr(request.app.state, "available_models", None)
    if cached_models is None:
        open_router_req = OpenRouterReq(
            api_key=request.app.state.master_open_router_api_key,
            http_client=request.app.state.http_client,
        )
        request.app.state.available_models = await list_available_models(open_router_req)

    return await get_available_models_for_user(request.app, user_id)
