import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, bootstrap
from app.processing import cluster, maintenance
from tests.test_core import add_article


@pytest.fixture()
def client(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", config.BASE / "data")  # real shipped data files
    db.init()
    app.state.no_collect = True
    from app.processing import alerts
    from app.collectors import load_all, sources_loader, corpos, rss
    alerts.seed(); load_all(); sources_loader.load(); corpos.load_companies(); rss.sync_feeds()
    with TestClient(app) as c:
        yield c


def test_endpoints_smoke(client):
    for src, c, l in [("bbc", "GB", "en"), ("lemonde", "FR", "fr"), ("elpais", "ES", "es")]:
        add_article(src, "Magnitude 7 earthquake strikes Valparaiso Chile", c, l, "tsunami warning Valparaiso")
    cluster.run(); maintenance.enrich_entities()
    for path in ["/api/health", "/api/system", "/api/startup", "/api/briefing", "/api/clusters", "/api/facets", "/api/sources",
                 "/api/sources/lemonde", "/api/articles?q=valparaiso", "/api/articles?lang=fr", "/api/world/heat", "/api/world/events",
                 "/api/world/countries", "/api/world/country/FR", "/api/vitals", "/api/official", "/api/agenda", "/api/alerts",
                 "/api/alert-rules", "/api/watchlist", "/api/companies", "/api/companies/lvmh", "/api/graph/search?q=LVMH",
                 "/api/vocab", "/api/lang/stats", "/api/lang/of-the-day", "/api/timeline?topic=valparaiso", "/api/backup/export",
                 "/api/world/arcs", "/api/system/feeds"]:
        r = client.get(path)
        assert r.status_code == 200, (path, r.text[:300])
    cl = client.get("/api/clusters").json()
    assert cl and cl[0]["n_sources"] == 3
    v = client.get(f"/api/clusters/{cl[0]['id']}?by=ownership").json()
    assert v["cluster"]["id"] == cl[0]["id"]
    assert len(client.get("/api/articles?q=valparaiso").json()["items"]) == 3


def test_graph_path_and_sourced_edges(client):
    p = client.get("/api/graph/path", params={"a": "co:lvmh", "b": "media:leparisien"}).json()
    assert p["found"] and all(e["source_url"] for e in p["edges"])
    n = client.get("/api/graph/neighbors", params={"id": "co:lvmh", "depth": 2}).json()
    assert n["nodes"] and all(e["source_url"] for e in n["edges"])


def test_watchlist_vocab_backup_roundtrip(client):
    client.post("/api/watchlist", json={"kind": "keyword", "value": "nuclear"})
    client.post("/api/vocab", json={"lang": "fr", "word": "Séisme", "translation": "earthquake", "context": "Un séisme."})
    vid = client.get("/api/vocab/due").json()[0]["id"]
    r = client.post(f"/api/vocab/{vid}/review", json={"quality": 5}).json()
    assert r["interval"] == 1
    exp = client.get("/api/backup/export").json()
    assert exp["watchlist"][0]["value"] == "nuclear" and exp["vocab"][0]["word"] == "séisme"
    db.execute("DELETE FROM watchlist")
    assert client.post("/api/backup/import", json=exp).json()["imported"] >= 1
    assert client.get("/api/watchlist").json()[0]["value"] == "nuclear"


def test_mark_read_and_source_edit(client):
    assert client.post("/api/briefing/mark-read").json()["ok"]
    assert client.get("/api/startup").json()["last_visit"]
    body = {"name": "Test Media", "country": "FR", "type": "online", "homepage": "http://t", "ownership": {"type": "private", "chain": []}}
    assert client.put("/api/sources/testmedia", json=body).json()["ok"]
    assert client.get("/api/sources/testmedia").json()["name"] == "Test Media"
