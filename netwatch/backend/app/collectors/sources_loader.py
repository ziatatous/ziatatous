"""Load data/sources/*.yaml into the DB, compute fiche completeness, build ownership edges for the power graph."""
import json
import re
import unicodedata

import yaml

from .. import config, db
from .base import Collector, register

# Fields that make a fiche "complete"; each counts only when it carries at least one reference URL.
CHECKS = {
    "identity": lambda s: bool(s.get("homepage") and s.get("country") and s.get("type")),
    "founded": lambda s: _has_ref(s.get("founded")),
    "ownership": lambda s: bool((s.get("ownership") or {}).get("chain")) and all(_has_ref(c) for c in s["ownership"]["chain"]),
    "financing": lambda s: bool(s.get("financing")) and all(_has_ref(c) for c in s["financing"]),
    "state_status": lambda s: _has_ref(s.get("state_affiliated")),
    "editorial_ratings": lambda s: bool(s.get("editorial_ratings")),
    "history": lambda s: bool(s.get("history")) and all(_has_ref(h) for h in s["history"]),
}


def _has_ref(x) -> bool:
    return isinstance(x, dict) and bool(x.get("ref"))


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9]+", "-", "".join(c for c in s if not unicodedata.combining(c))).strip("-")


def completeness(s: dict) -> float:
    return round(sum(1 for f in CHECKS.values() if f(s)) / len(CHECKS), 2)


def newest_verification(s: dict) -> str | None:
    dates = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("checked"):
                dates.append(str(o["checked"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(s)
    return max(dates) if dates else None


def _read_all() -> dict[str, dict]:
    """Merge every data/sources/*.yaml by id (later files, sorted by name, override earlier keys)."""
    merged: dict[str, dict] = {}
    for f in sorted((config.DATA_DIR / "sources").glob("*.yaml")):
        for s in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            merged.setdefault(s["id"], {}).update({k: v for k, v in s.items() if v is not None})
    return merged


def load() -> int:
    n = 0
    for sid, s in _read_all().items():
        s.setdefault("name", sid)
        existing = db.one("SELECT data FROM sources WHERE id=?", (sid,))
        if existing:  # keep user corrections and Wikidata enrichment stored in DB
            old = json.loads(existing["data"] or "{}")
            if old.get("_user_edited"):
                continue
            if "wikidata" in old and "wikidata" not in s:
                s["wikidata"] = old["wikidata"]
        db.execute("""INSERT INTO sources(id,name,country,languages,type,ownership_type,state_affiliated,homepage,data,completeness,verified_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,country=excluded.country,
            languages=excluded.languages,type=excluded.type,ownership_type=excluded.ownership_type,
            state_affiliated=excluded.state_affiliated,homepage=excluded.homepage,data=excluded.data,
            completeness=excluded.completeness,verified_at=excluded.verified_at""",
                   (sid, s["name"], s.get("country"), json.dumps(s.get("languages", [])), s.get("type"),
                    (s.get("ownership") or {}).get("type", "unknown"),
                    1 if (s.get("state_affiliated") or {}).get("value") else 0, s.get("homepage"),
                    json.dumps(s, ensure_ascii=False, default=str), completeness(s), newest_verification(s)))
        n += 1
    build_graph()
    return n


def node(con, id_, label, type_, country=None, qid=None):
    con.execute("INSERT INTO graph_nodes(id,label,type,country,wikidata) VALUES(?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET label=excluded.label, type=COALESCE(graph_nodes.type, excluded.type), "
                "wikidata=COALESCE(excluded.wikidata, graph_nodes.wikidata)", (id_, label, type_, country, qid))


def edge(con, src, dst, rel, url, weight=1.0, label=None):
    if not url:  # hard rule: no unsourced link in the power graph
        return
    con.execute("INSERT INTO graph_edges(src,dst,rel,weight,source_url,label) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(src,dst,rel) DO UPDATE SET weight=excluded.weight, source_url=excluded.source_url, label=excluded.label",
                (src, dst, rel, weight, url, label))


KIND_NODE = {"person": "person", "family": "person", "company": "company", "state": "state", "foundation": "org",
             "fund": "company", "ngo": "org", "cooperative": "org", "organization": "org"}


def build_graph() -> int:
    n = 0
    with db.session() as con:
        for r in con.execute("SELECT * FROM sources").fetchall():
            s = json.loads(r["data"])
            media_id = "media:" + r["id"]
            node(con, media_id, r["name"], "media", r["country"])
            chain = (s.get("ownership") or {}).get("chain") or []
            prev = media_id
            for c in chain:  # chain goes from direct owner up to the ultimate beneficiary
                nid = (c.get("company") and f"co:{c['company']}") or (c.get("qid") and f"wd:{c['qid']}") or f"{KIND_NODE.get(c.get('kind'), 'org')}:{slug(c['name'])}"
                node(con, nid, c["name"], KIND_NODE.get(c.get("kind"), "org"), c.get("country"), c.get("qid"))
                edge(con, nid, prev, "owns", c.get("ref"), _stake(c.get("stake")), c.get("stake"))
                prev = nid
                n += 1
    return n


def _stake(v) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(v or ""))
    return max(float(m.group(1).replace(",", ".")) / 100, 0.05) if m else 0.5


register(Collector("sources_yaml", "sources", 1440, load))
