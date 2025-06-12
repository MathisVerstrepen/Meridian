import json
import httpx
from pydantic import BaseModel
from typing import Optional
from rich import print as pprint

from services.graph_service import Message
from models.chatDTO import Reasoning

from database.pg.crud import (
    GraphConfigUpdate,
)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class OpenRouterReq:
    headers = {
        "Content-Type": "application/json",
    }

    def __init__(self, api_key: str, api_url: str = None):
        self.headers["Authorization"] = f"Bearer {api_key}"
        self.api_url = api_url


class OpenRouterReqChat(OpenRouterReq):
    def __init__(
        self,
        api_key: str,
        model: str,
        messages: list[Message],
        config: GraphConfigUpdate,
        reasoning: Reasoning,
    ):
        super().__init__(api_key, OPENROUTER_CHAT_URL)
        self.model = model
        self.messages = [mess.model_dump(exclude_none=True) for mess in messages]
        self.reasoning = reasoning
        self.config = config

        self.reasoning.effort = self.config.reasoning_effort

    def get_payload(self):
        # https://openrouter.ai/docs/api-reference/chat-completion
        return {
            "model": self.model,
            "messages": self.messages,
            "stream": True,
            "reasoning": self.reasoning.model_dump(),
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
            "repetition_penalty": self.config.repetition_penalty,
            "usage": {
                "include": True,
            },
        }


async def stream_openrouter_response(req: OpenRouterReq):
    """
    Streams responses from the OpenRouter API asynchronously.

    This function sends a request to the OpenRouter API and yields content
    chunks as they are received in the streaming response. It handles errors
    gracefully and provides appropriate error messages.

    Args:
        req (OpenRouterReq): An object containing the API request details including
                            URL, headers, and payload for the OpenRouter API.

    Yields:
        str: Content chunks from the AI model response or error messages.
            Success case: Text fragments from the model's response.
            Error case: Error messages prefixed with "Error:".

    Notes:
        - Uses httpx for asynchronous HTTP communication
        - Handles JSON parsing of streaming data
        - Processes OpenRouter's SSE (Server-Sent Events) format
        - Logs errors and unexpected responses to the console
    """

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST", req.api_url, headers=req.headers, json=req.get_payload()
            ) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    print(
                        f"OpenRouter API Error {response.status_code}: {error_content.decode()}"
                    )
                    yield f"Error: Failed to get response from AI Provider (Status: {response.status_code}). Check backend logs."
                    return

                reasoning_started = False
                usageData = {}
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[len("data: ") :].strip()
                        if data_str == "[DONE]":
                            if reasoning_started:
                                yield "[THINK]\n"
                                reasoning_started = False
                            break
                        try:
                            chunk = json.loads(data_str)
                            usageData = chunk.get("usage", {})
                            delta = chunk["choices"][0]["delta"]
                            if "reasoning" in delta and delta["reasoning"]:
                                if not reasoning_started:
                                    yield "[THINK]\n"
                                    reasoning_started = True
                                yield delta["reasoning"]
                                continue
                            elif "content" in delta and delta["content"]:
                                if reasoning_started:
                                    yield "[!THINK]\n\n"
                                    reasoning_started = False
                                yield delta["content"]
                        except json.JSONDecodeError:
                            print(f"Warning: Could not decode JSON chunk: {data_str}")
                            continue
                        except (AttributeError, KeyError):
                            print(f"Warning: Unexpected structure in chunk: {data_str}")
                            continue
                    elif line.strip():
                        print(f"Received non-data line: {line}")

                if usageData:
                    yield f"[USAGE]{json.dumps(usageData, indent=2)}"

    except httpx.RequestError as e:
        print(f"HTTPX Request Error connecting to OpenRouter: {e}")
        yield f"Error: Could not connect to AI service. {e}"
    except Exception as e:
        print(f"An unexpected error occurred during streaming: {e}")
        yield f"Error: An unexpected error occurred. {e}"


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
    icon: Optional[str] = None
    per_request_limits: Optional[str] = None
    pricing: Pricing
    supported_parameters: list[str]
    top_provider: TopProvider


class ResponseModel(BaseModel):
    data: list[ModelInfo]


BRAND_ICONS = [
    "deepseek",
    "x-ai",
    "cohere",
    "mistralai",
    "meta-llama",
    "google",
    "anthropic",
    "openai",
    "microsoft",
    "qwen",
    "perplexity",
    "nvidia",
]


async def list_available_models(req: OpenRouterReq) -> ResponseModel:
    """
    Lists available models from the OpenRouter API.

    This function sends a request to the OpenRouter API to retrieve a list of
    available models. It handles errors gracefully and provides appropriate
    error messages.

    Args:
        req (OpenRouterReq): An object containing the API request details including
                            URL and headers for the OpenRouter API.

    Returns:
        ResponseModel: A Pydantic model containing the list of available models.

    Notes:
        - Uses httpx for asynchronous HTTP communication
        - Handles JSON parsing of the response
        - Logs errors and unexpected responses to the console
    """

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(OPENROUTER_MODELS_URL, headers=req.headers)
            if response.status_code != 200:
                return f"Error: Failed to get models from AI Provider (Status: {response.status_code}). Check backend logs."

            try:
                models = response.json()
                models = ResponseModel(**models)

                for model in models.data:
                    brand = model.id.split("/")[0]
                    if brand in BRAND_ICONS:
                        model.icon = brand

                return models
            except json.JSONDecodeError:
                print("Warning: Could not decode JSON response.")
                return "Error: Could not decode JSON response."

    except httpx.RequestError as e:
        print(f"HTTPX Request Error connecting to OpenRouter: {e}")
        return f"Error: Could not connect to AI service. {e}"
    except Exception as e:
        print(f"An unexpected error occurred during model listing: {e}")
        return f"Error: An unexpected error occurred. {e}"
