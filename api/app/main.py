from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os

from utils.helpers import load_environment_variables
from database.pg.core import get_pg_async_engine
from database.pg.models import init_db
from database.pg.crud import update_settings
from database.neo4j.core import get_neo4j_async_driver
from services.openrouter import OpenRouterReq, list_available_models
from services.auth import parse_userpass
from const.settings import DEFAULT_SETTINGS
from models.usersDTO import SettingsDTO

from routers import graph, chat, models, users

logger = logging.getLogger("uvicorn.error")

if not os.path.exists("data/uploads"):
    os.makedirs("data/uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()

    app.state.pg_engine = await get_pg_async_engine()

    userpass = parse_userpass(os.getenv("USERPASS"))

    new_users = await init_db(app.state.pg_engine, userpass)
    for user in new_users:
        await update_settings(
            app.state.pg_engine,
            user.id,
            SettingsDTO(
                general=DEFAULT_SETTINGS.general,
                account=DEFAULT_SETTINGS.account,
                models=DEFAULT_SETTINGS.models,
                modelsDropdown=DEFAULT_SETTINGS.modelsDropdown,
                block=DEFAULT_SETTINGS.block,
                blockParallelization=DEFAULT_SETTINGS.blockParallelization,
            ).model_dump_json(),
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

app.mount("/static", StaticFiles(directory="data"), name="data")


@app.get("/")
def read_root():
    return {"Hello": "World"}
