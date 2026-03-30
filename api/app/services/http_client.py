from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def use_http_client(
    http_client: httpx.AsyncClient | None,
) -> AsyncIterator[httpx.AsyncClient]:
    if http_client is not None:
        yield http_client
        return

    async with httpx.AsyncClient() as fallback_client:
        yield fallback_client
