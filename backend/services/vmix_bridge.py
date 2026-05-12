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
_VMIX_NAME_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")


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


def _validate_vmix_token(label: str, token: str) -> None:
    if not token or not _VMIX_NAME_TOKEN.fullmatch(token):
        raise ValueError(f"invalid vMix {label}: {token!r} (allowed: letters, digits, underscore, hyphen)")


def _coerce_vmix_input_number(input: Any) -> int | None:  # noqa: A002
    if input is None:
        return None
    if isinstance(input, bool):
        raise ValueError("invalid vMix input: boolean is not allowed")
    if isinstance(input, int):
        if input < 1:
            raise ValueError("invalid vMix input: must be a positive integer")
        return int(input)
    if isinstance(input, str):
        s = input.strip()
        if not s.isdigit():
            raise ValueError(f"invalid vMix input: {input!r}")
        n = int(s)
        if n < 1:
            raise ValueError("invalid vMix input: must be a positive integer")
        return n
    raise ValueError(f"invalid vMix input type: {type(input).__name__}")


def build_function_command(
    function_name: str,
    input: int | None = None,  # noqa: A002 — matches vMix / API naming
    **kwargs: Any,
) -> bytes:
    """Serialise a vMix shortcut FUNCTION command (TCP / HTTP query-string style)."""
    fn = function_name.strip()
    _validate_vmix_token("function name", fn)
    input_no = _coerce_vmix_input_number(input)
    parts: list[str] = []
    if input_no is not None:
        parts.append(f"Input={input_no}")
    for key, value in kwargs.items():
        if value is None:
            continue
        ks = str(key)
        if ks.lower() == "input":
            continue
        _validate_vmix_token("parameter name", ks)
        parts.append(f"{ks}={quote(str(value), safe='')}")
    query = "&".join(parts)
    if query:
        line = f"FUNCTION {fn} {query}\r\n"
    else:
        line = f"FUNCTION {fn}\r\n"
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
        old_writer = self._writer
        old_reader = self._reader
        if old_writer is not None:
            try:
                old_writer.close()
                await old_writer.wait_closed()
            except Exception:
                log.exception("closing vmix writer")
        if self._writer is old_writer:
            self._writer = None
        if self._reader is old_reader:
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
        try:
            for cmd in (b"SUBSCRIBE TALLY\r\n", b"SUBSCRIBE ACTS\r\n"):
                self._writer.write(cmd)
            await self._writer.drain()
            log.info("Connected to vMix at %s:%s", self.host, self.port)
            return True
        except Exception:
            log.exception("vMix subscribe handshake failed")
            await self._close_connection()
            return False

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
        try:
            payload = build_function_command(function_name, input=input, **kwargs)
        except ValueError:
            raise
        async with self._lock:
            writer = self._writer
            if not writer:
                return "disconnected"
            try:
                writer.write(payload)
                await writer.drain()
            except Exception as e:
                log.warning("send_command failed: %s", e)
                await self._close_connection()
                return "error"
        return "sent"
