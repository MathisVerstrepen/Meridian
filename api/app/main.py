from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager

from utils.helpers import load_environment_variables
from database.core import get_async_engine
from database.models import init_db

from routers import graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()
    app.state.pg_engine = await get_async_engine()
    await init_db(app.state.pg_engine)

    yield


app = FastAPI(lifespan=lifespan)
app.include_router(graph.router)

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
