from fastapi import FastAPI
import os
from contextlib import asynccontextmanager

from utils.helpers import load_environment_variables
from database.core import get_async_engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()
    app.state.pg_engine = await get_async_engine()
    await init_db(app.state.pg_engine)

    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"Hello": os.getenv("DATABASE_URL")}
