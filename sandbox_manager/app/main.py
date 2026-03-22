import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status

from app.config import SandboxSettings, get_settings
from app.executor import SandboxExecutor
from app.models import CodeExecutionRequest, CodeExecutionResponse

logger = logging.getLogger("uvicorn.error")


def create_app(
    settings: SandboxSettings | None = None,
    executor: Any | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_executor = executor

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.executor = resolved_executor or SandboxExecutor(resolved_settings)
        app.state.execution_semaphore = asyncio.Semaphore(
            resolved_settings.max_concurrent_sandboxes
        )
        app.state.executor.cleanup_stale_containers()
        yield

        close = getattr(app.state.executor, "close", None)
        if callable(close):
            close()

    app = FastAPI(title="Meridian Sandbox Manager", lifespan=lifespan)

    @app.get("/health")
    async def health(request: Request):
        health_state = request.app.state.executor.health_state()
        if not health_state.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=health_state.message
            )
        return {
            "status": "ok",
            "worker_image": request.app.state.settings.sandbox_worker_image,
            "runtime": getattr(request.app.state.executor, "runtime", None) or "default",
        }

    @app.post("/execute", response_model=CodeExecutionResponse)
    async def execute_code(
        request: Request, payload: CodeExecutionRequest
    ) -> CodeExecutionResponse:
        settings = request.app.state.settings

        if payload.language.lower() != "python":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Only python is supported"
            )

        code_size = len(payload.code.encode("utf-8"))
        if code_size > settings.sandbox_code_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Code payload exceeds {settings.sandbox_code_max_bytes} bytes",
            )

        semaphore = request.app.state.execution_semaphore
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.sandbox_queue_wait_seconds)
        except TimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Sandbox execution queue is full",
            ) from exc

        try:
            return await asyncio.to_thread(request.app.state.executor.execute_python, payload.code)
        except RuntimeError as exc:
            logger.exception("Sandbox execution failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
            ) from exc
        finally:
            semaphore.release()

    return app


app = create_app()
