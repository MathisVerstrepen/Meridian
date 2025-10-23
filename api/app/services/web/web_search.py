import logging
import os
import httpx
from typing import TYPE_CHECKING, Any, Dict, List
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from fastapi import HTTPException

from database.pg.models import QueryTypeEnum
from services.web.web_extract import url_to_markdown
from database.pg.user_ops.usage_crud import check_and_increment_query_usage

if TYPE_CHECKING:
    from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate

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
                "time_range": {
                    "type": "string",
                    "enum": ["day", "month", "year"],
                    "description": "Time range for the search.",
                },
                "language": {
                    "type": "string",
                    "description": "The language code for the search results (e.g., 'en' for English).",
                    "enum": ["all", "en", "fr", "de", "es", "it"],
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


def _filter_and_rank_results(
    results: List[Dict[str, Any]], ignored_sites: List[str], preferred_sites: List[str]
) -> List[Dict[str, Any]]:
    """
    Filters search results by removing ignored sites and prioritizing preferred sites.
    """
    if not ignored_sites and not preferred_sites:
        return results

    def get_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.replace("www.", "")
        except (ValueError, AttributeError):
            return ""

    # Filter out ignored sites
    filtered_results = [
        res for res in results if get_domain(res.get("url", "")) not in ignored_sites
    ]

    # Separate preferred results from the rest
    preferred_results = []
    other_results = []
    for res in filtered_results:
        if get_domain(res.get("url", "")) in preferred_sites:
            preferred_results.append(res)
        else:
            other_results.append(res)

    # Return the combined list with preferred sites at the top
    return preferred_results + other_results


async def search_searxng(
    query: str,
    time_range: str,
    language: str,
    num_results: int,
    ignored_sites: List[str],
    preferred_sites: List[str],
) -> List[Dict[str, Any]]:
    """
    Perform a web search using the local SearxNG instance.
    """
    searxng_url = f"{os.getenv('SEARXNG_URL', 'localhost:8888')}/search"
    if not searxng_url.startswith("http"):
        searxng_url = "http://" + searxng_url

    params = {
        "q": query,
        "format": "json",
        "pageno": "1",
        "categories": "general",
        "engines": "google,wikidata,wikipedia,brave,yahoo,mullvadleta,mullvadleta brave,startpage",
    }

    if time_range in {"day", "month", "year"}:
        params["time_range"] = time_range

    if language != "all" and language in {"en", "fr", "de", "es", "it"}:
        params["language"] = language

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(searxng_url, params=params, timeout=20.0)
            response.raise_for_status()

            data = response.json()

            if data.get("unresponsive_engines", []):
                logger.warning(f"Unresponsive search engines: {data['unresponsive_engines']}")

            results = data.get("results", [])

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                    }
                )

            # Apply filtering and ranking
            final_results = _filter_and_rank_results(
                formatted_results, ignored_sites, preferred_sites
            )

            return final_results[:num_results]

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return [{"error": f"Search failed: {str(e)}"}]


async def search_google_custom(
    query: str,
    api_key: str,
    num_results: int,
    ignored_sites: List[str],
    preferred_sites: List[str],
) -> List[Dict[str, Any]]:
    google_cse_id = os.getenv("GOOGLE_CSE_ID")
    if not google_cse_id:
        logger.error("GOOGLE_CSE_ID environment variable not set. Cannot use Google Custom Search.")
        return [{"error": "Google Custom Search is not configured on the server."}]

    search_url = "https://www.googleapis.com/customsearch/v1"

    params = {
        "key": api_key,
        "cx": google_cse_id,
        "q": query,
        "num": 10,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            results = data.get("items", [])
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "content": result.get("snippet", ""),
                    }
                )

            # Apply filtering and ranking
            final_results = _filter_and_rank_results(
                formatted_results, ignored_sites, preferred_sites
            )

            return final_results[:num_results]
    except httpx.HTTPStatusError as e:
        error_details = (
            e.response.json().get("error", {}).get("message", "Unknown Google API error")
        )
        logger.error(f"Google Custom Search API error: {error_details}")
        return [{"error": f"Google Search failed: {error_details}"}]
    except Exception as e:
        logger.error(f"Google Custom Search failed: {e}")
        return [{"error": f"Google Search failed: {str(e)}"}]


async def search_web(
    query: str,
    time_range: str,
    language: str,
    config: "GraphConfigUpdate",
    user_id: str,
    pg_engine: SQLAlchemyAsyncEngine,
) -> List[Dict[str, Any]]:
    use_google_api = (
        config.tools_web_search_force_custom_api_key and config.tools_web_search_custom_api_key
    )

    if use_google_api:
        return await search_google_custom(
            query=query,
            api_key=config.tools_web_search_custom_api_key,
            num_results=config.tools_web_search_num_results,
            ignored_sites=config.tools_web_search_ignored_sites,
            preferred_sites=config.tools_web_search_preferred_sites,
        )
    else:
        try:
            await check_and_increment_query_usage(pg_engine, user_id, QueryTypeEnum.WEB_SEARCH)
        except HTTPException as e:
            return [{"error": f"Usage Error: {e.detail}"}]

        return await search_searxng(
            query=query,
            time_range=time_range,
            language=language,
            num_results=config.tools_web_search_num_results,
            ignored_sites=config.tools_web_search_ignored_sites,
            preferred_sites=config.tools_web_search_preferred_sites,
        )


async def fetch_page(
    url: str, max_length: int, pg_engine: SQLAlchemyAsyncEngine, user_id: str
) -> Dict[str, Any]:
    """
    Fetches the content of a URL and returns it as Markdown.
    """
    try:
        try:
            await check_and_increment_query_usage(pg_engine, user_id, QueryTypeEnum.LINK_EXTRACTION)
        except HTTPException as e:
            return [{"error": f"Usage Error: {e.detail}"}]

        markdown_content = await url_to_markdown(url)
        if markdown_content:
            # Limit content length to avoid overly large payloads
            if len(markdown_content) > max_length:
                markdown_content = markdown_content[:max_length] + "\n... (content truncated)"
            return {"markdown_content": markdown_content}
        else:
            return {
                "error": "Failed to fetch or process content from the URL. The page might be empty or inaccessible."
            }
    except Exception as e:
        logger.error(f"Fetching page content for {url} failed: {e}")
        return {"error": f"Failed to fetch page content: {str(e)}"}


TOOL_MAPPING = {
    "web_search": lambda args, req: search_web(
        query=args["query"],
        time_range=args.get("time_range", ""),
        language=args.get("language", "all"),
        config=req.config,
        user_id=req.user_id,
        pg_engine=req.pg_engine,
    ),
    "fetch_page_content": lambda args, req: fetch_page(
        url=args["url"],
        max_length=req.config.tools_link_extraction_max_length,
        pg_engine=req.pg_engine,
        user_id=req.user_id,
    ),
}
