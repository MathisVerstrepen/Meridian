import logging
import httpx
from typing import Dict, Any, List

logger = logging.getLogger("uvicorn.error")

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Searches the web using a local SearXNG instance to get up-to-date information, "
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


async def search_web(query: str) -> List[Dict[str, Any]]:
    """
    Perform a web search using the local SearxNG instance.

    Args:
        query (str): The search query

    Returns:
        List[Dict[str, Any]]: List of search results
    """
    searxng_url = "http://localhost:8888/search"

    params = {"q": query, "format": "json", "pageno": "1", "category_general": "1"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(searxng_url, params=params, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])[:5]

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

            for result in formatted_results:
                print(f"Title: {result['title']}")
                print(f"URL: {result['url']}")
                print(f"Content: {result['content']}")
                print(f"Length of content: {len(result['content'])} characters")
                print("-" * 40)

            return formatted_results

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return [{"error": f"Search failed: {str(e)}"}]


TOOL_MAPPING = {"web_search": lambda args: search_web(args["query"])}
