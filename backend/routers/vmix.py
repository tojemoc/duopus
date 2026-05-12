from fastapi import APIRouter, HTTPException

from deps import VmixBridgeDep
from schemas import VmixCommandBody

router = APIRouter(prefix="/api/vmix", tags=["vmix"])


@router.get("/state")
def vmix_state(bridge: VmixBridgeDep):
    return bridge.get_state()


@router.post("/command")
async def vmix_command(bridge: VmixBridgeDep, body: VmixCommandBody):
    if "input" in body.params:
        raise HTTPException(status_code=422, detail="params contains reserved key: input")
    try:
        status = await bridge.send_command(
            body.function,
            input=body.input,
            **body.params,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"status": status}
