from typing import Any

from fastapi import APIRouter, HTTPException

from deps import RundownEngineDep, VmixBridgeDep
from schemas import GoToStoryBody

router = APIRouter(prefix="/api/rundown", tags=["rundown"])


@router.get("/active")
async def active_rundown(engine: RundownEngineDep):
    return await engine.get_public_snapshot()


@router.post("/next")
async def next_rundown_step(engine: RundownEngineDep, bridge: VmixBridgeDep):
    """One operator step: next cue within the story, or next story; run cue vMix FUNCTIONs."""
    changed, ops = await engine.next_step()
    results: list[dict[str, Any]] = []
    for fn, inp, kw in ops:
        st = await bridge.send_command(fn, input=inp, **kw)
        results.append({"function": fn, "input": inp, "params": kw, "status": st})
    return {"ok": changed, "vmix": results}


@router.post("/advance")
async def advance_rundown(engine: RundownEngineDep, bridge: VmixBridgeDep):
    """Deprecated alias for /next (cue-aware + vMix). Prefer /next for Stream Deck."""
    return await next_rundown_step(engine, bridge)


@router.post("/go_to_story")
async def go_to_story(engine: RundownEngineDep, body: GoToStoryBody):
    ok = await engine.go_to_story(body.story_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Could not go to story (check active rundown)")
    return {"ok": True}
