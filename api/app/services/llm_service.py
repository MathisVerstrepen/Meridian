import os
import json
import httpx

from services.graph_service import Message


class OpenRouterReq:
    headers = {
        "Content-Type": "application/json",
    }

    def __init__(self, api_key: str, model: str, messages: list[Message]):
        self.headers["Authorization"] = f"Bearer {api_key}"
        self.api_url = os.getenv(
            "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
        )
        self.model = model
        self.messages = [mess.model_dump() for mess in messages]

    def get_payload(self):
        return {
            "model": self.model,
            "messages": self.messages,
            "stream": True,
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

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[len("data: ") :].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            content = (
                                chunk_data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content")
                            )
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            print(f"Warning: Could not decode JSON chunk: {data_str}")
                            continue
                        except IndexError:
                            print(f"Warning: Unexpected chunk structure: {chunk_data}")
                            continue
                    elif line.strip():
                        print(f"Received non-data line: {line}")

    except httpx.RequestError as e:
        print(f"HTTPX Request Error connecting to OpenRouter: {e}")
        yield f"Error: Could not connect to AI service. {e}"
    except Exception as e:
        print(f"An unexpected error occurred during streaming: {e}")
        yield f"Error: An unexpected error occurred. {e}"
