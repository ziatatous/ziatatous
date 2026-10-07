"""NETWATCH backend entrypoint. `python -m app.main` (UI + API) or `--collector-only` (future VPS mode)."""
import argparse
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, scheduler
from .api import bus, routes
from .processing import alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("netwatch")


def bootstrap(collect: bool = True) -> None:
    db.init()
    alerts.seed()
    from .collectors import load_all, sources_loader, corpos
    load_all()
    try:
        sources_loader.load()
        corpos.load_companies()
        from .collectors import rss
        rss.sync_feeds()
    except Exception as e:  # noqa: BLE001
        log.warning("data bootstrap: %s", e)
    scheduler.start(collect=collect)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus.bind(asyncio.get_running_loop())
    bootstrap(collect=not app.state.no_collect)
    yield
    scheduler.stop()


app = FastAPI(title="NETWATCH", version="0.1.0", lifespan=lifespan)
app.state.no_collect = False
app.include_router(routes.router)

if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (config.FRONTEND_DIST / path).resolve()
        if path and f.is_file() and config.FRONTEND_DIST in f.parents:
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")


def main() -> None:
    ap = argparse.ArgumentParser(description="NETWATCH")
    ap.add_argument("--collector-only", action="store_true", help="run collectors without serving the UI (VPS mode)")
    ap.add_argument("--no-collect", action="store_true", help="serve only, no scheduled collection")
    ap.add_argument("--check-feeds", action="store_true", help="test every RSS feed and exit")
    ap.add_argument("--host", default=config.HOST)
    ap.add_argument("--port", type=int, default=config.PORT)
    a = ap.parse_args()
    if a.check_feeds:
        db.init()
        from .collectors import rss
        for r in rss.check_all():
            print(("OK   " if r["ok"] else "DEAD ") + r["url"] + ("" if r["ok"] else f"  ({r['error']})"))
        return
    if a.collector_only:
        import time
        bootstrap(collect=True)
        log.info("collector-only mode; Ctrl+C to stop")
        while True:
            time.sleep(3600)
    app.state.no_collect = a.no_collect
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
