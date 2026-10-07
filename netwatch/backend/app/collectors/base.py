"""Collector framework: a failing collector never blocks the others; every run is logged."""
import logging
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Callable

from .. import db

log = logging.getLogger("netwatch.collect")
_running: set[str] = set()
_run_lock = threading.Lock()


@dataclass
class Collector:
    name: str
    family: str            # rss | events | markets | official | corpos | graph | agenda
    interval_min: int      # scheduling period
    fn: Callable[[], int]  # returns number of items stored
    needs: str = ""        # name of env key(s) required, informational

    def run(self) -> dict:
        with _run_lock:
            if self.name in _running:
                return {"collector": self.name, "skipped": True}
            _running.add(self.name)
        started = db.now()
        ok, items, error = 1, 0, None
        try:
            items = int(self.fn() or 0)
        except Exception as e:  # noqa: BLE001 - isolation is the whole point
            ok, error = 0, f"{type(e).__name__}: {e}"
            log.warning("collector %s failed: %s\n%s", self.name, error, traceback.format_exc(limit=3))
        finally:
            with _run_lock:
                _running.discard(self.name)
        db.execute("INSERT INTO collector_runs(collector,family,started,finished,ok,items,error) VALUES(?,?,?,?,?,?,?)",
                   (self.name, self.family, started, db.now(), ok, items, error))
        return {"collector": self.name, "ok": bool(ok), "items": items, "error": error}


REGISTRY: dict[str, Collector] = {}


def register(c: Collector) -> Collector:
    REGISTRY[c.name] = c
    return c


def last_success(name: str) -> str | None:
    r = db.one("SELECT finished FROM collector_runs WHERE collector=? AND ok=1 ORDER BY id DESC LIMIT 1", (name,))
    return r["finished"] if r else None


def status() -> list[dict]:
    out = []
    for c in REGISTRY.values():
        last = db.one("SELECT * FROM collector_runs WHERE collector=? ORDER BY id DESC LIMIT 1", (c.name,))
        agg = db.one("SELECT COUNT(*) n, SUM(ok) oks, SUM(items) items FROM collector_runs WHERE collector=?", (c.name,))
        out.append(dict(name=c.name, family=c.family, interval_min=c.interval_min, needs=c.needs,
                        last_success=last_success(c.name), last_run=last, runs=agg["n"],
                        total_items=agg["items"] or 0,
                        running=c.name in _running))
    return out


def run_by_name(name: str) -> dict:
    return REGISTRY[name].run()


_pool = None


def run_async(names: list[str] | None = None) -> None:
    """Run collectors in the background, 4 at a time, so one slow collector (RSS) never delays the others."""
    global _pool
    from concurrent.futures import ThreadPoolExecutor
    _pool = _pool or ThreadPoolExecutor(max_workers=4, thread_name_prefix="collect")

    def one(n: str):
        try:
            REGISTRY[n].run()
        except Exception:  # noqa: BLE001
            pass
    for n in names or list(REGISTRY):
        _pool.submit(one, n)
