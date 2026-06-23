import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
import sentry_sdk
from const.settings import DEFAULT_SETTINGS
from database.neo4j.core import create_neo4j_indexes, get_neo4j_async_driver
from database.pg.core import get_pg_async_engine
from database.pg.graph_ops.graph_crud import delete_old_temporary_graphs
from database.pg.models import create_initial_users
from database.pg.settings_ops.settings_crud import update_settings
from database.redis.redis_ops import RedisManager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import (
    chat,
    files,
    github,
    gitlab,
    google_drive,
    graph,
    images,
    inference_providers,
    models,
    prompt_improver,
    prompt_templates,
    repository,
    users,
)
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from services.auth import parse_userpass
from services.connection_manager import manager as connection_manager
from services.external_file_cache import cleanup_expired_external_file_cache
from services.files import create_user_root_folder
from services.image_playground.jobs import recover_stale_image_generation_jobs
from services.openrouter import OpenRouterReq, list_available_models
from services.providers.models_dev import fetch_models_dev_catalog
from services.rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from utils.helpers import load_environment_variables

logging.getLogger("urllib3").setLevel(logging.ERROR)
logger = logging.getLogger("uvicorn.error")
MODELS_DEV_REFRESH_INTERVAL_SECONDS = 60 * 60 * 6
EXTERNAL_FILE_CACHE_CLEANUP_INTERVAL_SECONDS = 60 * 60

if not os.path.exists("data/user_files"):
    os.makedirs("data/user_files")


def rate_limit_exception_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


async def cron_delete_temp_graphs(app: FastAPI):
    while True:
        try:
            logger.info("Cron job: Running job to delete old temporary graphs.")
            await delete_old_temporary_graphs(app.state.pg_engine, app.state.neo4j_driver)
        except Exception as e:
            logger.error(f"Cron job: Error deleting old temporary graphs: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        await asyncio.sleep(3600)  # Refresh every hour


async def refresh_openrouter_models(app: FastAPI):
    openRouterReq = OpenRouterReq(
        api_key=app.state.master_open_router_api_key,
        http_client=app.state.http_client,
    )
    models = await list_available_models(openRouterReq)
    app.state.available_models = models


async def cron_refresh_openrouter_models(app: FastAPI):
    while True:
        try:
            logger.info("Cron job: Refreshing OpenRouter models.")
            await refresh_openrouter_models(app)
        except Exception as e:
            logger.error(f"Cron job: Error refreshing OpenRouter models: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        await asyncio.sleep(3600)  # Refresh every hour


async def refresh_models_dev_catalog(app: FastAPI):
    app.state.models_dev_catalog = await fetch_models_dev_catalog(app.state.http_client)


async def cron_refresh_models_dev_catalog(app: FastAPI):
    while True:
        try:
            logger.info("Cron job: Refreshing models.dev catalog.")
            await refresh_models_dev_catalog(app)
        except Exception as e:
            logger.error(f"Cron job: Error refreshing models.dev catalog: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        await asyncio.sleep(MODELS_DEV_REFRESH_INTERVAL_SECONDS)


async def cron_cleanup_external_file_cache(app: FastAPI):
    while True:
        try:
            logger.info("Cron job: Cleaning up expired external file cache.")
            deleted = await cleanup_expired_external_file_cache(app.state.pg_engine)
            if deleted:
                logger.info("Cron job: Deleted %s expired external cache files.", deleted)
        except Exception as e:
            logger.error(f"Cron job: Error cleaning external file cache: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        await asyncio.sleep(EXTERNAL_FILE_CACHE_CLEANUP_INTERVAL_SECONDS)


async def shutdown_background_tasks(tasks: list[asyncio.Task[None]]):
    for task in tasks:
        task.cancel()

    if not tasks:
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for task, result in zip(tasks, results):
        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
            logger.error(
                f"Background task {task.get_name()} failed during shutdown: {result}",
                exc_info=result,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()
    app.state.available_models = None
    app.state.models_dev_catalog = None
    app.state.background_tasks = []
    app.state.http_client = None
    app.state.git_http_client = None
    app.state.redis_manager = None
    app.state.pg_engine = None
    app.state.neo4j_driver = None

    try:
        sentry_dsn = os.getenv("SENTRY_DSN")
        if sentry_dsn:
            logger.info(f"Sentry DSN found, initializing Sentry with DSN: {sentry_dsn}")
            sentry_sdk.init(
                dsn=sentry_dsn,
                # Add data like request headers and IP for users
                send_default_pii=True,
                # Enable sending logs to Sentry
                enable_logs=True,
                # Set traces_sample_rate to 1.0 to capture 100%
                # of transactions for tracing.
                traces_sample_rate=1.0,
                # Set profile_session_sample_rate to 1.0 to profile 100%
                # of profile sessions.
                profile_session_sample_rate=1.0,
                # Set profile_lifecycle to "trace" to automatically
                # run the profiler on when there is an active transaction
                profile_lifecycle="trace",
                profiles_sample_rate=1.0,
                enable_tracing=True,
                environment=os.getenv("ENV", "dev"),
                integrations=[
                    FastApiIntegration(),
                    SqlalchemyIntegration(),
                    HttpxIntegration(),
                ],
            )
            logger.info("Sentry initialized.")
        else:
            logger.info("No Sentry DSN found, skipping Sentry initialization.")

        app.state.pg_engine = await get_pg_async_engine()

        recovered_image_jobs = await recover_stale_image_generation_jobs(app.state.pg_engine)
        if recovered_image_jobs:
            logger.warning(
                "Startup: Marked %s stale image generation jobs as failed.",
                recovered_image_jobs,
            )

        userpass = await parse_userpass(os.getenv("USERPASS") or "")

        new_users = await create_initial_users(app.state.pg_engine, userpass)
        for user in new_users:
            await create_user_root_folder(app.state.pg_engine, user.id)
            await update_settings(app.state.pg_engine, user.id, DEFAULT_SETTINGS.model_dump())

        app.state.neo4j_driver = await get_neo4j_async_driver()
        await create_neo4j_indexes(app.state.neo4j_driver)

        app.state.master_open_router_api_key = os.getenv("MASTER_OPEN_ROUTER_API_KEY")
        if not app.state.master_open_router_api_key:
            raise ValueError("MASTER_OPEN_ROUTER_API_KEY is not set")

        limits = httpx.Limits(max_connections=500, max_keepalive_connections=50)
        timeout = httpx.Timeout(120.0, connect=10.0, read=60.0)
        app.state.http_client = httpx.AsyncClient(timeout=timeout, limits=limits, http2=True)
        app.state.git_http_client = httpx.AsyncClient(timeout=timeout, limits=limits, http2=False)

        app.state.redis_manager = RedisManager(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD", None),
        )

        app.state.connection_manager = connection_manager

        try:
            await refresh_models_dev_catalog(app)
        except Exception as e:
            logger.error(f"Startup: Error refreshing models.dev catalog: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        try:
            await refresh_openrouter_models(app)
        except Exception as e:
            logger.error(f"Startup: Error refreshing OpenRouter models: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        app.state.background_tasks = [
            asyncio.create_task(cron_delete_temp_graphs(app), name="cron_delete_temp_graphs"),
            asyncio.create_task(
                cron_refresh_openrouter_models(app),
                name="cron_refresh_openrouter_models",
            ),
            asyncio.create_task(
                cron_refresh_models_dev_catalog(app),
                name="cron_refresh_models_dev_catalog",
            ),
            asyncio.create_task(
                cron_cleanup_external_file_cache(app),
                name="cron_cleanup_external_file_cache",
            ),
        ]

        yield
    finally:
        await shutdown_background_tasks(app.state.background_tasks)

        if app.state.http_client is not None:
            await app.state.http_client.aclose()

        if app.state.git_http_client is not None:
            await app.state.git_http_client.aclose()

        if app.state.redis_manager is not None:
            await app.state.redis_manager.close()

        if app.state.neo4j_driver is not None:
            await app.state.neo4j_driver.close()

        if app.state.pg_engine is not None:
            await app.state.pg_engine.dispose()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter

if os.getenv("ENV", "dev") == "dev":
    origins = ["*"]
else:
    origins = os.getenv("ALLOW_CORS_ORIGINS", "").split(",")

logger.info(f"Allowed CORS origins: {origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
)
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for request {request.url}: {exc}", exc_info=True)
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected server error occurred."},
    )


app.include_router(graph.router)
app.include_router(chat.router)
app.include_router(models.router)
app.include_router(inference_providers.router)
app.include_router(users.router)
app.include_router(github.router)
app.include_router(gitlab.router)
app.include_router(google_drive.router)
app.include_router(repository.router)
app.include_router(files.router)
app.include_router(images.router)
app.include_router(prompt_templates.router)
app.include_router(prompt_improver.router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
