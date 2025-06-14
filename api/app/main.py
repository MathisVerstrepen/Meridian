from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager

from utils.helpers import load_environment_variables
from database.pg.core import get_pg_async_engine
from database.pg.models import init_db
from database.pg.crud import does_user_exist
from database.neo4j.core import get_neo4j_async_driver
from services.openrouter import OpenRouterReq, list_available_models

from routers import graph, chat, models, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_environment_variables()

    app.state.pg_engine = await get_pg_async_engine()
    await init_db(app.state.pg_engine)

    app.state.neo4j_driver = await get_neo4j_async_driver()

    app.state.open_router_api_key = os.getenv("OPEN_ROUTER_API_KEY")
    if not app.state.open_router_api_key:
        raise ValueError("OPEN_ROUTER_API_KEY is not set")

    app.state.available_models = await list_available_models(
        OpenRouterReq(
            api_key=app.state.open_router_api_key,
        )
    )

    yield


app = FastAPI(lifespan=lifespan)

if os.getenv("ENV", "dev") == "dev":
    origins = ["*"]
else:
    origins = os.getenv("ALLOW_CORS_ORIGINS", "").split(",")

print(f"Allowed CORS origins: {origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-User-ID"],
)

app.include_router(graph.router)
app.include_router(chat.router)
app.include_router(models.router)
app.include_router(users.router)

app.mount("/static", StaticFiles(directory="data"), name="data")


@app.middleware("http")
async def user_id_in_database_middleware(request, call_next):
    """
    Middleware to ensure that the user ID is present in the database,
    except for routes starting with /auth/sync-user/ or OPTIONS requests.
    If the user ID is not found, it raises a 404 error.
    """
    authorized_routes = [
        "/auth/sync-user/",
        "/static/uploads",
    ]

    if request.method == "OPTIONS" or any(
        request.url.path.startswith(route) for route in authorized_routes
    ):
        return await call_next(request)

    user_id_header = request.headers.get("X-User-ID")
    if not user_id_header:
        return JSONResponse(
            status_code=400, content={"detail": "X-User-ID header is required."}
        )

    # TODO: Cache user existence check to avoid hitting the database on every request
    user_exists = await does_user_exist(request.app.state.pg_engine, user_id_header)

    if not user_exists:
        return JSONResponse(
            status_code=404, content={"detail": "User ID not found in the database."}
        )

    return await call_next(request)


@app.get("/")
def read_root():
    return {"Hello": "World"}
