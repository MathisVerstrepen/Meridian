import logging
import os
from contextlib import asynccontextmanager

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from const.settings import DEFAULT_SETTINGS
from database.neo4j.core import get_neo4j_async_driver
from database.pg.core import get_pg_async_engine
from database.pg.models import create_initial_users
from database.pg.settings_ops.settings_crud import update_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from models.usersDTO import SettingsDTO
from routers import chat, files, github, graph, models, users
from services.auth import parse_userpass
from services.files import create_user_root_folder
from services.openrouter import OpenRouterReq, list_available_models
from utils.helpers import load_environment_variables

logger = logging.getLogger("uvicorn.error")

if not os.path.exists("data/user_files"):
    os.makedirs("data/user_files")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()

    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        logger.info(f"Sentry DSN found, initializing Sentry with DSN: {sentry_dsn}")
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=1,
            profiles_sample_rate=1,
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

    userpass = parse_userpass(os.getenv("USERPASS") or "")

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
                blockParallelization=DEFAULT_SETTINGS.blockParallelization,
                blockRouting=DEFAULT_SETTINGS.blockRouting,
            ).model_dump(),
        )

    app.state.neo4j_driver = await get_neo4j_async_driver()

    app.state.master_open_router_api_key = os.getenv("MASTER_OPEN_ROUTER_API_KEY")
    if not app.state.master_open_router_api_key:
        raise ValueError("MASTER_OPEN_ROUTER_API_KEY is not set")

    app.state.available_models = await list_available_models(
        OpenRouterReq(
            api_key=app.state.master_open_router_api_key,
        )
    )

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

app.include_router(graph.router)
app.include_router(chat.router)
app.include_router(models.router)
app.include_router(users.router)
app.include_router(github.router)
app.include_router(files.router)

app.mount("/static", StaticFiles(directory="data"), name="data")


@app.get("/")
def read_root():
    return {"Hello": "World"}
