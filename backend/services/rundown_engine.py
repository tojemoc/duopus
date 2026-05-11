"""Rundown state machine driven by vMix tally and manual controls."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from sqlmodel import Session, col, select

from database import get_engine
from models import Rundown, Script, Story

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RundownEngine:
    def __init__(
        self,
        redis_url: str,
        tally_channel: str = "vmix:tally",
        state_channel: str = "rundown:state",
        active_key: str = "duopus:active_rundown_id",
    ) -> None:
        self.redis_url = redis_url
        self.tally_channel = tally_channel
        self.state_channel = state_channel
        self.active_key = active_key
        self._redis: aioredis.Redis | None = None
        self._pubsub_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._live_started_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def get_active_rundown_id(self) -> UUID | None:
        r = await self._ensure_redis()
        raw = await r.get(self.active_key)
        if not raw:
            return None
        try:
            return UUID(str(raw))
        except ValueError:
            return None

    async def set_active_rundown(self, rundown_id: UUID) -> None:
        async with self._lock:
            r = await self._ensure_redis()
            raw_prev = await r.get(self.active_key)
            prev_id: UUID | None = None
            if raw_prev:
                try:
                    prev_id = UUID(str(raw_prev))
                except ValueError:
                    prev_id = None
            await asyncio.to_thread(self._sync_set_active_rundown, prev_id, rundown_id)
            await r.set(self.active_key, str(rundown_id))
            self._live_started_at = utcnow()
            await self._publish_state()

    def _sync_set_active_rundown(self, prev_id: UUID | None, new_id: UUID) -> None:
        """Close out the previous active rundown and reset the target rundown for a clean switch."""
        with Session(get_engine()) as session:
            if prev_id and prev_id != new_id:
                stmt = select(Story).where(Story.rundown_id == prev_id)
                for s in session.exec(stmt).all():
                    if s.status == "live":
                        s.status = "done"
                        session.add(s)
            stmt = select(Story).where(Story.rundown_id == new_id)
            for s in session.exec(stmt).all():
                s.status = "pending"
                session.add(s)
            session.commit()

    async def start(self) -> None:
        if self._pubsub_task and not self._pubsub_task.done():
            return
        self._stop.clear()
        self._pubsub_task = asyncio.create_task(self._listen_tally(), name="rundown-engine-tally")

    async def stop(self) -> None:
        self._stop.set()
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def _publish_state(self) -> None:
        active_id: UUID | None = None
        try:
            r = await self._ensure_redis()
            active_id = await self.get_active_rundown_id()
            snap = await asyncio.to_thread(self._build_snapshot_sync, active_id, self._live_started_at)
            await r.publish(self.state_channel, json.dumps(snap))
        except Exception:
            log.exception(
                "publishing rundown state to Redis failed (channel=%s active_id=%s)",
                self.state_channel,
                active_id,
            )

    def _build_snapshot_sync(
        self,
        active_id: UUID | None,
        live_started_at: datetime | None,
    ) -> dict[str, Any]:
        if not active_id:
            return {
                "active_rundown": None,
                "stories": [],
                "live_story": None,
                "elapsed_seconds": 0,
            }
        with Session(get_engine()) as session:
            rundown = session.get(Rundown, active_id)
            if not rundown:
                return {
                    "active_rundown": None,
                    "stories": [],
                    "live_story": None,
                    "elapsed_seconds": 0,
                }
            stmt = (
                select(Story, Script)
                .outerjoin(Script, Script.story_id == Story.id)
                .where(Story.rundown_id == active_id)
                .order_by(col(Story.position))
            )
            rows = session.exec(stmt).all()
            stories_out: list[dict[str, Any]] = []
            live_story: dict[str, Any] | None = None
            for story, script in rows:
                body = script.body if script else ""
                row = {
                    "id": str(story.id),
                    "position": story.position,
                    "title": story.title,
                    "type": story.type,
                    "planned_duration": story.planned_duration,
                    "actual_duration": story.actual_duration,
                    "vmix_input": story.vmix_input,
                    "status": story.status,
                    "script_body": body,
                }
                stories_out.append(row)
                if story.status == "live":
                    live_story = row
            elapsed = 0
            if live_story and live_started_at:
                elapsed = max(0, int((utcnow() - live_started_at).total_seconds()))
            return {
                "active_rundown": {
                    "id": str(rundown.id),
                    "title": rundown.title,
                    "show_date": rundown.show_date.isoformat(),
                    "status": rundown.status,
                },
                "stories": stories_out,
                "live_story": live_story,
                "elapsed_seconds": elapsed,
            }

    async def get_public_snapshot(self) -> dict[str, Any]:
        active_id = await self.get_active_rundown_id()
        return await asyncio.to_thread(self._build_snapshot_sync, active_id, self._live_started_at)

    def _sync_on_program_input(self, active_id: UUID | None, program_input: int | None) -> bool:
        if not active_id or program_input is None:
            return False
        with Session(get_engine()) as session:
            stmt = (
                select(Story)
                .where(Story.rundown_id == active_id)
                .order_by(col(Story.position))
            )
            stories = list(session.exec(stmt).all())
            target: Story | None = None
            for s in stories:
                if s.vmix_input is not None and s.vmix_input == program_input:
                    target = s
                    break
            if target is None:
                return False
            current_live = next((s for s in stories if s.status == "live"), None)
            if current_live and current_live.id == target.id:
                return False
            now = utcnow()
            if current_live:
                current_live.status = "done"
                if self._live_started_at:
                    current_live.actual_duration = max(
                        1,
                        int((now - self._live_started_at).total_seconds()),
                    )
                session.add(current_live)
            for s in stories:
                if s.id == target.id:
                    s.status = "live"
                elif s.status == "live":
                    s.status = "done"
                session.add(s)
            session.commit()
            return True

    async def on_program_input(self, program_input: int | None) -> None:
        async with self._lock:
            active_id = await self.get_active_rundown_id()
            changed = await asyncio.to_thread(
                self._sync_on_program_input_with_timer,
                active_id,
                program_input,
            )
        if changed:
            await self._publish_state()

    def _sync_on_program_input_with_timer(
        self,
        active_id: UUID | None,
        program_input: int | None,
    ) -> bool:
        changed = self._sync_on_program_input(active_id, program_input)
        if changed:
            self._live_started_at = utcnow()
        return changed

    async def _listen_tally(self) -> None:
        r = await self._ensure_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(self.tally_channel)
        try:
            while not self._stop.is_set():
                try:
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if not msg or msg.get("type") != "message":
                        continue
                    data = json.loads(msg["data"])
                    program_input = data.get("program_input")
                    if program_input is not None:
                        program_input = int(program_input)
                    await self.on_program_input(program_input)
                except json.JSONDecodeError:
                    continue
                except Exception:
                    log.exception("Failed to process vmix:tally message")
                    continue
        finally:
            await pubsub.unsubscribe(self.tally_channel)
            await pubsub.aclose()

    def _sync_advance(self, active_id: UUID | None) -> bool:
        if not active_id:
            return False
        with Session(get_engine()) as session:
            stmt = (
                select(Story)
                .where(Story.rundown_id == active_id)
                .order_by(col(Story.position))
            )
            stories = list(session.exec(stmt).all())
            if not stories:
                return False
            now = utcnow()
            idx_live = next((i for i, s in enumerate(stories) if s.status == "live"), None)
            if idx_live is not None:
                cur = stories[idx_live]
                cur.status = "done"
                if self._live_started_at:
                    cur.actual_duration = max(1, int((now - self._live_started_at).total_seconds()))
                session.add(cur)
                nxt_idx = idx_live + 1
                if nxt_idx >= len(stories):
                    session.commit()
                    return True
                nxt = stories[nxt_idx]
                for s in stories:
                    if s.id == nxt.id:
                        s.status = "live"
                    elif s.status == "live" and s.id != nxt.id:
                        s.status = "done"
                    session.add(s)
                session.commit()
                return True
            nxt_idx = next((i for i, s in enumerate(stories) if s.status == "pending"), None)
            if nxt_idx is None:
                return False
            nxt = stories[nxt_idx]
            for s in stories:
                if s.id == nxt.id:
                    s.status = "live"
                elif s.status == "live":
                    s.status = "done"
                session.add(s)
            session.commit()
            return True

    async def advance(self) -> bool:
        async with self._lock:
            active_id = await self.get_active_rundown_id()
            changed = await asyncio.to_thread(self._sync_advance_with_timer, active_id)
        if changed:
            await self._publish_state()
        return changed

    def _sync_advance_with_timer(self, active_id: UUID | None) -> bool:
        changed = self._sync_advance(active_id)
        if changed:
            if active_id and self._has_live_story(active_id):
                self._live_started_at = utcnow()
            else:
                self._live_started_at = None
        return changed

    def _has_live_story(self, active_id: UUID) -> bool:
        with Session(get_engine()) as session:
            stmt = select(Story).where(Story.rundown_id == active_id, Story.status == "live")
            return session.exec(stmt).first() is not None

    async def go_to_story(self, story_id: UUID) -> bool:
        async with self._lock:
            active_id = await self.get_active_rundown_id()
            changed = await asyncio.to_thread(self._sync_go_to_story_with_timer, active_id, story_id)
        if changed:
            await self._publish_state()
        return changed

    def _sync_go_to_story_with_timer(self, active_id: UUID | None, story_id: UUID) -> bool:
        changed = self._sync_go_to_story_fixed(active_id, story_id)
        if changed:
            self._live_started_at = utcnow()
        return changed

    def _sync_go_to_story_fixed(self, active_id: UUID | None, story_id: UUID) -> bool:
        if not active_id:
            return False
        with Session(get_engine()) as session:
            stmt = (
                select(Story)
                .where(Story.rundown_id == active_id)
                .order_by(col(Story.position))
            )
            stories = list(session.exec(stmt).all())
            target = next((s for s in stories if s.id == story_id), None)
            if not target:
                return False
            current_live = next((s for s in stories if s.status == "live"), None)
            if current_live and current_live.id == target.id:
                return False
            now = utcnow()
            if current_live and current_live.id != target.id and self._live_started_at:
                current_live.actual_duration = max(
                    1,
                    int((now - self._live_started_at).total_seconds()),
                )
                current_live.status = "done"
                session.add(current_live)
            for s in stories:
                if s.position < target.position:
                    s.status = "done"
                elif s.id == target.id:
                    s.status = "live"
                else:
                    s.status = "pending"
                session.add(s)
            session.commit()
            return True

