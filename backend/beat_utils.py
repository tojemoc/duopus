from __future__ import annotations

import json
from typing import Any

from schemas import Beat


def beats_to_json(beats: list[Beat]) -> str:
    return json.dumps([b.model_dump() for b in beats], ensure_ascii=False)


def beats_from_json(raw: str) -> list[Beat]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[Beat] = []
    for item in data:
        if isinstance(item, dict):
            try:
                out.append(Beat.model_validate(item))
            except Exception:
                continue
    return out


def planned_duration_from_beats(raw: str, override: int | None) -> int:
    beats = beats_from_json(raw)
    total = sum(max(0, int(b.duration or 0)) for b in beats)
    if total > 0:
        return total
    return max(0, int(override or 0))
