import json

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request

from schemas import PrompterSpeedBody

router = APIRouter(prefix="/api/prompter", tags=["prompter"])

SPEED_KEY = "duopus:prompter_speed_level"
SPEED_CHANNEL = "prompter:speed"
_MIN, _MAX = -20, 20


@router.post("/speed")
async def set_prompter_speed(request: Request, body: PrompterSpeedBody):
    delta = body.delta
    r: aioredis.Redis = request.app.state.redis_client
    raw = await r.get(SPEED_KEY)
    level = int(raw) if raw is not None else 0
    level = max(_MIN, min(_MAX, level + int(delta)))
    await r.set(SPEED_KEY, str(level))
    msg = json.dumps({"delta": delta, "level": level})
    await r.publish(SPEED_CHANNEL, msg)
    hub = request.app.state.ws_hub
    await hub.broadcast({"type": "prompter_speed", "payload": json.loads(msg)})
    return {"ok": True, "level": level}
