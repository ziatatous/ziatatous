"""APScheduler wiring + catch-up of missed collections at startup."""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from . import db
from .collectors import base
from .collectors import load_all
from .processing import maintenance

log = logging.getLogger("netwatch.sched")
_sched: BackgroundScheduler | None = None


def _due(c: base.Collector) -> bool:
    last = base.last_success(c.name)
    if not last:
        return True
    t = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - t > timedelta(minutes=c.interval_min)


def start(collect: bool = True) -> BackgroundScheduler:
    global _sched
    load_all()
    _sched = BackgroundScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600})
    if collect:
        for i, c in enumerate(base.REGISTRY.values()):
            # first run is handled by the catch-up below; the interval then keeps the cadence
            _sched.add_job(c.run, "interval", minutes=c.interval_min, id=c.name)
        _sched.add_job(maintenance.periodic, "interval", minutes=10, id="maintenance",
                       next_run_time=datetime.now(timezone.utc) + timedelta(seconds=90))
        _sched.add_job(maintenance.retention, "cron", hour=4, minute=15, id="retention")
    _sched.start()
    if collect:
        # catch-up: run what we missed while the PC was off, one after the other
        missed = [c.name for c in base.REGISTRY.values() if _due(c)]
        log.info("catch-up: %d collectors due: %s", len(missed), missed)
        base.run_async(missed)
    return _sched


def stop() -> None:
    if _sched:
        _sched.shutdown(wait=False)
