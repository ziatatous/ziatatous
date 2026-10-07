"""Multilingual event clustering. No text is generated: it only decides which articles
talk about the same event. Two backends: TF-IDF (default, light) and sentence embeddings."""
import json
import logging
import math

from .. import config, db
from ..countries import COUNTRIES
from . import text

log = logging.getLogger("netwatch.cluster")
WINDOW_H = 72


def _embed(texts: list[str]):
    from sentence_transformers import SentenceTransformer  # optional dependency
    global _model
    try:
        _model
    except NameError:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model.encode(texts, normalize_embeddings=True)


def _tfidf(texts: list[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer
    # Word unigrams + bigrams over normalised text. Cross-language matches rely on shared
    # proper nouns, numbers and loanwords; the embeddings backend handles true translation.
    v = TfidfVectorizer(preprocessor=text.norm, ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=60000)
    return v.fit_transform(texts)


def vectorise(texts: list[str]):
    if config.CLUSTER_MODE == "embeddings":
        try:
            return _embed(texts), 0.72, "embeddings"
        except Exception as e:  # noqa: BLE001
            log.warning("embeddings unavailable (%s) -> TF-IDF fallback", e)
    return _tfidf(texts), 0.28, "tfidf"


def run(window_hours: int = WINDOW_H) -> int:
    """Assign recent articles to clusters (greedy single pass, deterministic order)."""
    import numpy as np
    since = db.ts_ago(window_hours * 3600)
    arts = db.rows("SELECT id,title,summary,cluster_id,published_at,source_id,country,lang FROM articles "
                   "WHERE published_at>=? ORDER BY published_at", (since,))
    if len(arts) < 2:
        return 0
    docs = [f"{a['title']} {a['title']} {(a['summary'] or '')[:300]}" for a in arts]
    X, thr, mode = vectorise(docs)
    dense = X.toarray() if hasattr(X, "toarray") else np.asarray(X)
    norms = np.linalg.norm(dense, axis=1, keepdims=True)
    norms[norms == 0] = 1
    dense = dense / norms
    assign: dict[int, int] = {}  # article idx -> local cluster idx
    cents: list[np.ndarray] = []
    members: list[list[int]] = []
    for i in range(len(arts)):
        best, best_s = -1, 0.0
        if cents:
            sims = np.dot(np.vstack(cents), dense[i])
            j = int(np.argmax(sims))
            best, best_s = j, float(sims[j])
        if best >= 0 and best_s >= thr:
            members[best].append(i)
            cents[best] = dense[members[best]].mean(axis=0)
            cents[best] /= (np.linalg.norm(cents[best]) or 1)
            assign[i] = best
        else:
            cents.append(dense[i].copy())
            members.append([i])
            assign[i] = len(cents) - 1
    changed = 0
    with db.session() as con:
        # reuse existing DB cluster id when members already had one (stable ids across runs)
        for mem in members:
            ids = [arts[i]["cluster_id"] for i in mem if arts[i]["cluster_id"]]
            cid = max(set(ids), key=ids.count) if ids else None
            if len(mem) == 1 and cid is None:
                continue  # singletons stay unclustered until a second article matches
            if cid is None:
                cur = con.execute("INSERT INTO clusters(first_seen,last_seen) VALUES(?,?)", (db.now(), db.now()))
                cid = cur.lastrowid
            for i in mem:
                if arts[i]["cluster_id"] != cid:
                    con.execute("UPDATE articles SET cluster_id=? WHERE id=?", (cid, arts[i]["id"]))
                    changed += 1
    refresh_stats()
    log.info("cluster[%s]: %d articles, %d re-assigned", mode, len(arts), changed)
    return changed


def coverage_score(n_sources: int, n_countries: int, n_langs: int) -> float:
    """Breadth of coverage (NOT popularity): sources x (1+ln countries) x (1+ln languages)."""
    if n_sources <= 0:
        return 0.0
    return round(n_sources * (1 + math.log(max(n_countries, 1))) * (1 + math.log(max(n_langs, 1))), 2)


def refresh_stats() -> None:
    with db.session() as con:
        con.execute("DELETE FROM clusters WHERE id NOT IN (SELECT DISTINCT cluster_id FROM articles WHERE cluster_id IS NOT NULL)")
        rows = con.execute("""SELECT cluster_id id, COUNT(*) n, COUNT(DISTINCT source_id) s, COUNT(DISTINCT country) c,
                COUNT(DISTINCT lang) l, MIN(published_at) f, MAX(published_at) la FROM articles
                WHERE cluster_id IS NOT NULL GROUP BY cluster_id""").fetchall()
        for r in rows:
            # label article = longest title among the earliest third (original wording, never rewritten)
            lab = con.execute("SELECT id FROM articles WHERE cluster_id=? ORDER BY LENGTH(title) DESC, published_at LIMIT 1",
                              (r["id"],)).fetchone()
            con.execute("UPDATE clusters SET n_articles=?,n_sources=?,n_countries=?,n_langs=?,score=?,first_seen=?,"
                        "last_seen=?,label_article_id=? WHERE id=?",
                        (r["n"], r["s"], r["c"], r["l"], coverage_score(r["s"], r["c"], r["l"]), r["f"], r["la"],
                         lab["id"] if lab else None, r["id"]))


def weak_signals(limit: int = 20) -> list[dict]:
    """Two documented heuristics, no black box:
    - 'growth': <=4 sources but >=2x more articles in the last 6h than in the 6h before;
    - 'regional': >=3 sources, all from one continent, none elsewhere."""
    out = []
    now_6, now_12 = db.ts_ago(6 * 3600), db.ts_ago(12 * 3600)
    for c in db.rows("SELECT * FROM clusters WHERE n_sources>=2 ORDER BY last_seen DESC LIMIT 400"):
        arts = db.rows("SELECT published_at,country,source_id FROM articles WHERE cluster_id=?", (c["id"],))
        recent = sum(1 for a in arts if a["published_at"] >= now_6)
        before = sum(1 for a in arts if now_12 <= a["published_at"] < now_6)
        conts = {COUNTRIES.get(a["country"], {}).get("continent") for a in arts if a["country"]}
        conts.discard(None)
        if c["n_sources"] <= 4 and recent >= 2 and recent >= 2 * max(before, 1):
            out.append(dict(cluster_id=c["id"], kind="growth", detail=dict(recent_6h=recent, previous_6h=before,
                                                                          sources=c["n_sources"])))
        elif c["n_sources"] >= 3 and len(conts) == 1:
            out.append(dict(cluster_id=c["id"], kind="regional", detail=dict(continent=next(iter(conts)),
                                                                            sources=c["n_sources"])))
    return out[:limit]
