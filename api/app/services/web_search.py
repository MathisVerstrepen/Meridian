import logging
import os
import httpx
from typing import Dict, Any, List

from services.web_extract import url_to_markdown

logger = logging.getLogger("uvicorn.error")

NUM_WEB_RESULTS = 5

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Searches the web to get up-to-date information, "
            "context, or answer questions about recent events."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "categories": {
                    "type": "string",
                    "description": "Comma-separated list of search categories (e.g., 'general', 'news').",
                },
                "time_range": {
                    "type": "string",
                    "enum": ["day", "month", "year"],
                    "description": "Time range for the search.",
                },
            },
            "required": ["query"],
        },
    },
}

FETCH_PAGE_CONTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_page_content",
        "description": "Get the main content of a given URL. Use this to get more information from a specific webpage found via web_search.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL of the webpage to fetch.",
                }
            },
            "required": ["url"],
        },
    },
}


async def search_web(query: str) -> List[Dict[str, Any]]:
    """
    Perform a web search using the local SearxNG instance.

    Args:
        query (str): The search query

    Returns:
        List[Dict[str, Any]]: List of search results
    """
    searxng_url = f"{os.getenv('SEARXNG_URL', 'localhost:8888')}/search"
    if not searxng_url.startswith("http"):
        searxng_url = "http://" + searxng_url

    params = {"q": query, "format": "json", "pageno": "1", "category_general": "1"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(searxng_url, params=params, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])[:NUM_WEB_RESULTS]

            # Format results for the LLM
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                    }
                )

            return formatted_results

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return [{"error": f"Search failed: {str(e)}"}]


async def fetch_page(url: str) -> Dict[str, Any]:
    """
    Fetches the content of a URL and returns it as Markdown.

    Args:
        url (str): The URL to fetch.

    Returns:
        Dict[str, Any]: A dictionary containing the markdown content or an error.
    """
    try:
        markdown_content = await url_to_markdown(url)
        if markdown_content:
            # Limit content length to avoid overly large payloads
            MAX_CONTENT_LENGTH = 100000
            if len(markdown_content) > MAX_CONTENT_LENGTH:
                markdown_content = (
                    markdown_content[:MAX_CONTENT_LENGTH] + "\n... (content truncated)"
                )
            return {"markdown_content": markdown_content}
        else:
            return {
                "error": "Failed to fetch or process content from the URL. The page might be empty or inaccessible."
            }
    except Exception as e:
        logger.error(f"Fetching page content for {url} failed: {e}")
        return {"error": f"Failed to fetch page content: {str(e)}"}


TOOL_MAPPING = {
    "web_search": lambda args: search_web(args["query"]),
    "fetch_page_content": lambda args: fetch_page(args["url"]),
}
