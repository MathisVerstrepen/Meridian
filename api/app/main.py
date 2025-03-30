from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager

from utils.helpers import load_environment_variables
from database.pg.core import get_pg_async_engine
from database.pg.models import init_db
from database.neo4j.core import get_neo4j_async_driver

from routers import graph, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()

    app.state.pg_engine = await get_pg_async_engine()
    await init_db(app.state.pg_engine)

    app.state.neo4j_driver = await get_neo4j_async_driver()

    app.state.open_router_api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not app.state.open_router_api_key:
        raise ValueError("OPEN_ROUTER_API_KEY is not set")

    yield


app = FastAPI(lifespan=lifespan)
app.include_router(graph.router)
app.include_router(chat.router)

if os.getenv("ENV", "dev") == "dev":
    origins = [
        "*",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
def read_root():
    return {"Hello": "World"}
