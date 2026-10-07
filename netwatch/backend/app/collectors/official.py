"""Primary sources: EUR-Lex, BOE (Spain), Legifrance/JORF (France, DILA), sanctions (OpenSanctions)."""
import json
import logging
import re
import time

import feedparser

from .. import config, db, http
from ..processing import text
from .base import Collector, Skip, register

log = logging.getLogger("netwatch.official")

THEMES = {
    "liberties": ["liberté", "libertés", "libertad", "liberties", "freedom", "privacy", "données personnelles", "protección de datos", "rights", "droits"],
    "surveillance": ["surveillance", "vigilancia", "interception", "renseignement", "inteligencia", "biometric", "biométr", "facial recognition", "cyber"],
    "tax": ["fiscal", "impôt", "tax", "tribut", "taxe", "impuesto", "tva", "vat"],
    "energy": ["énergie", "energía", "energy", "nucléaire", "nuclear", "gas", "electric", "électri", "hydrogen", "oil", "pétrole"],
    "defense": ["défense", "defensa", "defence", "defense", "militar", "military", "armement", "armamento", "armed forces", "weapons"],
}


def themes_of(s: str) -> list[str]:
    low = (s or "").lower()
    return [k for k, ws in THEMES.items() if any(w in low for w in ws)]


def _store(origin: str, uid: str, ts: str, title: str, url: str, summary: str = "", country: str | None = None) -> int:
    th = themes_of(f"{title} {summary}")
    return db.execute("INSERT OR IGNORE INTO official_docs(uid,origin,ts,title,url,summary,themes,country) VALUES(?,?,?,?,?,?,?,?)",
                      (f"{origin}:{uid}", origin, ts, title, url, summary, json.dumps(th), country))


def _feed(url: str, origin: str, country: str) -> int:
    r = http.get(url)
    if r.status_code in (401, 403) and origin == "jorf":
        raise Skip("Légifrance blocks automated RSS access (403); the PISTE API (free account) is the alternative, see docs/ROADMAP.md")
    r.raise_for_status()
    n = 0
    for e in feedparser.parse(r.content).entries[:100]:
        t = e.get("published_parsed") or e.get("updated_parsed")
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", t) if t else db.now()
        n += _store(origin, e.get("id") or e.get("link"), ts, text.clean_html(e.get("title")), e.get("link"),
                    text.clean_html(e.get("summary"))[:600], country)
    return n


def eurlex() -> int:
    # EUR-Lex publishes RSS for custom searches; the OJ 'latest' feed is the generic one.
    return _feed("https://eur-lex.europa.eu/EN/display-feed.rss?rssId=162", "eurlex", "EU")


def parse_boe_sumario(d: dict) -> list[tuple[str, str, str, str]]:
    """BOE open-data JSON summary -> [(uid, title, url, department)]"""
    out = []
    diarios = d.get("data", {}).get("sumario", {}).get("diario", [])
    for dia in diarios if isinstance(diarios, list) else [diarios]:
        for sec in dia.get("seccion", []) if isinstance(dia.get("seccion"), list) else [dia.get("seccion", {})]:
            for dep in sec.get("departamento", []) if isinstance(sec.get("departamento"), list) else [sec.get("departamento", {})]:
                eps = dep.get("epigrafe", [])
                for ep in eps if isinstance(eps, list) else [eps]:
                    items = ep.get("item", [])
                    for it in items if isinstance(items, list) else [items]:
                        if it.get("identificador"):
                            out.append((it["identificador"], it.get("titulo", ""), (it.get("url_html") or ""), dep.get("nombre", "")))
    return out


def boe() -> int:
    n = 0
    for k in range(0, 3):
        day = time.strftime("%Y%m%d", time.gmtime(time.time() - k * 86400))
        r = http.get(f"https://www.boe.es/datosabiertos/api/boe/sumario/{day}", headers={"Accept": "application/json"})
        if r.status_code != 200:
            continue
        iso = f"{day[:4]}-{day[4:6]}-{day[6:]}T00:00:00Z"
        for uid, title, url, dep in parse_boe_sumario(r.json()):
            n += _store("boe", uid, iso, title, url, dep, "ES")
    return n


def legifrance() -> int:
    # DILA publishes the JORF through open data; the public RSS of the Journal officiel is used here
    return _feed("https://www.legifrance.gouv.fr/rss/jorf.xml", "jorf", "FR")


def sanctions() -> int:
    """OpenSanctions consolidated sanctions (default dataset). Uses the public entities index of the 'sanctions' collection."""
    key = config.key("OPENSANCTIONS_KEY")
    hdr = {"Authorization": f"ApiKey {key}"} if key else {}
    # The statistics/latest endpoint is key-free; entity-level pull needs the (free non-commercial) key or the bulk file.
    r = http.get("https://data.opensanctions.org/datasets/latest/sanctions/index.json", headers=hdr)
    r.raise_for_status()
    meta = r.json()
    ts = (meta.get("last_change") or meta.get("updated_at") or db.now())[:19] + "Z"
    n = _store("sanction:index", f"index:{ts}", ts, f"OpenSanctions consolidated sanctions updated ({meta.get('entity_count', '?')} entities)",
               "https://www.opensanctions.org/datasets/sanctions/", "")
    # entity names (targets) via the lightweight names export: one name per line in targets.nested.json is large; use simple CSV
    try:
        c = http.get("https://data.opensanctions.org/datasets/latest/sanctions/targets.simple.csv", timeout=120)
        if c.status_code == 200:
            import csv
            import io
            tracked = [w["value"].lower() for w in db.rows("SELECT value FROM watchlist")] + [x["name"].lower() for x in db.rows("SELECT name FROM companies")]
            rd = csv.DictReader(io.StringIO(c.text))
            for row in rd:
                nm = (row.get("name") or "").lower()
                if nm and any(t and t in nm for t in tracked):
                    n += _store("sanction:entity", row.get("id"), (row.get("last_change") or ts)[:19] + "Z",
                                f"{row.get('name')} — sanctioned ({row.get('countries','')})",
                                f"https://www.opensanctions.org/entities/{row.get('id')}/", row.get("sanctions", "")[:500])
    except Exception as e:  # noqa: BLE001
        log.warning("sanction entities skipped: %s", e)
    return n


register(Collector("eurlex", "official", 360, eurlex))
register(Collector("boe", "official", 360, boe))
register(Collector("legifrance", "official", 360, legifrance))
register(Collector("sanctions", "official", 720, sanctions))
