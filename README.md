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

## Ce que c'est maintenant : un tableau de bord LIVE
Pas d'historique ni de guides. Uniquement ce qui se passe :
- **Mouvements actifs** : les pays classés par nombre d'articles d'action (manifestation, grève, émeutes, protest, riot, huelga…) sur 24 h / 72 h / 7 j. Clique un pays pour lire les articles.
- **Live** (accueil) : les derniers articles d'action des 48 dernières heures + événements à venir.
- **Terrain** : carte + agenda des événements annoncés publiquement, annuaire de canaux publics.
- **Surveillance** : fil d'actu sur les libertés publiques (ONG).

## Où est quoi
| Fichier | Rôle |
|---|---|
| `data/feeds.yaml` | tes flux : médias + recherches Google News par pays (`gn_*`) |
| `data/keywords.yaml` | mots qui déclenchent « action de rue » (multilingue) |
| `data/agenda.yaml` | agendas ICS/RSS publics + événements saisis à la main |
| `data/scenes_annuaire.yaml` · `cities.yaml` | annuaire de canaux, villes |
| `backend/main.py` | tout le backend · `frontend/` : l'interface |

## Points d'attention
- Les flux Google News (`gn_*`) sont la source « live » par pays. Pour ceux-là, `robots.txt` est ignoré (`ignore_robots: true`), car Google News RSS est prévu pour les lecteurs de flux. Retire ce réglage si tu préfères tout respecter.
- Flux morts : voir **Système**. Désactive-les avec `enabled: false`. Ajoute un pays en copiant une ligne `gn_*`.
- Le classement par pays dépend du mot-clé et du flux : c'est un indicateur, pas une vérité. Aucune IA.
- **Terrain** est vide tant que tu n'ajoutes pas d'agendas dans `agenda.yaml` (aucune URL inventée).
- Si tu as déjà une base : garde-la, les anciens articles seront re-étiquetés à la prochaine collecte.

## Sauvegarde
Page Système : *Exporter la base* (fichier `.db` avec articles, événements et notes) / *Importer une base*.
Tes fichiers `data/*.yaml` se sauvegardent en les copiant.

## Raccourcis
`Ctrl/Cmd+K` : palette. *Mode calme* coupe les animations.
