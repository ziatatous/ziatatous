"""HTTP helper: honest User-Agent, per-host politeness delay, retries with exponential backoff."""
import threading
import time
from urllib.parse import urlparse
from urllib import robotparser

import httpx

from . import config

_last: dict[str, float] = {}
_lock = threading.Lock()
MIN_DELAY = 1.0  # seconds between two requests to the same host
_robots: dict[str, tuple[float, robotparser.RobotFileParser | None]] = {}


def _polite(host: str) -> None:
    with _lock:
        wait = _last.get(host, 0) + MIN_DELAY - time.time()
        _last[host] = time.time() + max(wait, 0)
    if wait > 0:
        time.sleep(wait)


def get(url: str, *, headers: dict | None = None, params: dict | None = None, retries: int = 3,
        timeout: float = 25, polite: bool = True, **kw) -> httpx.Response:
    h = {"User-Agent": config.USER_AGENT, "Accept": "*/*"}
    h.update(headers or {})
    host = urlparse(url).netloc
    err: Exception | None = None
    for attempt in range(retries):
        if polite:
            _polite(host)
        try:
            r = httpx.get(url, headers=h, params=params, timeout=timeout, follow_redirects=True, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            return r
        except httpx.HTTPError as e:
            err = e
            time.sleep(2 ** attempt)
    raise err or RuntimeError("request failed")


def get_json(url: str, **kw):
    r = get(url, **kw)
    r.raise_for_status()
    return r.json()


def allowed_by_robots(url: str) -> bool:
    """Respect robots.txt before extracting a full article text locally."""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    cached = _robots.get(base)
    if not cached or time.time() - cached[0] > 86400:
        rp = robotparser.RobotFileParser()
        try:
            r = get(base + "/robots.txt", retries=1, timeout=10)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp = None
        _robots[base] = (time.time(), rp)
        cached = _robots[base]
    rp = cached[1]
    return True if rp is None else rp.can_fetch(config.USER_AGENT, url)
