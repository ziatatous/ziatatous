"""Wikidata enrichment (SPARQL + entity search): ownership (P127), inception, country, board members, public offices."""
import json
import logging
import urllib.parse

from .. import db, http
from .base import Collector, register
from .sources_loader import edge, node

log = logging.getLogger("netwatch.wikidata")
SPARQL = "https://query.wikidata.org/sparql"


def sparql(q: str) -> list[dict]:
    r = http.get(SPARQL, params={"query": q, "format": "json"}, headers={"Accept": "application/sparql-results+json"}, timeout=60)
    r.raise_for_status()
    return [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]


def search_entity(name: str, lang: str = "en") -> dict | None:
    d = http.get_json("https://www.wikidata.org/w/api.php", params={
        "action": "wbsearchentities", "search": name, "language": lang, "format": "json", "limit": 1, "type": "item"})
    s = d.get("search") or []
    return s[0] if s else None


def qid_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def enrich_entity(qid: str) -> dict:
    rows = sparql(f"""SELECT ?ownerLabel ?owner ?inception ?countryLabel ?parentLabel ?parent WHERE {{
      VALUES ?e {{ wd:{qid} }}
      OPTIONAL {{ ?e wdt:P127 ?owner }} OPTIONAL {{ ?e wdt:P571 ?inception }}
      OPTIONAL {{ ?e wdt:P17 ?country }} OPTIONAL {{ ?e wdt:P749 ?parent }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,fr,es". }} }} LIMIT 50""")
    owners = {qid_of(r["owner"]): r.get("ownerLabel") for r in rows if r.get("owner")}
    parents = {qid_of(r["parent"]): r.get("parentLabel") for r in rows if r.get("parent")}
    return dict(qid=qid, url=f"https://www.wikidata.org/wiki/{qid}", owners=owners, parents=parents,
                inception=next((r["inception"][:10] for r in rows if r.get("inception")), None),
                country=next((r["countryLabel"] for r in rows if r.get("countryLabel")), None),
                checked=db.now()[:10])


def reverify_source(source_id: str) -> dict:
    s = db.one("SELECT * FROM sources WHERE id=?", (source_id,))
    if not s:
        raise KeyError(source_id)
    data = json.loads(s["data"])
    qid = (data.get("wikidata") or {}).get("qid")
    if not qid:
        hit = search_entity(data.get("name") or s["name"])
        if not hit:
            raise LookupError(f"no Wikidata entity found for {s['name']}")
        qid = hit["id"]
    wd = enrich_entity(qid)
    wd["auto_match"] = True  # name-based match: the user can confirm/correct the QID
    data["wikidata"] = wd
    db.execute("UPDATE sources SET data=?, verified_at=? WHERE id=?", (json.dumps(data, ensure_ascii=False), wd["checked"], source_id))
    with db.session() as con:
        mid = "media:" + source_id
        node(con, mid, s["name"], "media", s["country"], qid)
        for oq, ol in wd["owners"].items():
            node(con, f"wd:{oq}", ol or oq, "company", None, oq)
            edge(con, f"wd:{oq}", mid, "owns", f"https://www.wikidata.org/wiki/{qid}#P127", 0.5, "Wikidata P127")
    return wd


def reverify_all() -> int:
    n = 0
    for s in db.rows("SELECT id FROM sources"):
        try:
            reverify_source(s["id"])
            n += 1
        except Exception as e:  # noqa: BLE001
            log.warning("wikidata %s: %s", s["id"], e)
    return n


def company_people(company_id: str, qid: str) -> int:
    """Executives/board members (P169/P3320/P488) and their past public offices (P39): the revolving door."""
    rows = sparql(f"""SELECT ?role ?p ?pLabel ?pos ?posLabel ?start ?end WHERE {{
      VALUES ?c {{ wd:{qid} }} VALUES ?role {{ wdt:P169 wdt:P3320 wdt:P488 wdt:P127 }}
      ?c ?role ?p . ?p wdt:P31 wd:Q5 .
      OPTIONAL {{ ?p p:P39 ?st . ?st ps:P39 ?pos . OPTIONAL {{ ?st pq:P580 ?start }} OPTIONAL {{ ?st pq:P582 ?end }} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,fr,es". }} }} LIMIT 300""")
    rel_name = {"P169": "ceo_of", "P3320": "board_of", "P488": "chair_of", "P127": "owns"}
    n = 0
    with db.session() as con:
        cnode = f"co:{company_id}"
        for r in rows:
            pq = qid_of(r["p"])
            node(con, f"wd:{pq}", r.get("pLabel", pq), "person", None, pq)
            rel = rel_name.get(qid_of(r["role"]), "board_of")
            # the SPARQL "role" variable is a property URI; map by suffix
            rel = next((v for k, v in rel_name.items() if r["role"].endswith(k)), rel)
            edge(con, f"wd:{pq}", cnode, rel, f"https://www.wikidata.org/wiki/{qid}", 1.0, rel)
            if r.get("pos"):
                posq = qid_of(r["pos"])
                node(con, f"wd:{posq}", r.get("posLabel", posq), "state", None, posq)
                edge(con, f"wd:{pq}", f"wd:{posq}", "held_public_office", f"https://www.wikidata.org/wiki/{pq}", 1.0,
                     f"{(r.get('start') or '')[:4]}–{(r.get('end') or '')[:4]}")
                con.execute("INSERT OR IGNORE INTO company_facts(company_id,kind,ts,label,value,url,payload) VALUES(?,?,?,?,?,?,?)",
                            (company_id, "revolving_door", (r.get("start") or "0000")[:10], f"{r.get('pLabel')} — {r.get('posLabel')}", None,
                             f"https://www.wikidata.org/wiki/{pq}", json.dumps(dict(person=r.get("pLabel"), role=rel, office=r.get("posLabel"),
                                                                                    start=(r.get("start") or "")[:10], end=(r.get("end") or "")[:10]))))
            n += 1
    return n


register(Collector("wikidata_sources", "sources", 10080, reverify_all))
