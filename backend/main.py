import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketQuery
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import get_engine
from routers import prompter, rundown_ops, rundowns, stories, vmix
from services.rundown_engine import RundownEngine
from services.vmix_bridge import VmixBridge
from ws.hub import WebSocketHub, websocket_endpoint

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    get_engine()
    app.state.redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    bridge = VmixBridge(
        host=settings.vmix_host,
        port=settings.vmix_port,
        redis_url=settings.redis_url,
    )
    engine = RundownEngine(redis_url=settings.redis_url)
    hub = WebSocketHub(redis_url=settings.redis_url)
    app.state.vmix_bridge = bridge
    app.state.rundown_engine = engine
    app.state.ws_hub = hub
    await hub.start()
    await bridge.start()
    await engine.start()
    log.info("Duopus backend started (vMix host=%s)", settings.vmix_host)
    yield
    await engine.stop()
    await bridge.stop()
    await hub.stop()
    await app.state.redis_client.aclose()


app = FastAPI(title="Duopus NRCS", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rundowns.router)
app.include_router(stories.router)
app.include_router(vmix.router)
app.include_router(rundown_ops.router)
app.include_router(prompter.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    client = websocket.query_params.get("client")
    hub: WebSocketHub = websocket.app.state.ws_hub
    bridge = websocket.app.state.vmix_bridge
    engine = websocket.app.state.rundown_engine
    await websocket_endpoint(hub, bridge, engine, websocket, client=client)
