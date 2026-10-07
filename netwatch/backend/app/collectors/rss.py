"""RSS/Atom collector. Reads data/feeds.yaml, polite conditional GETs, dedup, language detection."""
import calendar
import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import feedparser
import yaml

from .. import config, db, http
from ..processing import text
from .base import Collector, register

log = logging.getLogger("netwatch.rss")


def load_yaml(name: str):
    p = config.DATA_DIR / name
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def sync_feeds() -> int:
    """Mirror feeds.yaml into the DB (keeps status of known feeds)."""
    cfg = load_yaml("feeds.yaml") or {}
    n = 0
    with db.session() as con:
        for f in cfg.get("feeds", []):
            fid = f.get("id") or hashlib.sha1(f["url"].encode()).hexdigest()[:10]
            con.execute("""INSERT INTO feeds(id,source_id,url,lang,country,category) VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET source_id=excluded.source_id,url=excluded.url,lang=excluded.lang,
                country=excluded.country,category=excluded.category""",
                        (fid, f.get("source"), f["url"], f.get("lang"), f.get("country"), f.get("category")))
            n += 1
    return n


def _entry_time(e) -> str:
    for k in ("published_parsed", "updated_parsed"):
        t = getattr(e, k, None) or e.get(k) if hasattr(e, "get") else None
        if t:
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(min(calendar.timegm(t), time.time())))
    return db.now()


def parse_and_store(feed: dict, content: bytes) -> int:
    parsed = feedparser.parse(content)
    new = 0
    with db.session() as con:
        for e in parsed.entries[:80]:
            url = (e.get("link") or "").strip()
            title = text.clean_html(e.get("title"))
            if not url or not title:
                continue
            summary = text.clean_html(e.get("summary") or e.get("description"))[:1200]
            th = text.title_hash(title)
            # duplicate = same URL (UNIQUE) or same normalised title from the same source in the last 7 days
            if con.execute("SELECT 1 FROM articles WHERE source_id=? AND title_hash=? AND fetched_at>?",
                           (feed["source_id"], th, db.ts_ago(7 * 86400))).fetchone():
                continue
            lang = feed["lang"] or text.detect_lang(f"{title}. {summary}")
            cur = con.execute("""INSERT OR IGNORE INTO articles(source_id,feed_id,url,title,summary,lang,country,
                published_at,fetched_at,title_hash) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                              (feed["source_id"], feed["id"], url, title, summary, lang, feed["country"],
                               _entry_time(e), db.now(), th))
            new += cur.rowcount
    return new


def fetch_feed(feed: dict) -> int:
    headers = {}
    if feed.get("etag"):
        headers["If-None-Match"] = feed["etag"]
    if feed.get("modified"):
        headers["If-Modified-Since"] = feed["modified"]
    try:
        r = http.get(feed["url"], headers=headers, retries=2, timeout=20)
        if r.status_code == 304:
            db.execute("UPDATE feeds SET last_ok=?,status='ok',fail_count=0 WHERE id=?", (db.now(), feed["id"]))
            return 0
        r.raise_for_status()
        n = parse_and_store(feed, r.content)
        db.execute("UPDATE feeds SET last_ok=?,status='ok',fail_count=0,last_error=NULL,etag=?,modified=? WHERE id=?",
                   (db.now(), r.headers.get("etag"), r.headers.get("last-modified"), feed["id"]))
        return n
    except Exception as e:  # noqa: BLE001
        fc = (feed.get("fail_count") or 0) + 1
        db.execute("UPDATE feeds SET last_error=?,fail_count=?,status=? WHERE id=?",
                   (f"{type(e).__name__}: {e}"[:300], fc, "dead" if fc >= 5 else "error", feed["id"]))
        return 0


def collect() -> int:
    sync_feeds()
    feeds = db.rows("SELECT * FROM feeds WHERE status!='dead' OR (fail_count<20 AND last_ok IS NULL)")
    total = 0
    # hosts are rate-limited inside http.get; a small pool hides latency across hosts
    with ThreadPoolExecutor(max_workers=6) as ex:
        for n in ex.map(fetch_feed, feeds):
            total += n
    db.set_state("last_rss_collect", db.now())
    return total


def check_all() -> list[dict]:
    """Installation-time check: test every feed, mark dead ones (replacement can be set in the Sources screen)."""
    sync_feeds()
    out = []
    for f in db.rows("SELECT * FROM feeds"):
        try:
            r = http.get(f["url"], retries=1, timeout=15)
            d = feedparser.parse(r.content)
            ok = r.status_code < 400 and len(d.entries) > 0
            err = None if ok else f"HTTP {r.status_code}, {len(d.entries)} entries"
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"{type(e).__name__}: {e}"
        db.execute("UPDATE feeds SET status=?,last_error=?,last_ok=CASE WHEN ? THEN ? ELSE last_ok END WHERE id=?",
                   ("ok" if ok else "dead", err, ok, db.now(), f["id"]))
        out.append(dict(id=f["id"], url=f["url"], ok=ok, error=err))
    return out


register(Collector("rss", "rss", 30, collect))
