from fastapi import APIRouter, HTTPException

from deps import RundownEngineDep
from schemas import GoToStoryBody

router = APIRouter(prefix="/api/rundown", tags=["rundown"])


@router.get("/active")
async def active_rundown(engine: RundownEngineDep):
    return await engine.get_public_snapshot()


@router.post("/advance")
async def advance_rundown(engine: RundownEngineDep):
    ok = await engine.advance()
    return {"ok": ok}


@router.post("/go_to_story")
async def go_to_story(engine: RundownEngineDep, body: GoToStoryBody):
    ok = await engine.go_to_story(body.story_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Could not go to story (check active rundown)")
    return {"ok": True}
