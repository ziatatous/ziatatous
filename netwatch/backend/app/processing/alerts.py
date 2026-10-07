"""Readable, parameterised alert rules. Every alert stores the rule that fired and its source data."""
import json
import logging

from .. import db

log = logging.getLogger("netwatch.alerts")

DEFAULT_RULES = [
    dict(id="quake_m6", name="Earthquake >= M6 (USGS)", kind="quake", params=dict(min_mag=6.0), level="VIGILANCE"),
    dict(id="quake_m7", name="Earthquake >= M7 (USGS)", kind="quake", params=dict(min_mag=7.0), level="CRITICAL"),
    dict(id="gdacs_orange", name="GDACS orange alert", kind="gdacs", params=dict(levels=["Orange"]), level="VIGILANCE"),
    dict(id="gdacs_red", name="GDACS red alert", kind="gdacs", params=dict(levels=["Red"]), level="CRITICAL"),
    dict(id="coverage_spike", name="Coverage spike (>=3x mean, >=3 countries)", kind="coverage_spike",
         params=dict(factor=4.0, min_countries=4, min_sources=8, max_per_run=3), level="INFO"),
    dict(id="market_move", name="Market move beyond threshold", kind="market_move", params=dict(pct=3.0), level="VIGILANCE"),
    dict(id="market_crash", name="Market move beyond 7 %", kind="market_move", params=dict(pct=7.0), level="CRITICAL"),
    dict(id="sanction_tracked", name="New sanction on a tracked entity", kind="sanction", params={}, level="CRITICAL"),
    dict(id="official_keyword", name="Official text matching a tracked keyword", kind="official_keyword", params={}, level="INFO"),
    dict(id="entity_mentions", name="Tracked entity cited by >= N sources", kind="entity_mentions",
         params=dict(min_sources=5, hours=24), level="INFO"),
]


def seed() -> None:
    # migrate the first (too noisy) default of the coverage-spike rule
    db.execute("UPDATE alert_rules SET params=? WHERE id='coverage_spike' AND params=?",
               (json.dumps(dict(factor=4.0, min_countries=4, min_sources=8, max_per_run=3)),
                json.dumps(dict(factor=3.0, min_countries=3, min_sources=5))))
    for r in DEFAULT_RULES:
        db.execute("INSERT OR IGNORE INTO alert_rules(id,name,kind,params,level,enabled) VALUES(?,?,?,?,?,1)",
                   (r["id"], r["name"], r["kind"], json.dumps(r["params"]), r["level"]))


def _emit(rule: dict, dedupe: str, title: str, detail: dict) -> bool:
    from ..api import bus
    n = db.execute("INSERT OR IGNORE INTO alerts(dedupe,level,rule_id,title,detail,created) VALUES(?,?,?,?,?,?)",
                   (dedupe, rule["level"], rule["id"], title,
                    json.dumps(dict(detail, rule=dict(id=rule["id"], name=rule["name"], params=rule["params"]))), db.now()))
    if n:
        bus.publish("alert", dict(level=rule["level"], title=title, rule_id=rule["id"]))
    return bool(n)


def evaluate() -> int:
    fired = 0
    rules = [dict(r, params=json.loads(r["params"] or "{}")) for r in db.rows("SELECT * FROM alert_rules WHERE enabled=1")]
    since = db.ts_ago(48 * 3600)
    for r in rules:
        k, p = r["kind"], r["params"]
        try:
            if k == "quake":
                for e in db.rows("SELECT * FROM events WHERE kind='quake' AND ts>=? AND magnitude>=?", (since, p.get("min_mag", 6))):
                    # a rule with a higher threshold supersedes the lower one for the same event
                    if r["id"] == "quake_m6" and e["magnitude"] >= 7:
                        continue
                    fired += _emit(r, f"{r['id']}:{e['uid']}", f"M{e['magnitude']:.1f} — {e['title']}",
                                   dict(event_uid=e["uid"], url=e["url"], source=e["source"], magnitude=e["magnitude"]))
            elif k == "gdacs":
                for e in db.rows("SELECT * FROM events WHERE kind='disaster' AND ts>=?", (since,)):
                    pl = json.loads(e["payload"] or "{}")
                    if pl.get("alertlevel") in p.get("levels", []):
                        fired += _emit(r, f"{r['id']}:{e['uid']}", e["title"], dict(url=e["url"], source=e["source"], **pl))
            elif k == "coverage_spike":
                rows = db.rows("SELECT id,n_sources,n_countries,score,label_article_id FROM clusters WHERE last_seen>=?", (since,))
                if len(rows) >= 5:
                    mean = sum(c["n_sources"] for c in rows) / len(rows)
                    n_emitted = 0
                    for c in sorted(rows, key=lambda x: -x["score"]):
                        if n_emitted >= p.get("max_per_run", 3):
                            break
                        if c["n_sources"] >= p["min_sources"] and c["n_sources"] >= p["factor"] * mean and c["n_countries"] >= p["min_countries"]:
                            a = db.one("SELECT title FROM articles WHERE id=?", (c["label_article_id"],)) or {"title": "?"}
                            ok_ = _emit(r, f"{r['id']}:{c['id']}", a["title"],
                                        dict(cluster_id=c["id"], sources=c["n_sources"], countries=c["n_countries"],
                                             mean_sources=round(mean, 2)))
                            fired += ok_
                            n_emitted += ok_
            elif k == "market_move":
                for m in db.rows("SELECT * FROM indicator_meta WHERE group_name IN ('markets','fx','commodities','crypto')"):
                    pts = db.rows("SELECT ts,value FROM indicators WHERE series=? ORDER BY ts DESC LIMIT 2", (m["series"],))
                    if len(pts) == 2 and pts[1]["value"]:
                        pct = (pts[0]["value"] / pts[1]["value"] - 1) * 100
                        thr = m["alert_move_pct"] or p.get("pct", 3)
                        if abs(pct) >= max(thr, p.get("pct", 0)) and (r["id"] != "market_move" or abs(pct) < 7):
                            fired += _emit(r, f"{r['id']}:{m['series']}:{pts[0]['ts']}", f"{m['label']} {pct:+.1f} %",
                                           dict(series=m["series"], last=pts[0], previous=pts[1], source_url=m["source_url"]))
            elif k == "sanction":
                tracked = [w["value"].lower() for w in db.rows("SELECT value FROM watchlist")] + \
                          [c["name"].lower() for c in db.rows("SELECT name FROM companies")]
                for d in db.rows("SELECT * FROM official_docs WHERE origin LIKE 'sanction%' AND ts>=?", (since,)):
                    if any(t in (d["title"] or "").lower() for t in tracked):
                        fired += _emit(r, f"{r['id']}:{d['uid']}", d["title"], dict(url=d["url"], origin=d["origin"]))
            elif k == "official_keyword":
                kws = [w["value"].lower() for w in db.rows("SELECT value FROM watchlist WHERE kind='keyword'")]
                for d in db.rows("SELECT * FROM official_docs WHERE ts>=?", (since,)):
                    hay = f"{d['title']} {d['summary']}".lower()
                    hit = [k2 for k2 in kws if k2 in hay]
                    if hit:
                        fired += _emit(r, f"{r['id']}:{d['uid']}", d["title"], dict(url=d["url"], origin=d["origin"], keywords=hit))
            elif k == "entity_mentions":
                since_h = db.ts_ago(p.get("hours", 24) * 3600)
                for w in db.rows("SELECT value FROM watchlist WHERE kind IN ('entity','company')"):
                    n = db.one("SELECT COUNT(DISTINCT source_id) n FROM articles WHERE published_at>=? AND "
                               "id IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?)",
                               (since_h, '"' + w["value"].replace('"', "") + '"'))
                    if n and n["n"] >= p.get("min_sources", 5):
                        fired += _emit(r, f"{r['id']}:{w['value']}:{db.now()[:10]}", f"{w['value']} cited by {n['n']} sources",
                                       dict(entity=w["value"], sources=n["n"], hours=p.get("hours", 24)))
        except Exception as e:  # noqa: BLE001
            log.warning("rule %s failed: %s", r["id"], e)
    # active = recent (last 48h) and not read
    db.execute("UPDATE alerts SET active=CASE WHEN created>=? AND read=0 THEN 1 ELSE 0 END", (since,))
    return fired
