from typing import TypeGuard

from services.web.web_search import fetch_page, search_web

MAX_WEB_TOOL_BATCH_SIZE = 5

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
                "queries": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_WEB_TOOL_BATCH_SIZE,
                    "items": {"type": "string", "minLength": 1},
                    "description": (
                        "An ordered list of 1 to 5 search queries. "
                        "Use a one-item list for a single search."
                    ),
                },
                "time_range": {
                    "type": "string",
                    "enum": ["day", "month", "year"],
                    "description": "Time range for the search.",
                },
                "language": {
                    "type": "string",
                    "description": """The language code for the search results
                    (e.g., 'en' for English).""",
                    "enum": ["all", "en", "fr", "de", "es", "it"],
                },
            },
            "required": ["queries"],
        },
    },
}

FETCH_PAGE_CONTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_page_content",
        "description": """Get the main Markdown content of a given URL.
        Successful Markdown may include a `## Navigation links` section with exact follow-up
        targets from the fetched page.""",
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_WEB_TOOL_BATCH_SIZE,
                    "items": {"type": "string", "minLength": 1},
                    "description": (
                        "An ordered list of 1 to 5 webpage URLs. "
                        "Use a one-item list for a single page."
                    ),
                },
            },
            "required": ["urls"],
        },
    },
}


async def web_search(arguments: dict, req):
    if "query" in arguments:
        return {"error": "Use 'queries' only; 'query' is not supported."}

    queries = arguments.get("queries")
    if not _is_valid_batch(queries):
        return {"error": "'queries' must be an array containing 1 to 5 non-empty strings."}

    searches = []
    failed_count = 0
    for query in queries:
        try:
            results = await search_web(
                query=query,
                time_range=arguments.get("time_range", ""),
                language=arguments.get("language", "all"),
                config=req.config,
                user_id=req.user_id,
                pg_engine=req.pg_engine,
                http_client=req.http_client,
            )
            if results and isinstance(results[0], dict) and results[0].get("error"):
                searches.append({"query": query, "error": results[0]["error"]})
                failed_count += 1
            else:
                searches.append({"query": query, "results": results})
        except Exception:
            searches.append({"query": query, "error": "Search operation failed."})
            failed_count += 1

    response: dict[str, object] = {"searches": searches}
    if failed_count == len(queries):
        response["error"] = "All search operations failed."
    return response


async def fetch_page_content(arguments: dict, req):
    if "url" in arguments:
        return {"error": "Use 'urls' only; 'url' is not supported."}

    urls = arguments.get("urls")
    if not _is_valid_batch(urls):
        return {"error": "'urls' must be an array containing 1 to 5 non-empty strings."}

    pages = []
    failed_count = 0
    for url in urls:
        try:
            page = await fetch_page(
                url=url,
                max_length=req.config.tools_link_extraction_max_length,
                pg_engine=req.pg_engine,
                user_id=req.user_id,
            )
            if isinstance(page, dict) and page.get("error"):
                pages.append({"url": url, "error": page["error"]})
                failed_count += 1
            else:
                pages.append({"url": url, "markdown_content": page["markdown_content"]})
        except Exception:
            pages.append({"url": url, "error": "Page fetch operation failed."})
            failed_count += 1

    response: dict[str, object] = {"pages": pages}
    if failed_count == len(urls):
        response["error"] = "All page fetch operations failed."
    return response


def _is_valid_batch(items: object) -> TypeGuard[list[str]]:
    return (
        isinstance(items, list)
        and 1 <= len(items) <= MAX_WEB_TOOL_BATCH_SIZE
        and all(isinstance(item, str) and len(item) > 0 for item in items)
    )
