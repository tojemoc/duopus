"""WebSocket hub: fan-out Redis pub/sub to browser clients."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)


class WebSocketHub:
    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._clients: set[WebSocket] = set()
        self._redis: aioredis.Redis | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def start(self) -> None:
        if self._listener_task and not self._listener_task.done():
            return
        self._stop.clear()
        self._listener_task = asyncio.create_task(self._redis_fanout(), name="ws-hub-redis")

    async def stop(self) -> None:
        self._stop.set()
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        for ws in list(self._clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def _redis_fanout(self) -> None:
        r = await self._ensure_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("vmix:tally", "rundown:state", "prompter:speed")
        try:
            while not self._stop.is_set():
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg or msg.get("type") != "message":
                    continue
                channel = msg.get("channel")
                data = msg.get("data")
                if channel == "vmix:tally":
                    try:
                        payload = json.loads(data) if isinstance(data, str) else data
                    except json.JSONDecodeError:
                        continue
                    await self.broadcast({"type": "vmix", "payload": payload})
                elif channel == "rundown:state":
                    try:
                        payload = json.loads(data) if isinstance(data, str) else data
                    except json.JSONDecodeError:
                        continue
                    await self.broadcast({"type": "rundown", "payload": payload})
                elif channel == "prompter:speed":
                    try:
                        payload = json.loads(data) if isinstance(data, str) else data
                    except json.JSONDecodeError:
                        continue
                    await self.broadcast({"type": "prompter_speed", "payload": payload})
        finally:
            await pubsub.unsubscribe("vmix:tally", "rundown:state", "prompter:speed")
            await pubsub.aclose()

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


async def websocket_endpoint(
    hub: WebSocketHub,
    bridge,
    engine,
    websocket: WebSocket,
    client: str | None = None,
) -> None:
    await hub.register(websocket)
    try:
        snap = await engine.get_public_snapshot()
        await websocket.send_json(
            {
                "type": "bootstrap",
                "client": client,
                "rundown": snap,
                "vmix": bridge.get_state(),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(websocket)
