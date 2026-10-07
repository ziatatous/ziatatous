"""Agenda: user-maintained data/agenda.yaml (each entry carries its source URL) + FRED release calendar when a key exists."""
import hashlib
import logging
import time

import yaml

from .. import config, db, http
from .base import Collector, register

log = logging.getLogger("netwatch.agenda")


def from_yaml() -> int:
    p = config.DATA_DIR / "agenda.yaml"
    if not p.exists():
        return 0
    n = 0
    for e in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("events", []):
        uid = "yaml:" + hashlib.sha1(f"{e['date']}{e['title']}".encode()).hexdigest()[:12]
        n += db.execute("INSERT OR REPLACE INTO agenda(uid,date,kind,title,country,url,source) VALUES(?,?,?,?,?,?,?)",
                        (uid, str(e["date"]), e.get("kind", "other"), e["title"], e.get("country"), e.get("url"), e.get("source", "agenda.yaml")))
    return n


def fred_releases() -> int:
    k = config.key("FRED_API_KEY")
    if not k:
        return 0
    d = http.get_json("https://api.stlouisfed.org/fred/releases/dates", params={
        "api_key": k, "file_type": "json", "include_release_dates_with_no_data": "true",
        "realtime_start": time.strftime("%Y-%m-%d"), "realtime_end": time.strftime("%Y-12-31"), "limit": 200,
        "sort_order": "asc", "order_by": "release_date"})
    n = 0
    for r in d.get("release_dates", []):
        if r["date"] < time.strftime("%Y-%m-%d"):
            continue
        n += db.execute("INSERT OR REPLACE INTO agenda(uid,date,kind,title,country,url,source) VALUES(?,?,?,?,?,?,?)",
                        (f"fred:{r['release_id']}:{r['date']}", r["date"], "macro", f"Data release: {r['release_name']}", "US",
                         f"https://fred.stlouisfed.org/releases?rid={r['release_id']}", "FRED"))
    return n


def collect() -> int:
    return from_yaml() + fred_releases()


register(Collector("agenda", "agenda", 720, collect))
