import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from const.prompts import (
    QUALITY_HELPER_PROMPT,
    TOOL_FETCH_PAGE_CONTENT_GUIDE,
    TOOL_WEB_SEARCH_GUIDE,
)
from database.pg.models import ToolCallStatusEnum
from models.message import ToolEnum
from services import openai_codex
from services.tools import registry
from services.tools import web as web_tools


@pytest.fixture
def req() -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(tools_link_extraction_max_length=1234),
        user_id="user-id",
        pg_engine=object(),
        http_client=object(),
    )


def _parameters(tool: dict) -> dict:
    return tool["function"]["parameters"]


def _tool_schema(tools: list[dict], name: str, schema_key: str = "parameters") -> dict:
    for tool in tools:
        payload = tool.get("function", tool)
        if payload.get("name") == name:
            return payload[schema_key]
    raise AssertionError(f"Tool {name!r} was not found")


def test_tool_schemas_require_only_bounded_array_inputs() -> None:
    search_parameters = _parameters(web_tools.WEB_SEARCH_TOOL)
    fetch_parameters = _parameters(web_tools.FETCH_PAGE_CONTENT_TOOL)

    assert web_tools.MAX_WEB_TOOL_BATCH_SIZE == 5
    assert search_parameters["required"] == ["queries"]
    assert "query" not in search_parameters["properties"]
    assert fetch_parameters["required"] == ["urls"]
    assert "url" not in fetch_parameters["properties"]

    for parameters, plural_name in (
        (search_parameters, "queries"),
        (fetch_parameters, "urls"),
    ):
        plural = parameters["properties"][plural_name]
        assert plural == {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {"type": "string", "minLength": 1},
            "description": plural["description"],
        }


@pytest.mark.parametrize(
    ("arguments", "expected_error"),
    [
        ({}, "'queries' must be an array containing 1 to 5 non-empty strings."),
        ({"query": "one"}, "Use 'queries' only; 'query' is not supported."),
        (
            {"query": "one", "queries": ["two"]},
            "Use 'queries' only; 'query' is not supported.",
        ),
        ({"queries": "one"}, "'queries' must be an array containing 1 to 5 non-empty strings."),
        ({"queries": []}, "'queries' must be an array containing 1 to 5 non-empty strings."),
        (
            {"queries": ["1", "2", "3", "4", "5", "6"]},
            "'queries' must be an array containing 1 to 5 non-empty strings.",
        ),
        (
            {"queries": ["valid", ""]},
            "'queries' must be an array containing 1 to 5 non-empty strings.",
        ),
        (
            {"queries": ["valid", 2]},
            "'queries' must be an array containing 1 to 5 non-empty strings.",
        ),
    ],
)
def test_web_search_rejects_invalid_forms_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    req: SimpleNamespace,
    arguments: dict,
    expected_error: str,
) -> None:
    calls = 0

    async def search_web(**kwargs):
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(web_tools, "search_web", search_web)

    assert asyncio.run(web_tools.web_search(arguments, req)) == {"error": expected_error}
    assert calls == 0


@pytest.mark.parametrize(
    ("arguments", "expected_error"),
    [
        ({}, "'urls' must be an array containing 1 to 5 non-empty strings."),
        ({"url": "https://one"}, "Use 'urls' only; 'url' is not supported."),
        (
            {"url": "https://one", "urls": ["https://two"]},
            "Use 'urls' only; 'url' is not supported.",
        ),
        ({"urls": "https://one"}, "'urls' must be an array containing 1 to 5 non-empty strings."),
        ({"urls": []}, "'urls' must be an array containing 1 to 5 non-empty strings."),
        (
            {"urls": ["1", "2", "3", "4", "5", "6"]},
            "'urls' must be an array containing 1 to 5 non-empty strings.",
        ),
        (
            {"urls": ["https://valid", ""]},
            "'urls' must be an array containing 1 to 5 non-empty strings.",
        ),
    ],
)
def test_fetch_page_rejects_invalid_forms_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    req: SimpleNamespace,
    arguments: dict,
    expected_error: str,
) -> None:
    calls = 0

    async def fetch_page(**kwargs):
        nonlocal calls
        calls += 1
        return {"markdown_content": "content"}

    monkeypatch.setattr(web_tools, "fetch_page", fetch_page)

    assert asyncio.run(web_tools.fetch_page_content(arguments, req)) == {"error": expected_error}
    assert calls == 0


def test_one_item_handlers_return_envelopes_with_defaults_and_service_arguments(
    monkeypatch: pytest.MonkeyPatch, req: SimpleNamespace
) -> None:
    search_result = [{"title": "Result", "url": "https://result", "content": "Snippet"}]
    page_markdown = "Page\n\n## Navigation links\n\n- [Next](<https://single/next>)"
    page_result = {"markdown_content": page_markdown}
    search_kwargs = {}
    fetch_kwargs = {}

    async def search_web(**kwargs):
        search_kwargs.update(kwargs)
        return search_result

    async def fetch_page(**kwargs):
        fetch_kwargs.update(kwargs)
        return page_result

    monkeypatch.setattr(web_tools, "search_web", search_web)
    monkeypatch.setattr(web_tools, "fetch_page", fetch_page)

    assert asyncio.run(web_tools.web_search({"queries": ["single"]}, req)) == {
        "searches": [{"query": "single", "results": search_result}]
    }
    assert search_kwargs == {
        "query": "single",
        "time_range": "",
        "language": "all",
        "config": req.config,
        "user_id": req.user_id,
        "pg_engine": req.pg_engine,
        "http_client": req.http_client,
    }
    assert asyncio.run(web_tools.fetch_page_content({"urls": ["https://single"]}, req)) == {
        "pages": [{"url": "https://single", "markdown_content": page_markdown}]
    }
    assert fetch_kwargs == {
        "url": "https://single",
        "max_length": 1234,
        "pg_engine": req.pg_engine,
        "user_id": req.user_id,
    }


def test_web_search_batch_is_serial_ordered_and_preserves_duplicates_and_options(
    monkeypatch: pytest.MonkeyPatch, req: SimpleNamespace
) -> None:
    active = 0
    max_active = 0
    calls = []

    async def search_web(**kwargs):
        nonlocal active, max_active
        calls.append(kwargs)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return [{"title": kwargs["query"], "url": "https://result", "content": "ok"}]

    monkeypatch.setattr(web_tools, "search_web", search_web)

    result = asyncio.run(
        web_tools.web_search(
            {
                "queries": ["first", "first", "last"],
                "time_range": "month",
                "language": "fr",
            },
            req,
        )
    )

    assert [call["query"] for call in calls] == ["first", "first", "last"]
    assert all(call["time_range"] == "month" and call["language"] == "fr" for call in calls)
    assert max_active == 1
    assert [search["query"] for search in result["searches"]] == ["first", "first", "last"]
    assert all("results" in search for search in result["searches"])
    assert "error" not in result


def test_fetch_batch_is_serial_ordered_and_applies_page_limit_per_duplicate(
    monkeypatch: pytest.MonkeyPatch, req: SimpleNamespace
) -> None:
    active = 0
    max_active = 0
    calls = []

    async def fetch_page(**kwargs):
        nonlocal active, max_active
        calls.append(kwargs)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return {"markdown_content": f"{kwargs['url']} call {len(calls)}"}

    monkeypatch.setattr(web_tools, "fetch_page", fetch_page)
    urls = ["https://one", "https://one", "https://two"]

    result = asyncio.run(web_tools.fetch_page_content({"urls": urls}, req))

    assert [call["url"] for call in calls] == urls
    assert all(call["max_length"] == 1234 for call in calls)
    assert max_active == 1
    assert result == {
        "pages": [
            {
                "url": url,
                "markdown_content": f"{url} call {index}",
            }
            for index, url in enumerate(urls, start=1)
        ],
    }


def test_web_search_batch_isolates_empty_controlled_and_unexpected_results(
    monkeypatch: pytest.MonkeyPatch, req: SimpleNamespace
) -> None:
    async def search_web(**kwargs):
        if kwargs["query"] == "controlled":
            return [{"error": "Safe service error."}]
        if kwargs["query"] == "raised":
            raise RuntimeError("secret exception")
        return []

    monkeypatch.setattr(web_tools, "search_web", search_web)

    result = asyncio.run(web_tools.web_search({"queries": ["empty", "controlled", "raised"]}, req))

    assert result == {
        "searches": [
            {"query": "empty", "results": []},
            {"query": "controlled", "error": "Safe service error."},
            {"query": "raised", "error": "Search operation failed."},
        ]
    }
    assert "secret exception" not in str(result)
    assert registry.resolve_tool_status(result) is ToolCallStatusEnum.SUCCESS


def test_all_failed_search_batch_retains_items_and_sets_root_error(
    monkeypatch: pytest.MonkeyPatch, req: SimpleNamespace
) -> None:
    async def search_web(**kwargs):
        if kwargs["query"] == "raised":
            raise RuntimeError("secret")
        return [{"error": "Safe service error."}]

    monkeypatch.setattr(web_tools, "search_web", search_web)

    result = asyncio.run(web_tools.web_search({"queries": ["controlled", "raised"]}, req))

    assert result == {
        "searches": [
            {"query": "controlled", "error": "Safe service error."},
            {"query": "raised", "error": "Search operation failed."},
        ],
        "error": "All search operations failed.",
    }
    assert registry.resolve_tool_status(result) is ToolCallStatusEnum.ERROR


def test_fetch_batch_isolates_controlled_and_unexpected_failures(
    monkeypatch: pytest.MonkeyPatch, req: SimpleNamespace
) -> None:
    async def fetch_page(**kwargs):
        if kwargs["url"].endswith("controlled"):
            return {"error": "Safe fetch error."}
        if kwargs["url"].endswith("raised"):
            raise RuntimeError("secret fetch exception")
        return {"markdown_content": "Page content"}

    monkeypatch.setattr(web_tools, "fetch_page", fetch_page)
    result = asyncio.run(
        web_tools.fetch_page_content(
            {"urls": ["https://ok", "https://controlled", "https://raised"]}, req
        )
    )

    assert result == {
        "pages": [
            {"url": "https://ok", "markdown_content": "Page content"},
            {"url": "https://controlled", "error": "Safe fetch error."},
            {"url": "https://raised", "error": "Page fetch operation failed."},
        ]
    }
    assert "secret fetch exception" not in str(result)
    assert registry.resolve_tool_status(result) is ToolCallStatusEnum.SUCCESS


def test_all_failed_fetch_batch_sets_root_error(monkeypatch, req: SimpleNamespace) -> None:
    async def fetch_page(**kwargs):
        return {"error": f"Cannot fetch {kwargs['url']}"}

    monkeypatch.setattr(web_tools, "fetch_page", fetch_page)
    result = asyncio.run(
        web_tools.fetch_page_content({"urls": ["https://one", "https://two"]}, req)
    )

    assert result["error"] == "All page fetch operations failed."
    assert [page["url"] for page in result["pages"]] == ["https://one", "https://two"]
    assert registry.resolve_tool_status(result) is ToolCallStatusEnum.ERROR


def test_batch_summary_renderers_keep_order_association_and_existing_tags() -> None:
    search_summary = registry._render_web_search_summary(
        "call-id",
        {"queries": ["one", "two"]},
        {
            "searches": [
                {
                    "query": "one",
                    "results": [{"title": "First", "url": "https://first", "content": "Snippet"}],
                },
                {"query": "two", "error": "Search failed."},
            ]
        },
        12,
    )
    fetch_summary = registry._render_fetch_page_summary(
        "call-id",
        {"urls": ["https://one", "https://two"]},
        {
            "pages": [
                {"url": "https://one", "markdown_content": "Page"},
                {"url": "https://two", "error": "Fetch failed."},
            ]
        },
        12,
    )

    assert search_summary.count("<search_query ") == 2
    assert search_summary.count("<search_res>") == 1
    assert search_summary.count("<search_error>") == 1
    assert search_summary.index('"one"') < search_summary.index("First")
    assert search_summary.index("First") < search_summary.index('"two"')
    assert search_summary.index('"two"') < search_summary.index("Search failed.")
    assert 'duration_ms="12"' in search_summary
    assert fetch_summary.count("<fetch_url ") == 2
    assert fetch_summary.count("<fetch_error>") == 1
    assert fetch_summary.index("https://one") < fetch_summary.index("https://two")
    assert fetch_summary.index("https://two") < fetch_summary.index("Fetch failed.")


def test_summary_renderers_ignore_deprecated_non_envelope_results() -> None:
    assert (
        registry._render_web_search_summary(
            "call-id",
            {"query": "legacy"},
            [{"title": "Title", "url": "https://url", "content": "Content"}],
        )
        == ""
    )
    assert (
        registry._render_fetch_page_summary(
            "call-id", {"url": "https://legacy"}, {"error": "Failed"}
        )
        == ""
    )


def test_tool_guidance_explains_bounded_ordered_partial_batches() -> None:
    assert "Always provide `queries` as an array of 1–5" in TOOL_WEB_SEARCH_GUIDE
    assert "one-item array for a single search" in TOOL_WEB_SEARCH_GUIDE
    assert "deprecated singular field" in TOOL_WEB_SEARCH_GUIDE
    assert "shared by every query" in TOOL_WEB_SEARCH_GUIDE
    assert "input order" in TOOL_WEB_SEARCH_GUIDE
    assert "retry only failed" in TOOL_WEB_SEARCH_GUIDE
    assert "unbounded crawl" in TOOL_WEB_SEARCH_GUIDE
    assert "Always provide `urls` as an array of 1–5" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "one-item array for a single page" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "deprecated singular field" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "input order" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "retry only failed" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "unbounded crawl" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "Do not guess URLs" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "prior successful `fetch_page_content` page" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "exact URLs" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "selectively follow relevant exact navigation URLs" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "fetch every navigation link" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "## Navigation links" in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "## Navigation links" in web_tools.FETCH_PAGE_CONTENT_TOOL["function"]["description"]
    assert "navigation_links" not in TOOL_FETCH_PAGE_CONTENT_GUIDE
    assert "navigation_links" not in web_tools.FETCH_PAGE_CONTENT_TOOL["function"]["description"]


def test_quality_helper_requires_claim_adjacent_web_source_citations() -> None:
    assert "`web_search`" in QUALITY_HELPER_PROMPT
    assert "`fetch_page_content`" in QUALITY_HELPER_PROMPT
    assert "every source you relied on" in QUALITY_HELPER_PROMPT
    assert "`[Source name](https://...)`" in QUALITY_HELPER_PROMPT
    assert "placed next to the claim it supports" in QUALITY_HELPER_PROMPT
    assert "MUST NOT omit citations" in QUALITY_HELPER_PROMPT
    assert "bare URLs or a detached, bare-URL-only source list" in QUALITY_HELPER_PROMPT


def test_plural_array_bounds_survive_representative_schema_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openrouter_tools = registry.get_openrouter_tools(
        [ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION]
    )
    codex_tools = openai_codex._build_dynamic_tools([ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION])
    existing_opencode_module = sys.modules.get("services.opencode_go")
    if existing_opencode_module is not None:
        anthropic_tools = existing_opencode_module._build_anthropic_tools(openrouter_tools)
    else:
        openrouter_stub = ModuleType("services.openrouter")
        openrouter_stub._parse_openrouter_error = lambda *args, **kwargs: None
        openrouter_stub._process_tool_calls_and_continue = lambda *args, **kwargs: None
        openrouter_stub._merge_tool_call_chunks = lambda *args, **kwargs: None
        with monkeypatch.context() as import_context:
            import_context.setitem(sys.modules, "services.openrouter", openrouter_stub)
            opencode_go = importlib.import_module("services.opencode_go")
            anthropic_tools = opencode_go._build_anthropic_tools(openrouter_tools)
            sys.modules.pop("services.opencode_go", None)

    adapter_schemas = (
        (
            _tool_schema(openrouter_tools, "web_search"),
            _tool_schema(openrouter_tools, "fetch_page_content"),
        ),
        (
            _tool_schema(codex_tools, "web_search", "inputSchema"),
            _tool_schema(codex_tools, "fetch_page_content", "inputSchema"),
        ),
        (
            _tool_schema(anthropic_tools, "web_search", "input_schema"),
            _tool_schema(anthropic_tools, "fetch_page_content", "input_schema"),
        ),
    )
    for search_schema, fetch_schema in adapter_schemas:
        assert search_schema["required"] == ["queries"]
        assert "query" not in search_schema["properties"]
        assert search_schema["properties"]["queries"]["minItems"] == 1
        assert search_schema["properties"]["queries"]["maxItems"] == 5
        assert fetch_schema["required"] == ["urls"]
        assert "url" not in fetch_schema["properties"]
        assert fetch_schema["properties"]["urls"]["minItems"] == 1
        assert fetch_schema["properties"]["urls"]["maxItems"] == 5
