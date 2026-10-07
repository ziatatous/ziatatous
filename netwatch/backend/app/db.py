"""SQLite access layer (WAL, FTS5). One short-lived connection per call: thread safe."""
import json
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
  id TEXT PRIMARY KEY, name TEXT, country TEXT, languages TEXT, type TEXT,
  ownership_type TEXT, state_affiliated INTEGER DEFAULT 0, homepage TEXT,
  data TEXT, completeness REAL DEFAULT 0, verified_at TEXT);
CREATE TABLE IF NOT EXISTS feeds(
  id TEXT PRIMARY KEY, source_id TEXT, url TEXT, lang TEXT, country TEXT, category TEXT,
  status TEXT DEFAULT 'new', last_ok TEXT, last_error TEXT, etag TEXT, modified TEXT,
  fail_count INTEGER DEFAULT 0, replacement TEXT);
CREATE TABLE IF NOT EXISTS articles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, feed_id TEXT, url TEXT UNIQUE,
  title TEXT, summary TEXT, lang TEXT, country TEXT, published_at TEXT, fetched_at TEXT,
  full_text TEXT, title_hash TEXT, cluster_id INTEGER, entities TEXT, read INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_art_pub ON articles(published_at);
CREATE INDEX IF NOT EXISTS ix_art_cluster ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS ix_art_source ON articles(source_id);
CREATE INDEX IF NOT EXISTS ix_art_hash ON articles(title_hash);
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
  title, summary, full_text, content='articles', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS art_ai AFTER INSERT ON articles BEGIN
  INSERT INTO articles_fts(rowid,title,summary,full_text) VALUES (new.id,new.title,new.summary,new.full_text);
END;
CREATE TRIGGER IF NOT EXISTS art_ad AFTER DELETE ON articles BEGIN
  INSERT INTO articles_fts(articles_fts,rowid,title,summary,full_text) VALUES('delete',old.id,old.title,old.summary,old.full_text);
END;
CREATE TRIGGER IF NOT EXISTS art_au AFTER UPDATE OF title, summary, full_text ON articles BEGIN
  INSERT INTO articles_fts(articles_fts,rowid,title,summary,full_text) VALUES('delete',old.id,old.title,old.summary,old.full_text);
  INSERT INTO articles_fts(rowid,title,summary,full_text) VALUES (new.id,new.title,new.summary,new.full_text);
END;
CREATE TABLE IF NOT EXISTS clusters(
  id INTEGER PRIMARY KEY AUTOINCREMENT, label_article_id INTEGER, first_seen TEXT, last_seen TEXT,
  n_articles INTEGER DEFAULT 0, n_sources INTEGER DEFAULT 0, n_countries INTEGER DEFAULT 0,
  n_langs INTEGER DEFAULT 0, score REAL DEFAULT 0, centroid TEXT);
CREATE TABLE IF NOT EXISTS collector_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, collector TEXT, family TEXT, started TEXT, finished TEXT,
  ok INTEGER, items INTEGER, error TEXT);
CREATE INDEX IF NOT EXISTS ix_runs ON collector_runs(collector, started);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT UNIQUE, kind TEXT, ts TEXT, country TEXT,
  lat REAL, lon REAL, magnitude REAL, title TEXT, url TEXT, source TEXT, payload TEXT);
CREATE INDEX IF NOT EXISTS ix_ev ON events(kind, ts);
CREATE TABLE IF NOT EXISTS indicators(
  series TEXT, ts TEXT, value REAL, PRIMARY KEY(series, ts));
CREATE TABLE IF NOT EXISTS indicator_meta(
  series TEXT PRIMARY KEY, label TEXT, unit TEXT, group_name TEXT, source TEXT, source_url TEXT,
  updated TEXT, alert_above REAL, alert_below REAL, alert_move_pct REAL);
CREATE TABLE IF NOT EXISTS official_docs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT UNIQUE, origin TEXT, ts TEXT, title TEXT, url TEXT,
  summary TEXT, themes TEXT, country TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS official_fts USING fts5(
  title, summary, content='official_docs', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS off_ai AFTER INSERT ON official_docs BEGIN
  INSERT INTO official_fts(rowid,title,summary) VALUES (new.id,new.title,new.summary);
END;
CREATE TABLE IF NOT EXISTS agenda(
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT UNIQUE, date TEXT, kind TEXT, title TEXT,
  country TEXT, url TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS alert_rules(
  id TEXT PRIMARY KEY, name TEXT, kind TEXT, params TEXT, level TEXT, enabled INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, dedupe TEXT UNIQUE, level TEXT, rule_id TEXT, title TEXT,
  detail TEXT, created TEXT, read INTEGER DEFAULT 0, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS watchlist(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, value TEXT, UNIQUE(kind, value));
CREATE TABLE IF NOT EXISTS vocab(
  id INTEGER PRIMARY KEY AUTOINCREMENT, lang TEXT, word TEXT, translation TEXT, context TEXT,
  article_id INTEGER, ease REAL DEFAULT 2.5, interval INTEGER DEFAULT 0, reps INTEGER DEFAULT 0,
  due TEXT, created TEXT, UNIQUE(lang, word));
CREATE TABLE IF NOT EXISTS reading_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, lang TEXT, seconds INTEGER, ts TEXT);
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS companies(
  id TEXT PRIMARY KEY, name TEXT, ticker TEXT, sector TEXT, country TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS company_facts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT, kind TEXT, ts TEXT, label TEXT,
  value REAL, url TEXT NOT NULL, payload TEXT, UNIQUE(company_id, kind, label, ts));
CREATE TABLE IF NOT EXISTS graph_nodes(
  id TEXT PRIMARY KEY, label TEXT, type TEXT, country TEXT, wikidata TEXT);
CREATE TABLE IF NOT EXISTS graph_edges(
  id INTEGER PRIMARY KEY AUTOINCREMENT, src TEXT, dst TEXT, rel TEXT, weight REAL DEFAULT 1,
  source_url TEXT NOT NULL CHECK(length(source_url) > 0), label TEXT,
  UNIQUE(src, dst, rel));
CREATE INDEX IF NOT EXISTS ix_ge_src ON graph_edges(src);
CREATE INDEX IF NOT EXISTS ix_ge_dst ON graph_edges(dst);
"""


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ts_ago(seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def session():
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init() -> None:
    with session() as con:
        con.execute("DROP TRIGGER IF EXISTS art_au")  # migrate: old version re-indexed text on every cluster_id/read update
        con.executescript(SCHEMA)


def rows(sql: str, args=()) -> list[dict]:
    with session() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def one(sql: str, args=()) -> dict | None:
    r = rows(sql, args)
    return r[0] if r else None


def execute(sql: str, args=()) -> int:
    with session() as con:
        return con.execute(sql, args).rowcount


def get_state(key: str, default=None):
    r = one("SELECT value FROM state WHERE key=?", (key,))
    return json.loads(r["value"]) if r else default


def set_state(key: str, value) -> None:
    execute("INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)))
