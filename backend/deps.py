from typing import Annotated

from fastapi import Depends, Request

from services.rundown_engine import RundownEngine
from services.vmix_bridge import VmixBridge


def get_bridge(request: Request) -> VmixBridge:
    return request.app.state.vmix_bridge


def get_rundown_engine(request: Request) -> RundownEngine:
    return request.app.state.rundown_engine


VmixBridgeDep = Annotated[VmixBridge, Depends(get_bridge)]
RundownEngineDep = Annotated[RundownEngine, Depends(get_rundown_engine)]
