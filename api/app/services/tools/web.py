from services.web.web_search import fetch_page, search_web

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
                    "description": """The language code for the search results
                    (e.g., 'en' for English).""",
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
        "description": """Get the main content of a given URL.
        Use this to get more information from a specific webpage found via web_search.""",
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


async def web_search(arguments: dict, req):
    return await search_web(
        query=arguments["query"],
        time_range=arguments.get("time_range", ""),
        language=arguments.get("language", "all"),
        config=req.config,
        user_id=req.user_id,
        pg_engine=req.pg_engine,
        http_client=req.http_client,
    )


async def fetch_page_content(arguments: dict, req):
    return await fetch_page(
        url=arguments["url"],
        max_length=req.config.tools_link_extraction_max_length,
        pg_engine=req.pg_engine,
        user_id=req.user_id,
    )
