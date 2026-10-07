"""REST API. Everything the frontend needs; nothing is generated: only stored data + statistics."""
import json
import re
import time
from collections import Counter, defaultdict, deque

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from .. import config, db
from ..collectors import base, markets, rss, sources_loader
from ..countries import COUNTRIES
from ..processing import alerts as alerts_mod
from ..processing import cluster, compare, maintenance, sm2, text, translate

router = APIRouter(prefix="/api")


def _j(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:  # noqa: BLE001
        return default


# ---------------------------------------------------------------- system
@router.get("/health")
def health():
    return dict(ok=True, time=db.now(), version="0.1.0", name="NETWATCH")


@router.get("/events/stream")
async def sse():
    from . import bus
    return StreamingResponse(bus.stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/system")
def system():
    size = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    feeds = db.rows("SELECT status, COUNT(*) n FROM feeds GROUP BY status")
    counts = {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in
              ("articles", "clusters", "events", "sources", "official_docs", "companies", "graph_edges", "vocab")}
    return dict(db_bytes=size, db_path=str(config.DB_PATH), collectors=base.status(), feeds=feeds, counts=counts,
                retention=dict(fulltext_days=config.RETENTION_FULLTEXT_DAYS, meta_days=config.RETENTION_META_DAYS),
                translation=translate.available(), cluster_mode=config.CLUSTER_MODE,
                keys={k: bool(config.key(k)) for k in ("ACLED_KEY", "FRED_API_KEY", "OPENSANCTIONS_KEY", "DEEPL_API_KEY",
                                                       "RELIEFWEB_APPNAME", "LDA_API_KEY")})


@router.post("/system/collect")
def collect_now(name: str | None = None):
    if name and name not in base.REGISTRY:
        raise HTTPException(404, "unknown collector")
    base.run_async([name] if name else None)
    return dict(started=name or "all")


@router.get("/system/feeds")
def feeds_status():
    return db.rows("SELECT f.*, s.name source_name FROM feeds f LEFT JOIN sources s ON s.id=f.source_id ORDER BY f.status DESC, f.id")


@router.post("/system/feeds/check")
def feeds_check():
    import threading
    threading.Thread(target=rss.check_all, daemon=True).start()
    return dict(started=True)


@router.put("/system/feeds/{fid}")
def feed_update(fid: str, body: dict = Body(...)):
    if "replacement" in body or "url" in body:
        db.execute("UPDATE feeds SET url=COALESCE(?,url), replacement=?, status='new', fail_count=0 WHERE id=?",
                   (body.get("url"), body.get("replacement"), fid))
    return dict(ok=True)


@router.get("/startup")
def startup():
    """Real system state for the boot sequence."""
    last_visit = db.get_state("last_visit")
    cols = base.status()
    fam: dict[str, str | None] = {}
    for c in cols:
        if c["last_success"] and (fam.get(c["family"]) is None or c["last_success"] > fam[c["family"]]):
            fam[c["family"]] = c["last_success"]
        fam.setdefault(c["family"], None)
    feed_counts = {r["status"]: r["n"] for r in db.rows("SELECT status, COUNT(*) n FROM feeds GROUP BY status")}
    new_articles = db.one("SELECT COUNT(*) n FROM articles WHERE fetched_at>?", (last_visit or "0",))["n"]
    lv = {r["level"]: r["n"] for r in db.rows("SELECT level, COUNT(*) n FROM alerts WHERE active=1 GROUP BY level")}
    return dict(last_visit=last_visit, feeds=feed_counts, new_articles=new_articles, alerts=lv, last_collect=fam,
                collectors_failing=[c["name"] for c in cols if c["last_run"] and not c["last_run"]["ok"]])


# ---------------------------------------------------------------- settings / backup
@router.get("/settings/{key}")
def get_setting(key: str):
    return dict(value=db.get_state("setting:" + key))


@router.put("/settings/{key}")
def put_setting(key: str, body: dict = Body(...)):
    db.set_state("setting:" + key, body.get("value"))
    return dict(ok=True)


@router.get("/backup/export")
def backup_export():
    return JSONResponse(maintenance.export_settings(),
                        headers={"Content-Disposition": f"attachment; filename=netwatch-settings-{time.strftime('%Y%m%d')}.json"})


@router.post("/backup/import")
def backup_import(body: dict = Body(...)):
    return maintenance.import_settings(body)


@router.post("/backup/db")
def backup_db():
    return dict(path=maintenance.backup_db())


# ---------------------------------------------------------------- articles & search
ART_COLS = """a.id,a.title,a.summary,a.url,a.lang,a.country,a.published_at,a.source_id,a.cluster_id,a.read,
 s.name source_name, s.ownership_type, s.type source_type, s.state_affiliated"""


def _fts_query(q: str) -> str:
    toks = re.findall(r"[\w'-]+", q, re.U)
    return " ".join(f'"{t}"*' if len(t) > 2 else f'"{t}"' for t in toks)


@router.get("/articles")
def articles(q: str | None = None, lang: str | None = None, country: str | None = None, source: str | None = None,
             ownership: str | None = None, since: str | None = None, until: str | None = None, cluster: int | None = None,
             limit: int = Query(50, le=200), offset: int = 0):
    where, args = [], []
    join = ""
    if q:
        join = "JOIN articles_fts f ON f.rowid=a.id"
        where.append("articles_fts MATCH ?")
        args.append(_fts_query(q))
    for col, v in (("a.lang", lang), ("a.country", country), ("a.source_id", source), ("s.ownership_type", ownership),
                   ("a.cluster_id", cluster)):
        if v is not None:
            where.append(f"{col}=?")
            args.append(v)
    if since:
        where.append("a.published_at>=?"); args.append(since)
    if until:
        where.append("a.published_at<=?"); args.append(until)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    order = "ORDER BY rank" if q else "ORDER BY a.published_at DESC"
    items = db.rows(f"SELECT {ART_COLS} FROM articles a {join} LEFT JOIN sources s ON s.id=a.source_id {w} {order} LIMIT ? OFFSET ?",
                    (*args, limit, offset))
    total = db.one(f"SELECT COUNT(*) n FROM articles a {join} LEFT JOIN sources s ON s.id=a.source_id {w}", args)["n"]
    return dict(items=items, total=total)


@router.get("/articles/{aid}")
def article(aid: int):
    a = db.one(f"SELECT {ART_COLS}, a.full_text, a.entities FROM articles a LEFT JOIN sources s ON s.id=a.source_id WHERE a.id=?", (aid,))
    if not a:
        raise HTTPException(404)
    a["entities"] = _j(a["entities"], [])
    db.execute("UPDATE articles SET read=1 WHERE id=?", (aid,))
    return a


@router.post("/articles/{aid}/fulltext")
def article_fulltext(aid: int):
    """Local, personal extraction for reading/learning. Respects robots.txt, never bypasses paywalls."""
    from .. import http
    a = db.one("SELECT id,url,full_text FROM articles WHERE id=?", (aid,))
    if not a:
        raise HTTPException(404)
    if a["full_text"]:
        return dict(text=a["full_text"], cached=True)
    if not http.allowed_by_robots(a["url"]):
        raise HTTPException(403, "robots.txt disallows fetching this page; open the original link instead")
    import trafilatura
    r = http.get(a["url"], retries=1)
    txt = trafilatura.extract(r.text, include_comments=False, include_tables=False) if r.status_code == 200 else None
    if not txt:
        raise HTTPException(422, "no extractable text (paywall or dynamic page): open the original link")
    db.execute("UPDATE articles SET full_text=? WHERE id=?", (txt, aid))
    return dict(text=txt, cached=False)


@router.post("/translate")
def translate_text(body: dict = Body(...)):
    try:
        out = translate.translate(body["text"], body["src"], body["dst"])
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return dict(out, label="machine translation")


@router.post("/translate/bilingual")
def bilingual(body: dict = Body(...)):
    sents = text.sentences(body["text"])[:80]
    try:
        out = [translate.translate(s, body["src"], body["dst"])["text"] for s in sents]
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return dict(pairs=list(zip(sents, out)), label="machine translation")


@router.get("/facets")
def facets():
    return dict(langs=db.rows("SELECT lang v, COUNT(*) n FROM articles WHERE lang IS NOT NULL GROUP BY lang ORDER BY n DESC"),
                countries=db.rows("SELECT country v, COUNT(*) n FROM articles WHERE country IS NOT NULL GROUP BY country ORDER BY n DESC"),
                ownership=db.rows("SELECT s.ownership_type v, COUNT(*) n FROM articles a JOIN sources s ON s.id=a.source_id GROUP BY 1 ORDER BY n DESC"),
                sources=db.rows("SELECT a.source_id v, s.name label, COUNT(*) n FROM articles a LEFT JOIN sources s ON s.id=a.source_id GROUP BY 1 ORDER BY n DESC LIMIT 300"))


# ---------------------------------------------------------------- clusters / briefing
def _cluster_rows(where="", args=(), order="c.score DESC", limit=30):
    rows = db.rows(f"""SELECT c.*, a.title, a.url, a.lang title_lang, a.source_id label_source, s.name label_source_name
        FROM clusters c LEFT JOIN articles a ON a.id=c.label_article_id LEFT JOIN sources s ON s.id=a.source_id
        {where} ORDER BY {order} LIMIT ?""", (*args, limit))
    for c in rows:
        info = db.rows("SELECT DISTINCT country, lang FROM articles WHERE cluster_id=?", (c["id"],))
        c["countries"] = sorted({i["country"] for i in info if i["country"]})
        c["langs"] = sorted({i["lang"] for i in info if i["lang"]})
        c.pop("centroid", None)
    return rows


@router.get("/clusters")
def clusters(hours: int = 48, limit: int = 30, country: str | None = None, q: str | None = None):
    where, args = "WHERE c.last_seen>=? AND c.n_sources>=2", [db.ts_ago(hours * 3600)]
    if country:
        where += " AND c.id IN (SELECT cluster_id FROM articles WHERE country=?)"
        args.append(country)
    if q:
        where += " AND c.id IN (SELECT cluster_id FROM articles WHERE id IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?))"
        args.append(_fts_query(q))
    return _cluster_rows(where, args, limit=limit)


@router.get("/clusters/{cid}")
def cluster_detail(cid: int, by: str = "country"):
    v = compare.cluster_view(cid, by)
    if not v:
        raise HTTPException(404)
    # primary source: official documents sharing rare terms with the cluster headline
    lab = db.one("SELECT title FROM articles WHERE id=?", (v["cluster"]["label_article_id"],))
    prim = []
    if lab:
        toks = [t for t in text.tokens(lab["title"]) if len(t) > 4][:4]
        if toks:
            prim = db.rows("""SELECT id,origin,ts,title,url FROM official_docs WHERE id IN
                (SELECT rowid FROM official_fts WHERE official_fts MATCH ?) ORDER BY ts DESC LIMIT 5""", (" OR ".join(f'"{t}"' for t in toks),))
    v["primary_sources"] = prim
    return v


@router.get("/briefing")
def briefing(hours: int = 36):
    last = db.get_state("last_visit")
    since = last or db.ts_ago(24 * 3600)
    counters = dict(
        by_country=db.rows("SELECT country v, COUNT(*) n FROM articles WHERE fetched_at>? AND country IS NOT NULL GROUP BY country ORDER BY n DESC LIMIT 12", (since,)),
        by_lang=db.rows("SELECT lang v, COUNT(*) n FROM articles WHERE fetched_at>? AND lang IS NOT NULL GROUP BY lang ORDER BY n DESC LIMIT 12", (since,)),
        total=db.one("SELECT COUNT(*) n FROM articles WHERE fetched_at>?", (since,))["n"],
        official=db.one("SELECT COUNT(*) n FROM official_docs WHERE ts>?", (since,))["n"],
        alerts=db.one("SELECT COUNT(*) n FROM alerts WHERE created>?", (since,))["n"])
    ws = []
    for w in cluster.weak_signals():
        c = _cluster_rows("WHERE c.id=?", (w["cluster_id"],), limit=1)
        if c:
            ws.append(dict(w, cluster=c[0]))
    official = db.rows("SELECT id,origin,ts,title,url,themes FROM official_docs ORDER BY ts DESC LIMIT 12")
    for o in official:
        o["themes"] = _j(o["themes"], [])
    return dict(since=since, last_visit=last, counters=counters,
                topics=_cluster_rows("WHERE c.last_seen>=? AND c.n_sources>=2", (db.ts_ago(hours * 3600),), limit=12),
                weak_signals=ws, official=official, vitals=vitals_strip(), agenda=agenda(72))


@router.post("/briefing/mark-read")
def mark_read():
    db.set_state("last_visit", db.now())
    return dict(ok=True)


@router.get("/timeline")
def timeline(topic: str, days: int = 30):
    since = db.ts_ago(days * 86400)
    arts = db.rows("""SELECT a.id,a.title,a.url,a.country,a.lang,a.published_at ts,a.source_id,s.name source_name FROM articles a
        LEFT JOIN sources s ON s.id=a.source_id WHERE a.published_at>=? AND a.id IN
        (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?) ORDER BY a.published_at""", (since, _fts_query(topic)))
    off = db.rows("""SELECT id,origin,ts,title,url FROM official_docs WHERE ts>=? AND id IN
        (SELECT rowid FROM official_fts WHERE official_fts MATCH ?) ORDER BY ts""", (since, _fts_query(topic)))
    al = db.rows("SELECT id,level,title,created ts FROM alerts WHERE created>=? AND title LIKE ?", (since, f"%{topic}%"))
    by_day = Counter(a["ts"][:10] for a in arts)
    return dict(topic=topic, articles=arts, official=off, alerts=al, by_day=sorted(by_day.items()))


# ---------------------------------------------------------------- sources
@router.get("/sources")
def sources(q: str | None = None, country: str | None = None, type: str | None = None):
    where, args = [], []
    if q:
        where.append("name LIKE ?"); args.append(f"%{q}%")
    if country:
        where.append("country=?"); args.append(country)
    if type:
        where.append("type=?"); args.append(type)
    rows = db.rows(f"SELECT id,name,country,languages,type,ownership_type,state_affiliated,homepage,completeness,verified_at FROM sources "
                   f"{'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY name", args)
    counts = {r["source_id"]: r["n"] for r in db.rows("SELECT source_id, COUNT(*) n FROM articles GROUP BY source_id")}
    for r in rows:
        r["languages"] = _j(r["languages"], [])
        r["articles"] = counts.get(r["id"], 0)
    return rows


@router.get("/sources/{sid}")
def source(sid: str):
    s = db.one("SELECT * FROM sources WHERE id=?", (sid,))
    if not s:
        raise HTTPException(404)
    data = _j(s["data"], {})
    stats = dict(
        per_day=db.rows("SELECT substr(published_at,1,10) d, COUNT(*) n FROM articles WHERE source_id=? AND published_at>=? GROUP BY d ORDER BY d",
                        (sid, db.ts_ago(30 * 86400))),
        total=db.one("SELECT COUNT(*) n FROM articles WHERE source_id=?", (sid,))["n"],
        categories=db.rows("SELECT category v, COUNT(*) n FROM feeds f JOIN articles a ON a.feed_id=f.id WHERE a.source_id=? GROUP BY category", (sid,)),
        top_entities=_top_entities(sid))
    # blind spots: big clusters (>=4 sources, 14d) this source did not cover, vs. the median source
    big = db.rows("SELECT id FROM clusters WHERE n_sources>=4 AND last_seen>=?", (db.ts_ago(14 * 86400),))
    if big:
        ids = [b["id"] for b in big]
        marks = ",".join("?" * len(ids))
        per_src = {r["source_id"]: r["n"] for r in db.rows(f"SELECT source_id, COUNT(DISTINCT cluster_id) n FROM articles WHERE cluster_id IN ({marks}) GROUP BY source_id", ids)}
        vals = sorted(per_src.values())
        stats["big_story_coverage"] = dict(covered=per_src.get(sid, 0), of=len(ids), median_source=vals[len(vals) // 2] if vals else 0)
    rsf = None
    if s["country"]:
        rk = db.one("SELECT ts,value FROM indicators WHERE series=? ORDER BY ts DESC LIMIT 1", (f"RSF:{s['country']}:rank",))
        sc = db.one("SELECT ts,value FROM indicators WHERE series=? ORDER BY ts DESC LIMIT 1", (f"RSF:{s['country']}:score",))
        if rk or sc:
            rsf = dict(rank=rk and rk["value"], score=sc and sc["value"], year=(rk or sc)["ts"][:4], ref="https://rsf.org/en/index")
    feeds = db.rows("SELECT id,url,lang,category,status,last_ok FROM feeds WHERE source_id=?", (sid,))
    owns = db.rows("""SELECT n.id, n.label, n.type FROM graph_edges e JOIN graph_nodes n ON n.id=e.dst
                      WHERE e.rel='owns' AND e.src IN (SELECT src FROM graph_edges WHERE dst=? AND rel='owns')""", ("media:" + sid,))
    return dict(id=s["id"], name=s["name"], country=s["country"], data=data, completeness=s["completeness"],
                verified_at=s["verified_at"], stats=stats, rsf=rsf, feeds=feeds, sibling_assets=owns,
                missing=[k for k, f in sources_loader.CHECKS.items() if not f(data)])


def _top_entities(sid: str):
    c: Counter = Counter()
    for r in db.rows("SELECT entities FROM articles WHERE source_id=? AND entities IS NOT NULL ORDER BY id DESC LIMIT 400", (sid,)):
        c.update(_j(r["entities"], []))
    return [dict(entity=e, count=n) for e, n in c.most_common(12)]


@router.put("/sources/{sid}")
def source_put(sid: str, body: dict = Body(...)):
    """Add or correct a source fiche (stored as user-edited so YAML reloads never overwrite it)."""
    body["id"] = sid
    body["_user_edited"] = True
    db.execute("""INSERT INTO sources(id,name,country,languages,type,ownership_type,state_affiliated,homepage,data,completeness,verified_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,country=excluded.country,languages=excluded.languages,
        type=excluded.type,ownership_type=excluded.ownership_type,state_affiliated=excluded.state_affiliated,homepage=excluded.homepage,
        data=excluded.data,completeness=excluded.completeness,verified_at=excluded.verified_at""",
               (sid, body.get("name", sid), body.get("country"), json.dumps(body.get("languages", [])), body.get("type"),
                (body.get("ownership") or {}).get("type", "unknown"), 1 if (body.get("state_affiliated") or {}).get("value") else 0,
                body.get("homepage"), json.dumps(body, ensure_ascii=False), sources_loader.completeness(body),
                sources_loader.newest_verification(body)))
    sources_loader.build_graph()
    return dict(ok=True, completeness=sources_loader.completeness(body))


@router.post("/sources/{sid}/reverify")
def source_reverify(sid: str):
    from ..collectors import wikidata
    try:
        return wikidata.reverify_source(sid)
    except KeyError:
        raise HTTPException(404)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


# ---------------------------------------------------------------- world
@router.get("/world/events")
def world_events(kind: str | None = None, days: int = 7, limit: int = 3000):
    where, args = ["ts>=?"], [db.ts_ago(days * 86400)]
    if kind:
        where.append("kind=?"); args.append(kind)
    rows = db.rows(f"SELECT id,uid,kind,ts,country,lat,lon,magnitude,title,url,source,payload FROM events WHERE {' AND '.join(where)} "
                   f"AND lat IS NOT NULL ORDER BY ts DESC LIMIT ?", (*args, limit))
    for r in rows:
        r["payload"] = _j(r["payload"], {})
    return rows


@router.get("/world/heat")
def world_heat(days: int = 7):
    """Per-country intensity, weighted by event kind (GDELT counts are damped with log)."""
    import math
    agg: dict[str, dict] = {}
    for r in db.rows("SELECT country,kind,source,COUNT(*) n, SUM(magnitude) m FROM events WHERE ts>=? AND country IS NOT NULL GROUP BY country,kind,source",
                     (db.ts_ago(days * 86400),)):
        c = COUNTRIES.get(r["country"])
        if not c:
            continue
        w = math.log1p(r["m"] or r["n"]) if r["source"] == "GDELT" else math.log1p((r["m"] or 0) + r["n"])
        a = agg.setdefault(r["country"], dict(country=r["country"], lat=c["lat"], lon=c["lon"], intensity=0.0, kinds=Counter()))
        a["intensity"] += w
        a["kinds"][r["kind"]] += w
    out = []
    for a in agg.values():
        a["kind"] = a["kinds"].most_common(1)[0][0]
        a["kinds"] = {k: round(v, 2) for k, v in a["kinds"].items()}
        a["intensity"] = round(a["intensity"], 2)
        out.append(a)
    return sorted(out, key=lambda x: -x["intensity"])


@router.get("/world/arcs")
def world_arcs(days: int = 1):
    """Bilateral relations of the day: GDELT does not give pairs at our aggregation level, so arcs come from
    sanctions/official documents naming two tracked countries (each arc links to its document)."""
    names = {c["name"]: k for k, c in COUNTRIES.items()}
    arcs = []
    for d in db.rows("SELECT title,url,origin,country FROM official_docs WHERE ts>=? LIMIT 400", (db.ts_ago(days * 86400 * 3),)):
        found = [k for n, k in names.items() if re.search(rf"\b{re.escape(n)}\b", d["title"] or "")]
        if d["country"] in COUNTRIES and d["country"] not in found:
            found.append(d["country"])
        if len(found) >= 2:
            a, b = COUNTRIES[found[0]], COUNTRIES[found[1]]
            arcs.append(dict(from_=found[0], to=found[1], slat=a["lat"], slon=a["lon"], elat=b["lat"], elon=b["lon"],
                             title=d["title"], url=d["url"], origin=d["origin"]))
    return arcs


@router.get("/world/countries")
def world_countries():
    return list(COUNTRIES.values())


@router.get("/world/country/{code}")
def country_dossier(code: str):
    code = code.upper()
    c = COUNTRIES.get(code)
    if not c:
        raise HTTPException(404)
    srcs = db.rows("SELECT id,name,ownership_type,type FROM sources WHERE country=?", (code,))
    local = db.rows(f"SELECT {ART_COLS} FROM articles a LEFT JOIN sources s ON s.id=a.source_id WHERE a.country=? ORDER BY a.published_at DESC LIMIT 25", (code,))
    foreign = db.rows(f"""SELECT {ART_COLS} FROM articles a LEFT JOIN sources s ON s.id=a.source_id WHERE a.country!=? AND a.id IN
        (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?) ORDER BY a.published_at DESC LIMIT 25""", (code, f'"{c["name"]}"'))
    ev = db.rows("SELECT kind,ts,magnitude,title,url,source FROM events WHERE country=? AND ts>=? ORDER BY ts DESC LIMIT 40", (code, db.ts_ago(30 * 86400)))
    off = db.rows("""SELECT id,origin,ts,title,url FROM official_docs WHERE country=? OR id IN
        (SELECT rowid FROM official_fts WHERE official_fts MATCH ?) ORDER BY ts DESC LIMIT 15""", (code, f'"{c["name"]}"'))
    wb = db.rows("""SELECT m.series,m.label,m.unit,m.source,m.source_url,
        (SELECT value FROM indicators i WHERE i.series=m.series ORDER BY ts DESC LIMIT 1) value,
        (SELECT ts FROM indicators i WHERE i.series=m.series ORDER BY ts DESC LIMIT 1) ts
        FROM indicator_meta m WHERE m.series LIKE ?""", (f"WB:{_iso3(code)}:%",))
    comps = db.rows("SELECT id,name,sector FROM companies WHERE country=?", (code,))
    rsf = db.one("SELECT value FROM indicators WHERE series=? ORDER BY ts DESC LIMIT 1", (f"RSF:{code}:rank",))
    agenda_ = db.rows("SELECT date,kind,title,url FROM agenda WHERE country=? AND date>=? ORDER BY date LIMIT 10", (code, time.strftime("%Y-%m-%d")))
    leaders = [r for r in db.rows("SELECT label FROM graph_nodes WHERE country=? AND type='person' LIMIT 5", (code,))]
    return dict(country=c, local_sources=srcs, local_news=local, foreign_news=foreign, events=ev, official=off, indicators=wb,
                companies=comps, press_freedom_rank=rsf and rsf["value"], agenda=agenda_, people=leaders)


_ISO3 = {"FR": "FRA", "ES": "ESP", "DE": "DEU", "IT": "ITA", "US": "USA", "CN": "CHN", "GB": "GBR", "JP": "JPN", "BR": "BRA", "IN": "IND"}


def _iso3(code: str) -> str:
    return _ISO3.get(code, code)


# ---------------------------------------------------------------- vitals
def vitals_strip():
    ids = ["SPX", "NDX", "CAC", "DAX", "VIX", "GOLD", "BRENT", "TTF", "BTC", "EURUSD"]
    out = []
    for sid in ids:
        st = markets.series_stats(sid)
        m = db.one("SELECT * FROM indicator_meta WHERE series=?", (sid,))
        if st and m:
            out.append(dict(series=sid, label=m["label"], unit=m["unit"], value=st["last"]["value"], ts=st["last"]["ts"],
                            change_pct=st["change_pct"], source=m["source"], source_url=m["source_url"], updated=m["updated"]))
    return out


@router.get("/vitals")
def vitals():
    out = defaultdict(list)
    for m in db.rows("SELECT * FROM indicator_meta WHERE series NOT LIKE 'WB:%' AND series NOT LIKE 'CO:%' AND series NOT LIKE 'RSF%' ORDER BY group_name,label"):
        st = markets.series_stats(m["series"])
        if not st:
            continue
        spark = db.rows("SELECT ts,value FROM indicators WHERE series=? ORDER BY ts DESC LIMIT 90", (m["series"],))[::-1]
        out[m["group_name"]].append(dict(m, **st, spark=spark))
    return out


@router.get("/vitals/{series:path}")
def vital_series(series: str, days: int = 3650):
    m = db.one("SELECT * FROM indicator_meta WHERE series=?", (series,))
    if not m:
        raise HTTPException(404)
    pts = db.rows("SELECT ts,value FROM indicators WHERE series=? AND ts>=? ORDER BY ts", (series, db.ts_ago(days * 86400)[:10]))
    return dict(meta=m, points=pts, stats=markets.series_stats(series))


@router.put("/vitals-threshold/{series:path}")
def vital_threshold(series: str, body: dict = Body(...)):
    db.execute("UPDATE indicator_meta SET alert_above=?, alert_below=?, alert_move_pct=? WHERE series=?",
               (body.get("above"), body.get("below"), body.get("move_pct"), series))
    return dict(ok=True)


# ---------------------------------------------------------------- official / agenda / alerts
@router.get("/official")
def official(q: str | None = None, origin: str | None = None, theme: str | None = None, limit: int = 60, offset: int = 0):
    where, args, join = [], [], ""
    if q:
        join = "JOIN official_fts f ON f.rowid=o.id"
        where.append("official_fts MATCH ?"); args.append(_fts_query(q))
    if origin:
        where.append("o.origin LIKE ?"); args.append(origin + "%")
    if theme:
        where.append("o.themes LIKE ?"); args.append(f'%"{theme}"%')
    w = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.rows(f"SELECT o.* FROM official_docs o {join} {w} ORDER BY o.ts DESC LIMIT ? OFFSET ?", (*args, limit, offset))
    for r in rows:
        r["themes"] = _j(r["themes"], [])
    return rows


@router.get("/agenda")
def agenda(hours: int = 24 * 60, kind: str | None = None):
    end = time.strftime("%Y-%m-%d", time.gmtime(time.time() + hours * 3600))
    where, args = "date>=? AND date<=?", [time.strftime("%Y-%m-%d"), end]
    if kind:
        where += " AND kind=?"; args.append(kind)
    return db.rows(f"SELECT * FROM agenda WHERE {where} ORDER BY date LIMIT 400", args)


@router.get("/alerts")
def alerts_list(limit: int = 100, unread: bool = False):
    rows = db.rows(f"SELECT * FROM alerts {'WHERE read=0' if unread else ''} ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        r["detail"] = _j(r["detail"], {})
    return rows


@router.get("/alerts/active")
def alerts_active():
    rows = db.rows("SELECT id,level,title,created,rule_id FROM alerts WHERE active=1 AND read=0 ORDER BY id DESC LIMIT 20")
    return rows


@router.post("/alerts/{aid}/read")
def alert_read(aid: int):
    db.execute("UPDATE alerts SET read=1, active=0 WHERE id=?", (aid,))
    return dict(ok=True)


@router.post("/alerts/read-all")
def alert_read_all():
    db.execute("UPDATE alerts SET read=1, active=0")
    return dict(ok=True)


@router.post("/alerts/evaluate")
def alerts_eval():
    return dict(fired=alerts_mod.evaluate())


@router.get("/alert-rules")
def rules_list():
    rows = db.rows("SELECT * FROM alert_rules ORDER BY level, id")
    for r in rows:
        r["params"] = _j(r["params"], {})
    return rows


@router.put("/alert-rules/{rid}")
def rule_update(rid: str, body: dict = Body(...)):
    db.execute("UPDATE alert_rules SET params=COALESCE(?,params), level=COALESCE(?,level), enabled=COALESCE(?,enabled), name=COALESCE(?,name) WHERE id=?",
               (json.dumps(body["params"]) if "params" in body else None, body.get("level"), body.get("enabled"), body.get("name"), rid))
    return dict(ok=True)


# ---------------------------------------------------------------- watchlist
@router.get("/watchlist")
def wl_list():
    return db.rows("SELECT * FROM watchlist ORDER BY kind,value")


@router.post("/watchlist")
def wl_add(body: dict = Body(...)):
    db.execute("INSERT OR IGNORE INTO watchlist(kind,value) VALUES(?,?)", (body["kind"], body["value"].strip()))
    return dict(ok=True)


@router.delete("/watchlist/{wid}")
def wl_del(wid: int):
    db.execute("DELETE FROM watchlist WHERE id=?", (wid,))
    return dict(ok=True)


# ---------------------------------------------------------------- companies
@router.get("/companies")
def companies(sector: str | None = None):
    rows = db.rows("SELECT id,name,ticker,sector,country,data FROM companies " + ("WHERE sector=? " if sector else "") + "ORDER BY name",
                   (sector,) if sector else ())
    for c in rows:
        st = markets.series_stats("CO:" + c["id"])
        c["last"] = st.get("last") if st else None
        c["change_pct"] = st.get("change_pct") if st else None
        c.pop("data")
    return rows


@router.post("/companies")
def company_add(body: dict = Body(...)):
    cid = sources_loader.slug(body["name"])
    body["id"] = cid
    db.execute("INSERT OR REPLACE INTO companies(id,name,ticker,sector,country,data) VALUES(?,?,?,?,?,?)",
               (cid, body["name"], body.get("stooq"), body.get("sector"), body.get("country"), json.dumps(body)))
    return dict(id=cid)


@router.get("/companies/{cid}")
def company(cid: str):
    c = db.one("SELECT * FROM companies WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404)
    data = _j(c["data"], {})
    facts = db.rows("SELECT kind,ts,label,value,url,payload FROM company_facts WHERE company_id=? ORDER BY ts DESC", (cid,))
    by_kind: dict[str, list] = defaultdict(list)
    for f in facts:
        f["payload"] = _j(f["payload"], {})
        by_kind[f["kind"]].append(f)
    hist = db.rows("SELECT ts,value FROM indicators WHERE series=? ORDER BY ts", ("CO:" + cid,))
    idx = db.rows("SELECT ts,value FROM indicators WHERE series='SPX' ORDER BY ts")
    media = db.rows("SELECT n.id,n.label FROM graph_edges e JOIN graph_nodes n ON n.id=e.dst WHERE e.src=? AND e.rel='owns' AND n.type='media'", (f"co:{cid}",))
    subs = db.rows("SELECT n.id,n.label,n.type,e.source_url FROM graph_edges e JOIN graph_nodes n ON n.id=e.dst WHERE e.src=? AND e.rel='owns'", (f"co:{cid}",))
    news = db.rows(f"""SELECT {ART_COLS} FROM articles a LEFT JOIN sources s ON s.id=a.source_id WHERE a.id IN
        (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?) ORDER BY a.published_at DESC LIMIT 30""", (f'"{c["name"].split(" (")[0]}"',))
    cl = db.rows("""SELECT DISTINCT cluster_id FROM articles WHERE cluster_id IS NOT NULL AND id IN
        (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?) LIMIT 10""", (f'"{c["name"].split(" (")[0]}"',))
    return dict(id=cid, name=c["name"], ticker=c["ticker"], sector=c["sector"], country=c["country"], data=data,
                facts=by_kind, history=hist, index=idx, owned=subs, media=media, news=news, clusters=[x["cluster_id"] for x in cl],
                quote=markets.series_stats("CO:" + cid))


# ---------------------------------------------------------------- power graph
def _load_adj():
    adj: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for e in db.rows("SELECT * FROM graph_edges"):
        adj[e["src"]].append((e["dst"], e))
        adj[e["dst"]].append((e["src"], e))
    return adj


@router.get("/graph/search")
def graph_search(q: str, limit: int = 15):
    return db.rows("SELECT id,label,type,country FROM graph_nodes WHERE label LIKE ? ORDER BY length(label) LIMIT ?", (f"%{q}%", limit))


@router.get("/graph/neighbors")
def graph_neighbors(id: str, depth: int = Query(1, ge=1, le=3), max_nodes: int = 250):
    adj = _load_adj()
    seen, frontier, edges = {id}, [id], {}
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for m, e in adj.get(n, []):
                edges[e["id"]] = e
                if m not in seen and len(seen) < max_nodes:
                    seen.add(m)
                    nxt.append(m)
        frontier = nxt
    marks = ",".join("?" * len(seen))
    nodes = db.rows(f"SELECT * FROM graph_nodes WHERE id IN ({marks})", list(seen))
    return dict(nodes=nodes, edges=[e for e in edges.values() if e["src"] in seen and e["dst"] in seen], center=id)


@router.get("/graph/path")
def graph_path(a: str, b: str, max_depth: int = 6):
    adj = _load_adj()
    prev: dict[str, tuple[str, dict] | None] = {a: None}
    dq = deque([(a, 0)])
    while dq:
        n, d = dq.popleft()
        if n == b:
            break
        if d >= max_depth:
            continue
        for m, e in adj.get(n, []):
            if m not in prev:
                prev[m] = (n, e)
                dq.append((m, d + 1))
    if b not in prev:
        return dict(found=False, nodes=[], edges=[])
    ids, edges, cur = [b], [], b
    while prev[cur]:
        p, e = prev[cur]
        edges.append(e)
        ids.append(p)
        cur = p
    marks = ",".join("?" * len(ids))
    nodes = {n["id"]: n for n in db.rows(f"SELECT * FROM graph_nodes WHERE id IN ({marks})", ids)}
    return dict(found=True, nodes=[nodes[i] for i in reversed(ids) if i in nodes], edges=list(reversed(edges)))


# ---------------------------------------------------------------- languages
@router.get("/lang/define")
def define(word: str, lang: str, target: str = "en"):
    import httpx
    from .. import http
    w = word.strip().lower()
    out = dict(word=w, lang=lang, definitions=[], translation=None, source="Wiktionary")
    try:
        r = http.get(f"https://en.wiktionary.org/api/rest_v1/page/definition/{w}", retries=1, timeout=10)
        if r.status_code == 200:
            for entry in r.json().get(lang, []):
                for d in entry.get("definitions", [])[:3]:
                    out["definitions"].append(dict(pos=entry.get("partOfSpeech"), text=text.clean_html(d.get("definition"))))
        out["url"] = f"https://en.wiktionary.org/wiki/{w}#{lang}"
    except httpx.HTTPError:
        pass
    try:
        out["translation"] = translate.translate(w, lang, target)["text"]
        out["machine"] = True
    except Exception:  # noqa: BLE001
        pass
    return out


@router.get("/vocab")
def vocab_list(lang: str | None = None):
    return db.rows("SELECT * FROM vocab " + ("WHERE lang=? " if lang else "") + "ORDER BY created DESC LIMIT 1000", (lang,) if lang else ())


@router.post("/vocab")
def vocab_add(body: dict = Body(...)):
    db.execute("INSERT OR IGNORE INTO vocab(lang,word,translation,context,article_id,due,created) VALUES(?,?,?,?,?,?,?)",
               (body["lang"], body["word"].lower(), body.get("translation"), body.get("context"), body.get("article_id"),
                time.strftime("%Y-%m-%d"), db.now()))
    return dict(ok=True)


@router.delete("/vocab/{vid}")
def vocab_del(vid: int):
    db.execute("DELETE FROM vocab WHERE id=?", (vid,))
    return dict(ok=True)


@router.get("/vocab/due")
def vocab_due(lang: str | None = None, limit: int = 30):
    return db.rows("SELECT * FROM vocab WHERE due<=? " + ("AND lang=? " if lang else "") + "ORDER BY due LIMIT ?",
                   (time.strftime("%Y-%m-%d"), *([lang] if lang else []), limit))


@router.post("/vocab/{vid}/review")
def vocab_review(vid: int, body: dict = Body(...)):
    v = db.one("SELECT * FROM vocab WHERE id=?", (vid,))
    if not v:
        raise HTTPException(404)
    ease, interval, reps, due = sm2.review(v["ease"], v["interval"], v["reps"], int(body["quality"]))
    db.execute("UPDATE vocab SET ease=?,interval=?,reps=?,due=? WHERE id=?", (ease, interval, reps, due, vid))
    return dict(ease=ease, interval=interval, reps=reps, due=due)


@router.post("/lang/log")
def reading_log(body: dict = Body(...)):
    db.execute("INSERT INTO reading_log(lang,seconds,ts) VALUES(?,?,?)", (body["lang"], int(body["seconds"]), db.now()))
    return dict(ok=True)


@router.get("/lang/stats")
def lang_stats():
    return dict(words=db.rows("SELECT lang, COUNT(*) n, SUM(CASE WHEN reps>=3 THEN 1 ELSE 0 END) learned FROM vocab GROUP BY lang"),
                reading=db.rows("SELECT lang, SUM(seconds) seconds FROM reading_log GROUP BY lang"),
                articles_read=db.rows("SELECT lang, COUNT(*) n FROM articles WHERE read=1 GROUP BY lang"),
                known=db.get_state("setting:known_langs", ["fr", "en", "es"]))


@router.get("/lang/of-the-day")
def lang_of_the_day():
    """A story you already follow in a known language, told in a language you don't know yet."""
    known = set(db.get_state("setting:known_langs", ["fr", "en", "es"]))
    since = db.ts_ago(48 * 3600)
    best = []
    for c in db.rows("SELECT id,score FROM clusters WHERE last_seen>=? AND n_langs>=2 ORDER BY score DESC LIMIT 60", (since,)):
        arts = db.rows(f"SELECT {ART_COLS} FROM articles a LEFT JOIN sources s ON s.id=a.source_id WHERE a.cluster_id=?", (c["id"],))
        kn = [a for a in arts if a["lang"] in known]
        un = [a for a in arts if a["lang"] and a["lang"] not in known]
        if kn and un:
            best.append(dict(cluster_id=c["id"], known=kn[0], unknown=un[:3], langs=sorted({a["lang"] for a in un})))
    return best[:5]
