"""Periodic post-processing, retention policy, backup."""
import json
import logging
import shutil
import time

from .. import config, db
from . import alerts, cluster, text

log = logging.getLogger("netwatch.maint")


def periodic() -> None:
    for step in (enrich_entities, cluster.run, alerts.evaluate):
        try:
            step()
        except Exception as e:  # noqa: BLE001
            log.warning("maintenance step %s failed: %s", step.__name__, e)


def gazetteer() -> list[str]:
    g = [w["value"] for w in db.rows("SELECT value FROM watchlist")]
    g += [c["name"] for c in db.rows("SELECT name FROM companies")]
    return g


def enrich_entities(limit: int = 800) -> int:
    gz = gazetteer()
    todo = db.rows("SELECT id,title,summary FROM articles WHERE entities IS NULL ORDER BY id DESC LIMIT ?", (limit,))
    with db.session() as con:
        for a in todo:
            ents = text.extract_entities(f"{a['title']}. {a['summary'] or ''}", gz)
            con.execute("UPDATE articles SET entities=? WHERE id=?", (json.dumps(ents, ensure_ascii=False), a["id"]))
    return len(todo)


def retention() -> None:
    db.execute("UPDATE articles SET full_text=NULL WHERE full_text IS NOT NULL AND fetched_at<?",
               (db.ts_ago(config.RETENTION_FULLTEXT_DAYS * 86400),))
    db.execute("DELETE FROM articles WHERE fetched_at<?", (db.ts_ago(config.RETENTION_META_DAYS * 86400),))
    db.execute("DELETE FROM events WHERE ts<?", (db.ts_ago(config.RETENTION_META_DAYS * 86400),))
    db.execute("DELETE FROM collector_runs WHERE started<?", (db.ts_ago(60 * 86400),))
    cluster.refresh_stats()
    with db.session() as con:
        con.execute("INSERT INTO articles_fts(articles_fts) VALUES('optimize')")
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def export_settings() -> dict:
    """User-authored data: watchlist, vocabulary, corrected sources, alert rules, state."""
    t = lambda sql: db.rows(sql)  # noqa: E731
    return dict(version=1, exported=db.now(), watchlist=t("SELECT kind,value FROM watchlist"),
                vocab=t("SELECT lang,word,translation,context,ease,interval,reps,due,created FROM vocab"),
                alert_rules=t("SELECT * FROM alert_rules"), state=t("SELECT * FROM state"),
                sources=t("SELECT id,data FROM sources"), reading_log=t("SELECT lang,seconds,ts FROM reading_log"))


def import_settings(d: dict) -> dict:
    n = 0
    with db.session() as con:
        for w in d.get("watchlist", []):
            n += con.execute("INSERT OR IGNORE INTO watchlist(kind,value) VALUES(?,?)", (w["kind"], w["value"])).rowcount
        for v in d.get("vocab", []):
            n += con.execute("INSERT OR IGNORE INTO vocab(lang,word,translation,context,ease,interval,reps,due,created) "
                             "VALUES(?,?,?,?,?,?,?,?,?)", (v["lang"], v["word"], v["translation"], v["context"], v["ease"],
                                                          v["interval"], v["reps"], v["due"], v["created"])).rowcount
        for r in d.get("alert_rules", []):
            con.execute("INSERT OR REPLACE INTO alert_rules(id,name,kind,params,level,enabled) VALUES(?,?,?,?,?,?)",
                        (r["id"], r["name"], r["kind"], r["params"], r["level"], r["enabled"]))
        for s in d.get("state", []):
            con.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (s["key"], s["value"]))
        for s in d.get("sources", []):
            con.execute("UPDATE sources SET data=? WHERE id=?", (s["data"], s["id"]))
        for r in d.get("reading_log", []):
            con.execute("INSERT INTO reading_log(lang,seconds,ts) VALUES(?,?,?)", (r["lang"], r["seconds"], r["ts"]))
    return dict(imported=n)


def backup_db() -> str:
    out = config.BASE / "backups"
    out.mkdir(exist_ok=True)
    dest = out / f"netwatch-{time.strftime('%Y%m%d-%H%M%S')}.db"
    with db.session() as con:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    shutil.copy2(config.DB_PATH, dest)
    return str(dest)
