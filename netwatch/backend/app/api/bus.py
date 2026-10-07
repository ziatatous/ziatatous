"""Tiny pub/sub for Server-Sent Events. publish() is safe to call from worker threads."""
import asyncio
import json

_subs: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


def bind(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def publish(kind: str, data: dict) -> None:
    msg = json.dumps({"kind": kind, **data})
    if _loop is None:
        return
    for q in list(_subs):
        _loop.call_soon_threadsafe(lambda q=q: q.put_nowait(msg) if q.qsize() < 200 else None)


async def stream():
    q: asyncio.Queue = asyncio.Queue()
    _subs.add(q)
    try:
        yield "retry: 5000\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=20)
                yield f"data: {msg}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _subs.discard(q)
