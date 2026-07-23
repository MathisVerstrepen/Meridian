import re

import httpx
from bs4 import BeautifulSoup, Tag

ALIBABA_TOKEN_PLAN_OFFICIAL_OVERVIEW_URL = (
    "https://help.aliyun.com/en/model-studio/token-plan-personal-overview"
)
MAX_OFFICIAL_CATALOG_BYTES = 2 * 1024 * 1024
MAX_OFFICIAL_CATALOG_ROWS = 5_000
MAX_OFFICIAL_MODEL_ID_LENGTH = 255 - len("alibaba-token-plan/")

_ASCII_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")


class AlibabaTokenPlanOfficialCatalogError(RuntimeError):
    """A sanitized official-catalog discovery failure."""


def _normalize_cell_text(cell: Tag) -> str:
    return _WHITESPACE_RE.sub(" ", cell.get_text(" ", strip=True)).strip().casefold()


def _own_rows(table: Tag) -> list[Tag]:
    return [
        row
        for row in table.find_all("tr")
        if isinstance(row, Tag) and row.find_parent("table") is table
    ]


def _direct_cells(row: Tag) -> list[Tag]:
    return [cell for cell in row.find_all(["th", "td"], recursive=False) if isinstance(cell, Tag)]


def parse_alibaba_token_plan_official_video_model_ids(html_body: bytes) -> list[str]:
    if len(html_body) > MAX_OFFICIAL_CATALOG_BYTES:
        raise AlibabaTokenPlanOfficialCatalogError(
            "Alibaba official catalog response exceeded the size limit."
        )
    try:
        decoded_html = html_body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AlibabaTokenPlanOfficialCatalogError(
            "Alibaba official catalog returned invalid UTF-8."
        ) from exc

    soup = BeautifulSoup(decoded_html, "html.parser")
    qualifying_tables: list[tuple[list[Tag], int]] = []
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        rows = _own_rows(table)
        for index, row in enumerate(rows):
            cells = _direct_cells(row)
            if len(cells) >= 2 and [
                _normalize_cell_text(cells[-2]),
                _normalize_cell_text(cells[-1]),
            ] == ["model id", "capability"]:
                qualifying_tables.append((rows, index))
                break

    if not qualifying_tables:
        raise AlibabaTokenPlanOfficialCatalogError(
            "Alibaba official catalog did not contain the supported model table."
        )

    candidate_count = 0
    model_ids: list[str] = []
    seen: set[str] = set()
    for rows, header_index in qualifying_tables:
        for row in rows[header_index + 1 :]:
            cells = _direct_cells(row)
            if len(cells) < 2:
                continue
            model_id = cells[-2].get_text(" ", strip=True).strip()
            capability = _normalize_cell_text(cells[-1])
            if not model_id and not capability:
                continue
            candidate_count += 1
            if candidate_count > MAX_OFFICIAL_CATALOG_ROWS:
                raise AlibabaTokenPlanOfficialCatalogError(
                    "Alibaba official catalog returned too many entries."
                )
            if capability != "video generation":
                continue
            if (
                not model_id
                or len(model_id) > MAX_OFFICIAL_MODEL_ID_LENGTH
                or _ASCII_CONTROL_RE.search(model_id)
                or any(character.isspace() for character in model_id)
                or model_id in seen
            ):
                continue
            seen.add(model_id)
            model_ids.append(model_id)
    return model_ids


async def fetch_alibaba_token_plan_official_video_model_ids(
    http_client: httpx.AsyncClient,
) -> list[str]:
    timeout = httpx.Timeout(20.0, connect=10.0, read=20.0)
    request = httpx.Request(
        "GET",
        ALIBABA_TOKEN_PLAN_OFFICIAL_OVERVIEW_URL,
        headers={"Accept": "text/html, application/xhtml+xml"},
        extensions={"timeout": timeout.as_dict()},
    )
    response: httpx.Response | None = None
    try:
        response = await http_client.send(
            request,
            auth=None,
            follow_redirects=False,
            stream=True,
        )
        if response.status_code != 200:
            raise AlibabaTokenPlanOfficialCatalogError(
                "Alibaba official catalog request returned an unexpected status."
            )
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise AlibabaTokenPlanOfficialCatalogError(
                "Alibaba official catalog returned an unsupported media type."
            )
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise AlibabaTokenPlanOfficialCatalogError(
                    "Alibaba official catalog returned an invalid response size."
                ) from exc
            if declared_length < 0 or declared_length > MAX_OFFICIAL_CATALOG_BYTES:
                raise AlibabaTokenPlanOfficialCatalogError(
                    "Alibaba official catalog response exceeded the size limit."
                )
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_OFFICIAL_CATALOG_BYTES:
                raise AlibabaTokenPlanOfficialCatalogError(
                    "Alibaba official catalog response exceeded the size limit."
                )
    except AlibabaTokenPlanOfficialCatalogError:
        raise
    except (httpx.HTTPError, TimeoutError) as exc:
        raise AlibabaTokenPlanOfficialCatalogError(
            "Alibaba official catalog request failed."
        ) from exc
    finally:
        if response is not None:
            await response.aclose()
    return parse_alibaba_token_plan_official_video_model_ids(bytes(body))
