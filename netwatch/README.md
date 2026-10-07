# NETWATCH

Terminal personnel de veille mondiale — esthétique cyberpunk, usage professionnel.
Tourne **en local sur ton PC**, pour **un seul utilisateur**. Gratuit, sans abonnement, sans IA rédactionnelle :
on affiche ce que les journalistes et les institutions ont écrit, avec leur source, et des statistiques simples pour comparer.

> Les trois principes : chaque élément visuel porte une donnée réelle · aucun texte généré par IA · chaque information est sourcée.

---

## 1. Installation (une seule fois)

Il te faut deux outils gratuits :

| Outil | Version | Où le trouver |
|---|---|---|
| **Python** | 3.12 ou plus récent | https://www.python.org/downloads/ (sous Windows, coche « Add python.exe to PATH ») |
| **Node.js** | 20 ou plus récent (nécessaire **une seule fois** pour fabriquer l'interface) | https://nodejs.org/ |

Pour vérifier, ouvre un terminal et tape `python --version` (ou `python3 --version`) puis `node --version`.

## 2. Lancement (une seule commande)

- **Windows** : double-clique sur `start.bat` (ou tape `start.bat` dans un terminal ouvert dans ce dossier).
- **macOS / Linux** : `./start.sh`

Le premier lancement installe tout (2 à 3 minutes). Les suivants démarrent en quelques secondes.
Le navigateur s'ouvre sur http://127.0.0.1:8000. Pour arrêter : `Ctrl+C` dans le terminal (ou ferme la fenêtre).

Options utiles : `./start.sh --no-collect` (consulter sans collecter), `./start.sh --rebuild` (reconstruire l'interface).

## 3. Premier démarrage

1. Une séquence de 2-3 secondes affiche l'état réel du système (n'importe quelle touche la passe).
2. La collecte démarre toute seule en arrière-plan. Les premiers articles arrivent en quelques minutes.
3. Va dans **Système** : tu vois chaque collecteur (dernier succès, erreurs, volume), la taille de la base, et le bouton « Collect everything now ».
4. Onglet **RSS feeds → Test all feeds** : teste les ~250 flux, marque les flux morts. Colle une URL de remplacement si besoin.
   (Les URL ont été écrites de mémoire et **n'ont pas pu être testées** depuis l'environnement de construction : ce test est important.)
5. Optionnel : copie `.env.example` en `.env` et ajoute les clés gratuites (voir plus bas).

Si le PC était éteint, au démarrage NETWATCH **rattrape** ce qui a été manqué (flux RSS, séismes, marchés…).

## 4. Utilisation

| Module | À quoi ça sert |
|---|---|
| **Briefing** | La page du matin : ce qui a bougé depuis ta dernière visite, sujets classés par *ampleur* de couverture (sources × pays × langues), signaux faibles, textes officiels, agenda 72 h. Bouton « Marquer comme lu ». |
| **Topics / Vue croisée** | Un événement, toutes les narrations : colonnes par pays / propriété / langue, vocabulaire distinctif (statistique), chronologie de couverture (qui parle en premier, qui se tait), sources primaires. |
| **Sources** | Fiche détaillée de chaque média : propriétaire jusqu'au bénéficiaire final (arbre), financement, statut étatique, liberté de la presse (RSF), notes de tiers (avec avertissement), historique, statistiques. **Chaque champ a un lien de référence.** |
| **World** | Globe 3D / carte 2D (GDELT, ACLED, USGS, GDACS), dossiers pays, France / Espagne / UE. |
| **Corpos** | ~65 grandes entreprises : cours, actionnaires (13F), lobbying, amendes, allers-retours public/privé, médias détenus. |
| **Vitals** | Marchés, taux, inflation, chômage, dette — avec contexte sur 10 ans et seuils d'alerte. |
| **Power net** | Graphe des connexions entre personnes, entreprises, médias, États. Chemin le plus court entre deux entités. Chaque lien est cliquable et sourcé. |
| **Official** | Journal officiel (FR), BOE (ES), EUR-Lex (UE), sanctions. |
| **Alerts** | Trois niveaux (INFO cyan, VIGILANCE jaune, CRITIQUE rouge), règles lisibles et paramétrables. |
| **Agenda · Watch · Search** | Calendrier, liste de suivi + chronologies d'un sujet, recherche plein texte filtrable. |
| **Languages** | Lecture Original / Traduit / Bilingue, clic sur un mot (définition, prononciation, vocabulaire), révision espacée, mode immersion, langue du jour. |
| **System** | Santé des collecteurs, flux RSS, sauvegarde / restauration, clés. |

Raccourcis : `Ctrl/Cmd+K` palette de commandes (pays, entreprise, personne, source, sujet, langue, action) · `?` aide · `/` recherche · `.` mode calme · `g` puis `b s m c v p o a g w f l y` pour naviguer.

**Code couleur (jamais décoratif)** : jaune = vigilance / action possible · rouge = critique, baisse forte, conflit, média d'État · cyan = donnée, lien, info neutre · vert = normal, hausse, collecte OK, propriété indépendante · magenta = personnes, entités, réseau de pouvoir. La légende est dans l'aide (`?`) et la page Design.

**Mode calme** (`.` ou bouton dans la barre latérale) : coupe toutes les animations. Respecte aussi `prefers-reduced-motion`. Lignes de balayage désactivables, sons désactivés par défaut.

## 5. Clés API gratuites (toutes optionnelles)

Rien n'est obligatoire pour démarrer. Voir `.env.example` :

| Clé | Pour | Inscription (gratuite) |
|---|---|---|
| `ACLED_EMAIL` + `ACLED_KEY` | Conflits et manifestations (World) | https://acleddata.com/register/ |
| `FRED_API_KEY` | Séries US (taux, CPI, chômage) + calendrier de publications | https://fredaccount.stlouisfed.org/apikeys |
| `RELIEFWEB_APPNAME` | Catastrophes ReliefWeb | https://apidoc.reliefweb.int/ |
| `OPENSANCTIONS_KEY` | Sanctions (usage non commercial) | https://www.opensanctions.org/api/ |
| `LDA_API_KEY` | Lobbying américain, si le service l'exige | https://lda.senate.gov/api/ |
| `DEEPL_API_KEY` | Traduction DeepL (sinon Argos local) | https://www.deepl.com/pro-api (offre Free) |
| `NETWATCH_CONTACT` | Ton e-mail, envoyé dans le User-Agent (exigé par SEC EDGAR) | — |

Sans clé : GDELT, USGS, GDACS, Stooq, ECB, Eurostat, Banque mondiale, Wikidata, SEC EDGAR, EUR-Lex, BOE, RSS.

## 6. Traduction locale (optionnel)

```
.venv/bin/pip install argostranslate        # Windows : .venv\Scripts\pip install argostranslate
.venv/bin/python -c "import argostranslate.package as p; p.update_package_index(); [p.install_from_path(x.download()) for x in p.get_available_packages() if x.to_code in ('en','fr','es') ]"
```
(Cela télécharge plusieurs centaines de Mo.) Toute traduction est affichée avec le badge « machine translation ».

Regroupement multilingue plus précis (optionnel) : `pip install sentence-transformers` puis `NETWATCH_CLUSTER_MODE=embeddings` dans `.env`. Aucun texte n'est généré : le modèle sert uniquement à détecter que deux articles parlent du même événement.

## 7. Tes données

- Base : `data/netwatch.db` (SQLite). Rétention configurable (`.env` : texte intégral 30 j, métadonnées 365 j par défaut).
- **Sauvegarde** : Système → Backup & keys → « Export settings » (liste de suivi, vocabulaire, sources corrigées, règles) ; « Copy database » copie la base dans `backups/`.
- Fichiers que tu peux éditer : `data/feeds.yaml` (flux), `data/sources/*.yaml` (fiches), `data/corpos.yaml` (entreprises), `data/agenda.yaml` (agenda).
- Les fiches sources pré-remplies indiquent pour chaque champ l'URL justificative ; elles sont marquées **« to verify »** tant qu'aucune date de vérification n'est enregistrée.

## 8. En cas de problème

- « Python/Node introuvable » : réinstalle-les en cochant l'option PATH, puis rouvre le terminal.
- Page blanche : dans le terminal du lancement, regarde les messages d'erreur ; essaie `./start.sh --rebuild`.
- Un collecteur est rouge dans **Système** : le message d'erreur est affiché ; les autres continuent de fonctionner.
- Sous Windows, `start.bat` n'a pas pu être testé par l'auteur : si le premier lancement échoue, copie le message d'erreur.

## 9. Pour les développeurs

```
backend/   FastAPI + SQLite (FTS5) + APScheduler   → cd backend && ../.venv/bin/python -m pytest
frontend/  Vite + React + TypeScript + Tailwind    → cd frontend && npm run dev   (proxy vers :8000)
```
Voir `docs/ARCHITECTURE.md`, `docs/SOURCES_DATA.md`, `docs/ROADMAP.md`. Mode collecteur seul (futur VPS) : `python -m app.main --collector-only`.

Licence des polices : Rajdhani, Orbitron, JetBrains Mono, Inter (SIL OFL), embarquées via @fontsource. Aucun asset de CD Projekt Red.
