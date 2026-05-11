"""Persistent async TCP client for vMix TCP API (port 8099)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import redis.asyncio as aioredis

log = logging.getLogger(__name__)

TALLY_OK_RE = re.compile(r"^TALLY OK (.+)$")


@dataclass
class VmixTallyState:
    """Per-input tally: 0 = off, 1 = program, 2 = preview (vMix TCP API)."""

    digits: str = ""
    program_input: int | None = None
    preview_input: int | None = None
    by_input: dict[int, int] = field(default_factory=dict)

    def to_pub_dict(self) -> dict[str, Any]:
        return {
            "digits": self.digits,
            "program_input": self.program_input,
            "preview_input": self.preview_input,
            "by_input": {str(k): v for k, v in self.by_input.items()},
        }


def parse_tally_ok_line(line: str) -> VmixTallyState | None:
    line = line.strip()
    m = TALLY_OK_RE.match(line)
    if not m:
        return None
    digits = m.group(1).strip()
    by_input: dict[int, int] = {}
    program_input: int | None = None
    preview_input: int | None = None
    for i, ch in enumerate(digits):
        if not ch.isdigit():
            continue
        state = int(ch)
        input_no = i + 1
        by_input[input_no] = state
        if state == 1:
            program_input = input_no
        elif state == 2:
            preview_input = input_no
    return VmixTallyState(
        digits=digits,
        program_input=program_input,
        preview_input=preview_input,
        by_input=by_input,
    )


def build_function_command(
    function_name: str,
    input: int | None = None,  # noqa: A002 — matches vMix / API naming
    **kwargs: Any,
) -> bytes:
    """Serialise a vMix shortcut FUNCTION command (TCP / HTTP query-string style)."""
    parts: list[str] = []
    if input is not None:
        parts.append(f"Input={input}")
    for key, value in kwargs.items():
        if value is None:
            continue
        parts.append(f"{key}={quote(str(value), safe='')}")
    query = "&".join(parts)
    if query:
        line = f"FUNCTION {function_name} {query}\r\n"
    else:
        line = f"FUNCTION {function_name}\r\n"
    return line.encode("utf-8")


class VmixBridge:
    def __init__(
        self,
        host: str,
        port: int,
        redis_url: str,
        tally_channel: str = "vmix:tally",
    ) -> None:
        self.host = host
        self.port = port
        self.redis_url = redis_url
        self.tally_channel = tally_channel
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._redis: aioredis.Redis | None = None
        self._tally = VmixTallyState()
        self._lock = asyncio.Lock()
        self._redis_lock = asyncio.Lock()
        self._run_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    @property
    def tally(self) -> VmixTallyState:
        return self._tally

    def get_state(self) -> dict[str, Any]:
        return {"tally": self._tally.to_pub_dict(), "connected": self._writer is not None}

    async def start(self) -> None:
        if self._run_task and not self._run_task.done():
            return
        self._stop.clear()
        self._run_task = asyncio.create_task(self._run_forever(), name="vmix-bridge")

    async def stop(self) -> None:
        self._stop.set()
        if self._run_task:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            self._run_task = None
        await self._close_connection()
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def _close_connection(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                log.exception("closing vmix writer")
            self._writer = None
            self._reader = None

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            async with self._redis_lock:
                if self._redis is None:
                    self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def _publish_tally(self) -> None:
        try:
            r = await self._ensure_redis()
            await r.publish(self.tally_channel, json.dumps(self._tally.to_pub_dict()))
        except Exception:
            log.exception("publishing tally to Redis failed; keeping vMix link up")

    async def _handle_line(self, line: str) -> None:
        parsed = parse_tally_ok_line(line)
        if parsed is None:
            return
        self._tally = parsed
        await self._publish_tally()

    async def _connect_once(self) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=10.0,
            )
        except Exception as e:
            log.warning("vMix connect failed: %s", e)
            return False
        assert self._writer is not None
        for cmd in (b"SUBSCRIBE TALLY\r\n", b"SUBSCRIBE ACTS\r\n"):
            self._writer.write(cmd)
        await self._writer.drain()
        log.info("Connected to vMix at %s:%s", self.host, self.port)
        return True

    async def _run_forever(self) -> None:
        delay = 1.0
        max_delay = 60.0
        while not self._stop.is_set():
            ok = await self._connect_once()
            if not ok:
                await asyncio.sleep(delay)
                delay = min(max_delay, delay * 2)
                continue
            delay = 1.0
            try:
                assert self._reader is not None
                while not self._stop.is_set():
                    raw = await self._reader.readuntil(b"\r\n")
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    await self._handle_line(line)
            except asyncio.IncompleteReadError:
                log.info("vMix connection closed (incomplete read)")
            except asyncio.LimitOverrunError:
                log.warning("vMix read limit overrun; reconnecting")
            except Exception:
                log.exception("vMix read loop error")
            finally:
                await self._close_connection()
                if self._stop.is_set():
                    break
                await asyncio.sleep(delay)
                delay = min(max_delay, delay * 2)

    async def send_command(
        self,
        function_name: str,
        input: int | None = None,  # noqa: A002
        **kwargs: Any,
    ) -> str:
        """Send a FUNCTION command on the live connection; returns a short status message."""
        payload = build_function_command(function_name, input=input, **kwargs)
        async with self._lock:
            if not self._writer:
                return "disconnected"
            try:
                self._writer.write(payload)
                await self._writer.drain()
            except Exception as e:
                log.warning("send_command failed: %s", e)
                await self._close_connection()
                return "error"
        return "sent"
