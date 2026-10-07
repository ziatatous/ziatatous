import io
import json
import sqlite3
import zipfile
from datetime import date

import pytest

from app import db
from app.collectors import corpos, events, markets, official, rss, sources_loader
from app.processing import alerts, cluster, compare, sm2, text

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Earthquake hits Chile coast</title><link>http://a.example/1</link><description>&lt;p&gt;Strong quake near Valparaiso&lt;/p&gt;</description><pubDate>Mon, 06 Oct 2025 10:00:00 GMT</pubDate></item>
<item><title>Earthquake hits Chile coast!</title><link>http://a.example/2</link><description>dup title</description></item>
<item><title>Other news</title><link>http://a.example/3</link></item></channel></rss>"""

FEED = dict(id="f1", source_id="s1", lang="en", country="US", url="http://a.example/rss")


def add_article(src, title, country, lang, summary="", hours_ago=1):
    db.execute("INSERT OR IGNORE INTO sources(id,name,country,ownership_type) VALUES(?,?,?,?)", (src, src, country, "private"))
    db.execute("INSERT INTO articles(source_id,url,title,summary,lang,country,published_at,fetched_at,title_hash) VALUES(?,?,?,?,?,?,?,?,?)",
               (src, f"http://x/{src}/{title}", title, summary, lang, country, db.ts_ago(hours_ago * 3600), db.now(), text.title_hash(title)))


def test_rss_parse_dedup_and_fts():
    n = rss.parse_and_store(FEED, RSS)
    assert n == 2  # near-duplicate title from same source dropped
    r = db.rows("SELECT title,summary,lang FROM articles ORDER BY id")
    assert r[0]["summary"] == "Strong quake near Valparaiso"  # html stripped
    hit = db.rows("SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'valparaiso'")
    assert len(hit) == 1
    assert rss.parse_and_store(FEED, RSS) == 0  # idempotent


def test_text_helpers():
    assert text.norm("Élysée, Président!") == "elysee president"
    ents = text.extract_entities("Emmanuel Macron met Olaf Scholz in Berlin.", ["Berlin"])
    assert "Emmanuel Macron" in ents and "Berlin" in ents
    assert text.detect_lang("Le président a annoncé de nouvelles mesures économiques hier soir") == "fr"
    assert len(text.sentences("One. Two! Three?")) == 3


def test_clustering_groups_same_event_across_sources_and_coverage():
    for i, (src, c, l) in enumerate([("bbc", "GB", "en"), ("lemonde", "FR", "fr"), ("elpais", "ES", "es")]):
        add_article(src, "Magnitude 7 earthquake strikes Valparaiso Chile tsunami warning", c, l, "Valparaiso Chile earthquake tsunami")
    add_article("zdf", "Stock markets rally on interest rate hopes", "DE", "de", "Dax Fed rates")
    add_article("ft", "Central bank signals interest rate cut stock rally", "GB", "en", "rates stock rally")
    cluster.run()
    rows = db.rows("SELECT cluster_id, source_id FROM articles")
    quake = {r["cluster_id"] for r in rows if r["source_id"] in ("bbc", "lemonde", "elpais")}
    assert len(quake) == 1 and None not in quake
    c = db.one("SELECT * FROM clusters WHERE id=?", (quake.pop(),))
    assert c["n_sources"] == 3 and c["n_countries"] == 3 and c["n_langs"] == 3
    assert c["score"] == cluster.coverage_score(3, 3, 3)
    # breadth beats raw volume: 3 sources/3 countries/3 langs > 4 sources in 1 country/1 lang
    assert cluster.coverage_score(3, 3, 3) > cluster.coverage_score(4, 1, 1) * 1.5


def test_cross_view_distinctive_terms_and_silences():
    add_article("bbc", "Rebels storm city, officials say", "GB", "en", "x")
    add_article("rt", "Liberation forces enter city", "RU", "en", "x")
    add_article("afp", "Armed group enters city", "FR", "en", "x")
    db.execute("INSERT INTO clusters(first_seen,last_seen) VALUES('a','b')")
    db.execute("UPDATE articles SET cluster_id=1")
    cluster.refresh_stats()
    v = compare.cluster_view(1, "country")
    assert set(v["groups"]) == {"GB", "RU", "FR"}
    assert any(t["term"] == "liberation" for t in v["distinctive"]["RU"])
    assert "AF" in v["silent_continents"] and "SA" in v["silent_continents"]
    assert [t["source_id"] for t in v["timeline"]] == ["bbc", "rt", "afp"] or len(v["timeline"]) == 3


def test_weak_signal_regional():
    for s in ("a1", "a2", "a3"):
        add_article(s, "Local dam protest grows", "BR" if s != "x" else "US", "pt", "dam protest")
    cluster.run()
    ws = cluster.weak_signals()
    assert ws and ws[0]["kind"] in ("regional", "growth")


def test_usgs_gdacs_parsers_and_alert_rules():
    usgs = {"features": [{"id": "us1", "properties": {"mag": 7.2, "time": 1_700_000_000_000, "place": "Chile", "url": "http://u"},
                          "geometry": {"coordinates": [-71, -33, 10]}},
                         {"id": "us2", "properties": {"mag": 4.9, "time": 1_700_000_000_000, "place": "x"}, "geometry": {"coordinates": [0, 0, 1]}}]}
    items = events.parse_usgs(usgs)
    assert len(items) == 2 and items[0][6] == 7.2
    now = db.now()
    with db.session() as con:
        for i in items:
            i = list(i); i[2] = now
            events._put(con, *i)
    alerts.seed()
    assert alerts.evaluate() >= 1
    al = db.rows("SELECT * FROM alerts")
    assert [a["level"] for a in al] == ["CRITICAL"]  # M7.2 -> critical only, M6 rule superseded
    d = json.loads(al[0]["detail"])
    assert d["rule"]["id"] == "quake_m7" and d["url"] == "http://u"  # rule + source data always attached
    assert alerts.evaluate() == 0  # dedupe
    gd = {"features": [{"properties": {"eventtype": "FL", "eventid": 1, "episodeid": 2, "alertlevel": "Red", "name": "Flood", "fromdate": "2025-10-01T00:00:00",
                                       "url": {"details": "http://g"}}, "geometry": {"type": "Point", "coordinates": [10, 20]}}]}
    assert events.parse_gdacs(gd)[0][2].endswith("Z")


def test_gdelt_parse():
    cols = [""] * 61
    cols[28], cols[30], cols[53], cols[56], cols[57], cols[60] = "19", "-8.0", "UP", "49.0", "31.0", "http://news/x"
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("x.export.CSV", "\n".join(["\t".join(cols)] * 4))
    agg = events.parse_gdelt_export(z.getvalue())
    assert agg[("UP", "conflict")][0] == 4


def test_market_parsers_and_stats():
    pts = markets.parse_stooq_csv("Date,Open,High,Low,Close,Volume\n2025-01-01,1,1,1,10,5\n2025-01-02,1,1,1,12,5\nbad,,,,x,")
    assert pts == [("2025-01-01", 10.0), ("2025-01-02", 12.0)]
    assert markets.parse_ecb_csv("TIME_PERIOD,OBS_VALUE\n2025-03,2.5\n2025-04-01,2.4")[0] == ("2025-03-01", 2.5)
    js = {"dimension": {"time": {"category": {"index": {"2025-01": 0, "2025-02": 1}}}}, "value": {"0": 6.1, "1": 6.0}}
    assert markets.parse_jsonstat_time_series(js)[-1] == ("2025-02-01", 6.0)
    markets._store("T", [("2025-01-01", 10), ("2025-01-02", 20)])
    st = markets.series_stats("T")
    assert st["change_pct"] == 100 and st["percentile_10y"] == 100


def test_market_alert():
    alerts.seed()
    with db.session() as con:
        markets._meta(con, "SPX", "S&P 500", "pts", "markets", "Stooq", "http://s", db.now())
    markets._store("SPX", [("2025-01-01", 100.0), ("2025-01-02", 94.0)])
    alerts.evaluate()
    assert [a["rule_id"] for a in db.rows("SELECT rule_id FROM alerts")] == ["market_move"]


def test_boe_parse():
    d = {"data": {"sumario": {"diario": [{"seccion": [{"departamento": [{"nombre": "MINISTERIO", "epigrafe": [
        {"item": [{"identificador": "BOE-A-1", "titulo": "Real Decreto", "url_html": "http://boe/1"}]}]}]}]}]}}}
    assert official.parse_boe_sumario(d) == [("BOE-A-1", "Real Decreto", "http://boe/1", "MINISTERIO")]
    assert official.themes_of("Loi sur la surveillance et l'énergie nucléaire") == ["surveillance", "energy"]


def test_13f_parser():
    x = """<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable"><infoTable><nameOfIssuer>APPLE INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>1000</value><shrsOrPrnAmt><sshPrnamt>50</sshPrnamt></shrsOrPrnAmt></infoTable></informationTable>"""
    h = corpos.parse_13f_infotable(x)
    assert h[0]["issuer"] == "APPLE INC" and h[0]["shares"] == 50
    assert corpos._norm_issuer("Apple Inc.") == corpos._norm_issuer("APPLE INC")


def test_sm2():
    e, i, r, d = sm2.review(2.5, 0, 0, 5, date(2025, 1, 1))
    assert (i, r, d) == (1, 1, "2025-01-02")
    e, i, r, d = sm2.review(e, i, r, 4, date(2025, 1, 2))
    assert i == 6
    e, i, r, d = sm2.review(e, i, r, 1, date(2025, 1, 8))
    assert (i, r) == (1, 0) and e >= 1.3


def test_graph_edges_must_be_sourced():
    with db.session() as con:
        sources_loader.node(con, "a", "A", "person")
        sources_loader.node(con, "b", "B", "company")
        sources_loader.edge(con, "a", "b", "owns", None)  # silently refused
        sources_loader.edge(con, "a", "b", "owns", "http://ref")
    assert len(db.rows("SELECT * FROM graph_edges")) == 1
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO graph_edges(src,dst,rel,source_url) VALUES('a','b','x','')")


def test_sources_completeness(tmp_path):
    s = dict(id="x", name="X", country="FR", type="press", homepage="http://x",
             founded=dict(value=1944, ref="http://r"), ownership=dict(type="private", chain=[dict(name="O", kind="person", ref="http://r")]),
             financing=[dict(kind="ads", ref="http://r")], state_affiliated=dict(value=False, ref="http://r"))
    assert sources_loader.completeness(s) == round(5 / 7, 2)
    s["ownership"]["chain"][0].pop("ref")
    assert sources_loader.completeness(s) < round(5 / 7, 2)


def test_cluster_scales_without_dense_matrix():
    import random
    random.seed(0)
    words = [f"w{n}" for n in range(3000)]
    for k in range(1500):  # 1500 articles, ~100 events of 15 articles each
        topic = k % 100
        add_article(f"s{k}", f"event{topic} alpha{topic} beta{topic} gamma{topic} delta{topic} " + " ".join(random.sample(words, 2)), "FR", "en", "", hours_ago=2)
    cluster.run()
    n = db.one("SELECT COUNT(DISTINCT cluster_id) n FROM articles WHERE cluster_id IS NOT NULL")["n"]
    assert 90 <= n <= 110


def test_scheduler_jobs_are_not_paused(monkeypatch):
    from app import scheduler
    from app.collectors import base
    monkeypatch.setattr(base, "run_async", lambda names=None: None)
    s = scheduler.start(collect=True)
    try:
        jobs = {j.id: j for j in s.get_jobs()}
        assert "rss" in jobs and jobs["rss"].next_run_time is not None
        assert jobs["maintenance"].next_run_time is not None
    finally:
        scheduler.stop()


def test_fts_query_symbols_only():
    from app.api.routes import _fts_query
    assert db.rows("SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?", (_fts_query("?!"),)) == []


def test_13f_parser_handles_prefixed_namespaces():
    x = """<?xml version="1.0"?><ns1:informationTable xmlns:ns1="http://www.sec.gov/edgar/document/thirteenf/informationtable" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="a b">
    <ns1:infoTable><ns1:nameOfIssuer>APPLE INC</ns1:nameOfIssuer><ns1:titleOfClass>COM</ns1:titleOfClass><ns1:cusip>1</ns1:cusip><ns1:value>5</ns1:value>
    <ns1:shrsOrPrnAmt><ns1:sshPrnamt>7</ns1:sshPrnamt></ns1:shrsOrPrnAmt></ns1:infoTable></ns1:informationTable>"""
    h = corpos.parse_13f_infotable(x)
    assert h and h[0]["issuer"] == "APPLE INC" and h[0]["shares"] == 7


def test_missing_key_is_skipped_not_failed(monkeypatch):
    from app.collectors import base
    c = base.Collector("t_skip", "x", 10, lambda: (_ for _ in ()).throw(base.Skip("no key")))
    r = c.run()
    assert r["ok"] is True and r["error"].startswith("skipped")
    assert db.one("SELECT ok FROM collector_runs WHERE collector='t_skip'")["ok"] == 1


def test_gdacs_rss_fallback_parser():
    rss_xml = b"""<?xml version="1.0"?><rss xmlns:gdacs="http://www.gdacs.org" xmlns:georss="http://www.georss.org/georss" version="2.0"><channel>
    <item><title>Red alert flood</title><link>http://g/1</link><gdacs:alertlevel>Red</gdacs:alertlevel><gdacs:eventtype>FL</gdacs:eventtype><gdacs:eventid>9</gdacs:eventid><georss:point>10.5 20.5</georss:point></item></channel></rss>"""
    items = events.parse_gdacs_rss(rss_xml)
    assert items and items[0][4:6] == (10.5, 20.5) and items[0][10]["alertlevel"] == "Red"


def test_cluster_update_does_not_touch_fts(monkeypatch):
    add_article("bbc", "Quake in Chile", "GB", "en", "tsunami")
    add_article("elpais", "Quake in Chile tsunami", "ES", "es", "tsunami")
    before = db.rows("SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'tsunami'")
    cluster.run()
    assert db.rows("SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'tsunami'") == before  # still indexed once each


def test_cluster_skips_when_nothing_new():
    add_article("a", "Same story alpha beta gamma", "FR", "fr", "")
    add_article("b", "Same story alpha beta gamma", "ES", "es", "")
    assert cluster.run() >= 1
    assert cluster.run() == 0


def test_coverage_spike_is_capped():
    alerts.seed()
    for i in range(40):
        db.execute("INSERT INTO articles(source_id,url,title,published_at,fetched_at,country,lang) VALUES('s',?,?,?,?,'FR','fr')", (f"u{i}", f"t{i}", db.now(), db.now()))
        big = i < 5
        db.execute("INSERT INTO clusters(label_article_id,first_seen,last_seen,n_articles,n_sources,n_countries,n_langs,score) VALUES(?,?,?,?,?,?,?,?)",
                   (i + 1, db.now(), db.now(), 100 if big else 1, 100 if big else 1, 6, 3, 90 - i))
    alerts.evaluate()
    assert db.one("SELECT COUNT(*) n FROM alerts WHERE rule_id='coverage_spike'")["n"] == 3
