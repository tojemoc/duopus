import json

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request

from schemas import PrompterSpeedBody

router = APIRouter(prefix="/api/prompter", tags=["prompter"])

SPEED_KEY = "duopus:prompter_speed_level"
SPEED_CHANNEL = "prompter:speed"
_MIN, _MAX = -20, 20
_LUA_SET_SPEED = r"""
local key = KEYS[1]
local delta = tonumber(ARGV[1]) or 0
local minv = tonumber(ARGV[2])
local maxv = tonumber(ARGV[3])
local raw = redis.call('GET', key)
local cur = tonumber(raw)
if cur == nil then cur = 0 end
local nextv = cur + delta
if nextv < minv then nextv = minv end
if nextv > maxv then nextv = maxv end
redis.call('SET', key, tostring(nextv))
return nextv
"""


@router.post("/speed")
async def set_prompter_speed(request: Request, body: PrompterSpeedBody):
    delta = body.delta
    r: aioredis.Redis = request.app.state.redis_client
    level = int(await r.eval(_LUA_SET_SPEED, 1, SPEED_KEY, int(delta), _MIN, _MAX))
    msg = json.dumps({"delta": delta, "level": level})
    await r.publish(SPEED_CHANNEL, msg)
    hub = request.app.state.ws_hub
    await hub.broadcast({"type": "prompter_speed", "payload": json.loads(msg)})
    return {"ok": True, "level": level}
