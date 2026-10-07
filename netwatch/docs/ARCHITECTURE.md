# NETWATCH — architecture

## Stack (et pourquoi)
| Couche | Choix | Raison |
|---|---|---|
| Backend | Python 3.12+, FastAPI, SQLite + FTS5, APScheduler | Un seul fichier de base, recherche plein texte intégrée, aucune installation serveur. |
| Collecte | `httpx` (poli : délai par hôte, retries/backoff), `feedparser`, `trafilatura` (extraction locale à la demande) | Léger. L'extraction du texte intégral n'a lieu que quand on ouvre un article (robots.txt respecté). |
| Clustering | scikit-learn TF-IDF (défaut) ou `sentence-transformers` (option) | Aucun texte n'est généré. TF-IDF = repli léger, sans modèle. |
| Frontend | Vite + React + TypeScript, Tailwind, D3, globe.gl, ECharts, TanStack Query, Zustand, i18next | Animations en CSS (pas de framer-motion) : elles se coupent toutes d'un coup (mode calme, prefers-reduced-motion). |
| Temps réel | Server-Sent Events (`/api/events/stream`) | Alertes poussées vers l'UI. |
| Distribution | `start.sh` / `start.bat` ; le backend sert `frontend/dist` | Un seul processus, une seule adresse. |

## Flux de données
```
collectors/* ──► SQLite ──► processing (entités, clusters, alertes) ──► api/routes.py ──► React
   ▲  APScheduler (+ rattrapage au démarrage)                              └─ SSE (alertes)
data/*.yaml (feeds, sources, corpos, agenda) ─ chargés au démarrage, les corrections utilisateur gagnent
```
- **Collecteur** : `collectors/base.py` — chaque collecteur est isolé, journalisé dans `collector_runs`, une panne n'en bloque aucun autre.
- **Rattrapage** : `scheduler.start()` relance au démarrage les collecteurs dont le dernier succès est plus vieux que leur période.
- **Rétention** : `processing/maintenance.retention()` (cron 04:15).
- **Mode VPS** : `python -m app.main --collector-only` ; PWA-ready (manifest + service worker du shell).

## Garde-fous encodés dans le code
- `graph_edges.source_url NOT NULL CHECK(length>0)` : impossible de stocker un lien non sourcé (+ `edge()` refuse). Testé.
- Complétude d'une fiche source = champs **avec URL de référence** (`sources_loader.CHECKS`).
- Score de couverture = `sources × (1+ln pays) × (1+ln langues)` (`cluster.coverage_score`) : ampleur, pas popularité.
- Vue croisée : log-odds lissés par groupe (`processing/compare.py`) — statistique, pas de texte généré.
- Alertes : chaque alerte stocke la règle (id, nom, paramètres) et les données sources (`processing/alerts.py`).
- Effets visuels (glitch, décryptage) uniquement sur changement réel de donnée (`useChanged`, `Decrypt fresh`).

## Emplacement IA (désactivé)
Rien d'actif. Point d'extension prévu : un module `processing/analysis.py` derrière une interface `Analyzer` et un onglet « Analysis » grisé ; aucune route ne l'expose aujourd'hui.
