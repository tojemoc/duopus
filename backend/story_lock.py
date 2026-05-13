"""Shared story edit-lock helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from models import utcnow

LOCK_TTL_SECONDS = 5 * 60


def lock_expired(locked_at: datetime | None) -> bool:
    if not locked_at:
        return True
    return utcnow() - locked_at > timedelta(seconds=LOCK_TTL_SECONDS)
