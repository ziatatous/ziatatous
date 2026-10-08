# ASFALTO — observatoire personnel des mouvements de rue

Tableau de bord **local**, sans IA, qui agrège des sources publiques (RSS / ICS) et affiche des fiches
(mouvements, scènes, contre-surveillance). Chaque info renvoie à sa source. Un seul utilisateur.

## Lancer
Il faut **Python 3.10+** installé (python.org). Ensuite :

- **Linux / macOS** : `./start.sh`
- **Windows** : double-clic sur `start.bat`

Le script crée un environnement `.venv`, installe `requirements.txt`, démarre le serveur sur
http://127.0.0.1:8000 et ouvre le navigateur. Arrêt : `Ctrl+C`.
Au premier lancement, la collecte démarre toute seule (quelques minutes). Ensuite : toutes les 3 h
tant que le programme tourne, avec rattrapage au démarrage.

## Où est quoi
| Fichier | Rôle |
|---|---|
| `data/feeds.yaml` | flux RSS (nom, URL, orientation, rubrique) — **à toi de modifier** |
| `data/agenda.yaml` | agendas ICS/RSS publics + événements saisis à la main (Terrain) |
| `data/mouvements.yaml` · `scenes.yaml` · `surveillance.yaml` | contenu des fiches |
| `data/scenes_annuaire.yaml` | annuaire de canaux publics par ville |
| `data/cities.yaml` | villes (centre de carte) |
| `backend/main.py` | tout le backend (API + collecte) |
| `frontend/` | interface (HTML/CSS/JS, aucune étape de build) |

## Points d'attention (honnêteté)
- **Les URLs des flux n'ont pas pu être testées** pendant l'écriture (réseau bloqué). Ouvre la page
  **Système → Collecter maintenant** : les flux morts apparaissent en rouge avec l'erreur. Remplace-les ou
  mets `enabled: false` dans `feeds.yaml`.
- **Les fiches sont des résumés de départ écrits à la main** (pas générés à l'exécution), avec leurs liens de
  référence. Relis-les, corrige-les et complète-les. Les liens Wikipédia n'ont pas été vérifiés non plus.
- **Terrain** : aucun agenda n'est configuré par défaut (je n'ai pas voulu inventer d'URL). Ajoute des
  ICS/RSS publics de salles ou collectifs dans `agenda.yaml`, ou saisis des événements dans `manual:`.
  Sans source : « Rien d'annoncé ».
- Les écarts avec ton prompt, pour rester simple : interface en JS sans build (pas de Vite/React/Tailwind),
  pas de galerie d'images (les droits des visuels sont à gérer toi-même : propose-moi de l'ajouter), PWA
  minimale (manifest seulement).

## Sauvegarde
Page Système : *Exporter la base* (fichier `.db` avec articles, événements et notes) / *Importer une base*.
Tes fichiers `data/*.yaml` se sauvegardent en les copiant.

## Notes perso
Sur chaque fiche mouvement/scène, une zone « Mes notes » ; page **Notes** pour tout relire.

## Raccourcis
`Ctrl/Cmd+K` : palette de commandes. Bouton *Mode calme* : coupe les animations (déjà respecté si ton
système demande `prefers-reduced-motion`). Le glitch ne s'affiche que sur les articles apparus depuis ta dernière visite.
