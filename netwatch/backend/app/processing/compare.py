"""Cross-view analytics for one cluster. Purely statistical (frequencies, log-odds), no generated text."""
import math
from collections import Counter

from .. import db
from ..countries import COUNTRIES
from . import text


def _group_key(a: dict, by: str) -> str:
    if by == "country":
        return a["country"] or "?"
    if by == "ownership":
        return a["ownership_type"] or "unknown"
    if by == "lang":
        return a["lang"] or "?"
    return a["source_id"]


def cluster_view(cluster_id: int, by: str = "country") -> dict:
    cl = db.one("SELECT * FROM clusters WHERE id=?", (cluster_id,))
    if not cl:
        return {}
    arts = db.rows("""SELECT a.id,a.title,a.summary,a.url,a.lang,a.country,a.published_at,a.source_id,a.entities,
                      s.name source_name,s.ownership_type,s.type source_type,s.state_affiliated
                      FROM articles a LEFT JOIN sources s ON s.id=a.source_id WHERE a.cluster_id=? ORDER BY a.published_at""",
                   (cluster_id,))
    groups: dict[str, list[dict]] = {}
    for a in arts:
        groups.setdefault(_group_key(a, by), []).append(a)
    # distinctive vocabulary per group: smoothed log-odds vs. the rest of the cluster
    tot: Counter = Counter()
    per: dict[str, Counter] = {}
    for g, items in groups.items():
        c = Counter(t for a in items for t in set(text.tokens(a["title"])))
        per[g] = c
        tot.update(c)
    n_total = sum(tot.values()) or 1
    distinct = {}
    for g, c in per.items():
        n_g = sum(c.values()) or 1
        scored = []
        for t, k in c.items():
            other = tot[t] - k
            lo = math.log((k + .5) / (n_g + 1)) - math.log((other + .5) / (n_total - n_g + 1))
            scored.append((lo, t, k))
        distinct[g] = [dict(term=t, count=k, score=round(lo, 2)) for lo, t, k in sorted(scored, reverse=True)[:8] if lo > 0]
    shared = [t for t, k in tot.most_common(20) if sum(1 for c in per.values() if t in c) >= max(2, len(per) // 2 + 1)][:10]
    ents: Counter = Counter()
    for a in arts:
        try:
            import json
            ents.update(json.loads(a["entities"] or "[]"))
        except Exception:  # noqa: BLE001
            pass
    # coverage timeline: first article per source; silences = continents with zero coverage
    seen, timeline = set(), []
    for a in arts:
        if a["source_id"] not in seen:
            seen.add(a["source_id"])
            timeline.append(dict(source_id=a["source_id"], source=a["source_name"] or a["source_id"],
                                 country=a["country"], at=a["published_at"], article_id=a["id"]))
    covered = {COUNTRIES.get(a["country"], {}).get("continent") for a in arts}
    silent = sorted({c["continent"] for c in COUNTRIES.values()} - covered - {None})
    return dict(cluster=cl, by=by, groups=groups, distinctive=distinct, shared_terms=shared,
                top_entities=[dict(entity=e, count=n) for e, n in ents.most_common(12)], timeline=timeline,
                silent_continents=silent)
