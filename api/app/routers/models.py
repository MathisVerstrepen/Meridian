from fastapi import APIRouter, Request


from services.openrouter import OpenRouterReq, list_available_models, ResponseModel

router = APIRouter()


@router.get("/models")
async def get_models(request: Request) -> ResponseModel:
    """
    Retrieves the available models from the OpenRouter API.

    This endpoint fetches the list of models from the OpenRouter API and returns them.

    Returns:
        list[str]: A list of model names.
    """

    if request.app.state.available_models is not None:
        return request.app.state.available_models

    openRouterReq = OpenRouterReq(
        api_key=request.app.state.open_router_api_key,
    )

    models = await list_available_models(openRouterReq)

    request.app.state.available_models = models

    return models
