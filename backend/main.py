import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import init_db
from routers import auth_routes, prompter, rundowns, scripts, stories, templates, users
from seed import ensure_seed_data
from services.autogen import autogen_loop

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    await ensure_seed_data()

    stop = asyncio.Event()
    task = asyncio.create_task(autogen_loop(stop, autogen_time_utc=settings.autogen_time_utc))
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        with contextlib.suppress(Exception):
            await task


app = FastAPI(title="Duopus NRCS (Phase 1)", lifespan=lifespan)
settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(users.router)
app.include_router(templates.router)
app.include_router(rundowns.router)
app.include_router(stories.router)
app.include_router(scripts.router)
app.include_router(prompter.router)


@app.get("/health")
def health():
    return {"status": "ok"}
