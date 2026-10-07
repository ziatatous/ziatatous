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


def _pairs_above(X, thr: float, block: int = 400):
    """Yield (i, j) with j < i and cosine >= thr, without ever building a dense n x n or n x features matrix."""
    import numpy as np
    from scipy import sparse
    n = X.shape[0]
    sp = sparse.issparse(X)
    for a in range(0, n, block):
        b = min(n, a + block)
        S = X[a:b] @ X[:b].T  # rows a..b vs earlier+same block
        S = S.toarray() if sp else np.asarray(S)
        for r in range(b - a):
            i = a + r
            js = np.nonzero(S[r, :i] >= thr)[0]
            for j in js:
                yield i, int(j)


def run(window_hours: int = WINDOW_H) -> int:
    """Group recent articles into events. Single-link over cosine similarity (union-find), deterministic,
    memory-bounded (sparse blocks). Existing DB cluster ids are reused when members already had one."""
    since = db.ts_ago(window_hours * 3600)
    arts = db.rows("SELECT id,title,summary,cluster_id,published_at,source_id,country,lang FROM articles "
                   "WHERE published_at>=? ORDER BY published_at", (since,))
    if len(arts) < 2:
        return 0
    docs = [f"{a['title']} {a['title']} {(a['summary'] or '')[:300]}" for a in arts]
    X, thr, mode = vectorise(docs)
    if mode == "tfidf":
        pass  # TfidfVectorizer already L2-normalises rows -> dot product == cosine
    parent = list(range(len(arts)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j in _pairs_above(X, thr):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
    comps: dict[int, list[int]] = {}
    for i in range(len(arts)):
        comps.setdefault(find(i), []).append(i)
    changed = 0
    with db.session() as con:
        for mem in comps.values():
            if len(mem) < 2:
                continue  # singletons stay unclustered until a second article matches
            ids = [arts[i]["cluster_id"] for i in mem if arts[i]["cluster_id"]]
            cid = max(set(ids), key=ids.count) if ids else None
            if cid is None:
                cid = con.execute("INSERT INTO clusters(first_seen,last_seen) VALUES(?,?)", (db.now(), db.now())).lastrowid
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
