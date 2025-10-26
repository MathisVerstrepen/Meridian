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
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from models.usersDTO import SettingsDTO
from routers import chat, files, github, graph, models, users, gitlab, repository
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from services.auth import parse_userpass
from services.connection_manager import manager as connection_manager
from services.files import create_user_root_folder
from services.openrouter import OpenRouterReq, list_available_models
from utils.helpers import load_environment_variables

logging.getLogger("urllib3").setLevel(logging.ERROR)
logger = logging.getLogger("uvicorn.error")

if not os.path.exists("data/user_files"):
    os.makedirs("data/user_files")


async def cron_delete_temp_graphs(app: FastAPI):
    while True:
        try:
            logger.info("Cron job: Running job to delete old temporary graphs.")
            await delete_old_temporary_graphs(app.state.pg_engine, app.state.neo4j_driver)
        except Exception as e:
            logger.error(f"Cron job: Error deleting old temporary graphs: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        await asyncio.sleep(3600)  # Refresh every hour


async def cron_refresh_openrouter_models(app: FastAPI):
    while True:
        try:
            logger.info("Cron job: Refreshing OpenRouter models.")
            openRouterReq = OpenRouterReq(
                api_key=app.state.master_open_router_api_key,
            )
            models = await list_available_models(openRouterReq)
            app.state.available_models = models
        except Exception as e:
            logger.error(f"Cron job: Error refreshing OpenRouter models: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)

        await asyncio.sleep(3600)  # Refresh every hour


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()

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

    userpass = await parse_userpass(os.getenv("USERPASS") or "")

    new_users = await create_initial_users(app.state.pg_engine, userpass)
    for user in new_users:
        await create_user_root_folder(app.state.pg_engine, user.id)
        await update_settings(
            app.state.pg_engine,
            user.id,
            SettingsDTO(
                general=DEFAULT_SETTINGS.general,
                account=DEFAULT_SETTINGS.account,
                appearance=DEFAULT_SETTINGS.appearance,
                models=DEFAULT_SETTINGS.models,
                modelsDropdown=DEFAULT_SETTINGS.modelsDropdown,
                block=DEFAULT_SETTINGS.block,
                blockAttachment=DEFAULT_SETTINGS.blockAttachment,
                blockParallelization=DEFAULT_SETTINGS.blockParallelization,
                blockRouting=DEFAULT_SETTINGS.blockRouting,
                blockGithub=DEFAULT_SETTINGS.blockGithub,
                tools=DEFAULT_SETTINGS.tools,
                toolsWebSearch=DEFAULT_SETTINGS.toolsWebSearch,
                toolsLinkExtraction=DEFAULT_SETTINGS.toolsLinkExtraction,
            ).model_dump(),
        )

    app.state.neo4j_driver = await get_neo4j_async_driver()
    await create_neo4j_indexes(app.state.neo4j_driver)

    app.state.master_open_router_api_key = os.getenv("MASTER_OPEN_ROUTER_API_KEY")
    if not app.state.master_open_router_api_key:
        raise ValueError("MASTER_OPEN_ROUTER_API_KEY is not set")

    asyncio.create_task(cron_delete_temp_graphs(app))
    asyncio.create_task(cron_refresh_openrouter_models(app))

    limits = httpx.Limits(max_connections=500, max_keepalive_connections=50)
    timeout = httpx.Timeout(60.0, connect=10.0, read=30.0)
    http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
    app.state.http_client = http_client

    app.state.redis_manager = RedisManager(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD", None),
    )

    app.state.connection_manager = connection_manager

    yield


app = FastAPI(lifespan=lifespan)

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
app.include_router(users.router)
app.include_router(github.router)
app.include_router(gitlab.router)
app.include_router(repository.router)
app.include_router(files.router)

app.mount("/static", StaticFiles(directory="data"), name="data")


@app.get("/")
def read_root():
    return {"Hello": "World"}
