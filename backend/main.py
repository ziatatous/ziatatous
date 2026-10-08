"""ASFALTO backend: collects public RSS/ICS sources into SQLite and serves the UI.
No AI: only titles, summaries and links written by humans are stored."""
import datetime as dt
import html
import re
import shutil
import sqlite3
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path

import feedparser
import httpx
import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "asfalto.db"
UA = "Mozilla/5.0 (compatible; Asfalto/1.0; personal local reader)"

app = FastAPI(title="ASFALTO")


# ---------- helpers ----------
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def load_yaml(name):
    with open(DATA / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def init_db():
    DATA.mkdir(exist_ok=True)
    with db() as c:
        c.executescript(
            """
        CREATE TABLE IF NOT EXISTS items(
          id INTEGER PRIMARY KEY, link TEXT UNIQUE, title TEXT, summary TEXT,
          published TEXT, first_seen TEXT, source_id TEXT, source TEXT,
          orient TEXT, category TEXT, lang TEXT);
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY, uid TEXT UNIQUE, title TEXT, start TEXT, end TEXT,
          place TEXT, city TEXT, lat REAL, lon REAL, type TEXT, scene TEXT,
          source TEXT, link TEXT);
        CREATE TABLE IF NOT EXISTS runs(
          source_id TEXT PRIMARY KEY, name TEXT, kind TEXT, last_run TEXT,
          ok INTEGER, count INTEGER, error TEXT);
        CREATE TABLE IF NOT EXISTS notes(key TEXT PRIMARY KEY, text TEXT, updated TEXT);
        """
        )


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def clean(text, n=400):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n]


_robots = {}


def allowed(url):
    """Respect robots.txt (cached per host). If robots.txt is unreachable, allow."""
    p = urllib.parse.urlparse(url)
    host = f"{p.scheme}://{p.netloc}"
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = httpx.get(host + "/robots.txt", timeout=10, headers={"User-Agent": UA}, follow_redirects=True)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch(UA, url)


def fetch(url):
    if not allowed(url):
        raise RuntimeError("bloqué par robots.txt")
    r = httpx.get(url, timeout=20, headers={"User-Agent": UA}, follow_redirects=True)
    r.raise_for_status()
    return r.text


def record(c, sid, name, kind, ok, count, err=""):
    c.execute(
        "INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?,?)", (sid, name, kind, now(), int(ok), count, err[:300])
    )


# ---------- collectors ----------
def collect_feed(f):
    with db() as c:
        try:
            parsed = feedparser.parse(fetch(f["url"]))
            if not parsed.entries:
                raise RuntimeError("aucun article trouvé (flux vide ou invalide)")
            n = 0
            for e in parsed.entries[:60]:
                link = e.get("link")
                if not link:
                    continue
                pub = e.get("published_parsed") or e.get("updated_parsed")
                pub = dt.datetime(*pub[:6]).isoformat() if pub else now()
                cur = c.execute(
                    "INSERT OR IGNORE INTO items(link,title,summary,published,first_seen,source_id,source,orient,category,lang)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (link, clean(e.get("title"), 300), clean(e.get("summary")), pub, now(), f["id"],
                     f["name"], f.get("orient", ""), f.get("category", "general"), f.get("lang", "")),
                )
                n += cur.rowcount
            record(c, f["id"], f["name"], "rss", True, len(parsed.entries))
        except Exception as ex:
            record(c, f["id"], f["name"], "rss", False, 0, str(ex))


def collect_calendar(s, cities):
    from ics import Calendar

    city = cities.get(s.get("city", "madrid"), {})
    with db() as c:
        try:
            text = fetch(s["url"])
            n = 0
            if s.get("kind", "ics") == "ics":
                for e in Calendar(text).events:
                    geo = getattr(e, "geo", None)
                    lat, lon = (geo[0], geo[1]) if geo else (city.get("lat"), city.get("lon"))
                    start = e.begin.isoformat() if e.begin else None
                    uid = f"{s['id']}|{e.uid or e.name}|{start}"
                    c.execute(
                        "INSERT OR REPLACE INTO events(uid,title,start,end,place,city,lat,lon,type,scene,source,link)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (uid, clean(e.name, 200), start, e.end.isoformat() if e.end else None,
                         clean(e.location, 200), s.get("city", "madrid"), lat, lon, s.get("type", "other"),
                         s.get("scene", ""), s["name"], e.url or s.get("page", "")),
                    )
                    n += 1
            else:  # rss agenda: dates come from the entry publication date
                for e in feedparser.parse(text).entries[:60]:
                    pub = e.get("published_parsed") or e.get("updated_parsed")
                    start = dt.datetime(*pub[:6]).isoformat() if pub else None
                    c.execute(
                        "INSERT OR REPLACE INTO events(uid,title,start,end,place,city,lat,lon,type,scene,source,link)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"{s['id']}|{e.get('link')}", clean(e.get("title"), 200), start, None, "",
                         s.get("city", "madrid"), city.get("lat"), city.get("lon"), s.get("type", "other"),
                         s.get("scene", ""), s["name"], e.get("link")),
                    )
                    n += 1
            record(c, s["id"], s["name"], "agenda", True, n)
        except Exception as ex:
            record(c, s["id"], s["name"], "agenda", False, 0, str(ex))


def collect_manual(cities):
    """Manually entered events (data/agenda.yaml -> manual:) are re-synced on each run."""
    ag = load_yaml("agenda.yaml")
    with db() as c:
        c.execute("DELETE FROM events WHERE source='manuel'")
        for i, e in enumerate(ag.get("manual") or []):
            city = cities.get(e.get("city", "madrid"), {})
            c.execute(
                "INSERT OR REPLACE INTO events(uid,title,start,end,place,city,lat,lon,type,scene,source,link)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"manual|{i}|{e['title']}", e["title"], str(e["start"]), None, e.get("place", ""),
                 e.get("city", "madrid"), e.get("lat", city.get("lat")), e.get("lon", city.get("lon")),
                 e.get("type", "other"), e.get("scene", ""), "manuel", e.get("link", "")),
            )


def collect_all():
    cities = load_yaml("cities.yaml")
    feeds = [f for f in (load_yaml("feeds.yaml").get("feeds") or []) if f.get("enabled", True)]
    sources = [s for s in (load_yaml("agenda.yaml").get("sources") or []) if s.get("enabled", True)]
    for f in feeds:
        collect_feed(f)
        time.sleep(1)  # be polite
    for s in sources:
        collect_calendar(s, cities)
        time.sleep(1)
    collect_manual(cities)


# ---------- API ----------
@app.get("/api/data/{name}")
def get_data(name: str):
    if name not in ("mouvements", "scenes", "annuaire", "surveillance", "cities"):
        raise HTTPException(404)
    fname = {"annuaire": "scenes_annuaire.yaml"}.get(name, f"{name}.yaml")
    return load_yaml(fname)


@app.get("/api/items")
def items(category: str = "", orient: str = "", q: str = "", limit: int = 80):
    sql, args = "SELECT * FROM items WHERE 1=1", []
    if category:
        sql += " AND category=?"; args.append(category)
    if orient:
        sql += " AND orient=?"; args.append(orient)
    if q:
        sql += " AND (title LIKE ? OR summary LIKE ?)"; args += [f"%{q}%"] * 2
    sql += " ORDER BY published DESC LIMIT ?"
    args.append(min(limit, 300))
    with db() as c:
        return [dict(r) for r in c.execute(sql, args)]


@app.get("/api/events")
def events(type: str = "", scene: str = "", city: str = "", past: bool = False):
    sql, args = "SELECT * FROM events WHERE 1=1", []
    if not past:
        sql += " AND (start IS NULL OR substr(start,1,10) >= ?)"; args.append(dt.date.today().isoformat())
    for col, v in (("type", type), ("scene", scene), ("city", city)):
        if v:
            sql += f" AND {col}=?"; args.append(v)
    sql += " ORDER BY start LIMIT 500"
    with db() as c:
        return [dict(r) for r in c.execute(sql, args)]


@app.get("/api/system")
def system():
    with db() as c:
        runs = [dict(r) for r in c.execute("SELECT * FROM runs ORDER BY ok, name")]
        n_items = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        n_ev = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return {"runs": runs, "items": n_items, "events": n_ev}


@app.post("/api/collect")
def collect_now():
    collect_all()
    return system()


@app.get("/api/notes/{key}")
def get_note(key: str):
    with db() as c:
        r = c.execute("SELECT text FROM notes WHERE key=?", (key,)).fetchone()
    return {"text": r["text"] if r else ""}


@app.put("/api/notes/{key}")
def put_note(key: str, body: dict):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO notes VALUES(?,?,?)", (key, body.get("text", ""), now()))
    return {"ok": True}


@app.get("/api/notes")
def all_notes():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM notes WHERE text<>'' ORDER BY updated DESC")]


@app.get("/api/export")
def export():
    with db() as c:  # flush the WAL/journal into the file before sending
        c.execute("PRAGMA wal_checkpoint")
    return FileResponse(DB, filename="asfalto-backup.db")


@app.post("/api/import")
async def import_db(file: UploadFile = File(...)):
    tmp = DATA / "import.tmp"
    tmp.write_bytes(await file.read())
    try:
        t = sqlite3.connect(tmp)
        t.execute("SELECT COUNT(*) FROM items"); t.execute("SELECT COUNT(*) FROM notes"); t.close()
    except Exception:
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, "fichier invalide")
    shutil.move(tmp, DB)
    return {"ok": True}


# ---------- startup ----------
sched = BackgroundScheduler()


@app.on_event("startup")
def startup():
    init_db()
    sched.add_job(collect_all, "interval", hours=3, id="collect", replace_existing=True)
    sched.start()
    # catch-up at launch: collect in background if data is older than 3 h
    with db() as c:
        last = c.execute("SELECT MAX(last_run) FROM runs").fetchone()[0]
    if not last or (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last)).total_seconds() > 3 * 3600:
        sched.add_job(collect_all, id="catchup")


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="ui")
