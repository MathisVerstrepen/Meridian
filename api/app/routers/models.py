from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

from services.openrouter import OpenRouterReq, list_available_models

router = APIRouter()


class Architecture(BaseModel):
    input_modalities: list[str]
    instruct_type: Optional[str] = None
    modality: str
    output_modalities: list[str]
    tokenizer: str

class Pricing(BaseModel):
    completion: str
    image: Optional[str] = None
    internal_reasoning: Optional[str] = None
    prompt: str
    request: Optional[str] = None
    web_search: Optional[str] = None

class TopProvider(BaseModel):
    context_length: Optional[int] = -1
    is_moderated: bool
    max_completion_tokens: Optional[int] = None

class ModelInfo(BaseModel):
    architecture: Architecture
    context_length: Optional[int] = -1
    created: int
    description: str
    id: str
    name: str
    per_request_limits: Optional[str] = None
    pricing: Pricing
    supported_parameters: list[str]
    top_provider: TopProvider

class ResponseModel(BaseModel):
    data: list[ModelInfo]


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
