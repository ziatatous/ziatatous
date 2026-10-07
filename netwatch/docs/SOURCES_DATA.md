# NETWATCH — sources de données

**Statut de vérification.** L'environnement de construction n'avait pas d'accès réseau sortant : *aucune* URL ci-dessous n'a été interrogée en réel. La colonne « Statut » indique ce qui est à confirmer au premier lancement (page **Système** : chaque collecteur affiche son dernier succès / erreur). Si une source a disparu ou est devenue payante, remplace-la et note-le ici.
Usage strictement **personnel et local**. On stocke titres, chapôs, liens et métadonnées ; le texte intégral n'est extrait qu'à la demande, localement, jamais redistribué ; `robots.txt` respecté ; délai ≥ 1 s entre deux requêtes au même hôte ; aucun contournement de paywall.

| Collecteur | Source / URL | Licence / conditions | Quota | Clé | Fréquence | Statut |
|---|---|---|---|---|---|---|
| `rss` | ~258 flux dans `data/feeds.yaml` | Titres/chapôs/liens pour usage perso | 1 req/s/hôte, GET conditionnels (ETag) | non | 30 min | URLs à tester (Système → Test all feeds) |
| `usgs` | https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson | Domaine public US | souple | non | 20 min | à confirmer |
| `gdacs` | https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP | Libre, citer GDACS | souple | non | 30 min | à confirmer (format JSON) |
| `gdelt` | http://data.gdeltproject.org/gdeltv2/lastupdate.txt + fichiers `export.CSV.zip` (15 min) | Libre, citer GDELT | fichiers statiques | non | 60 min (4 h de fichiers) | à confirmer |
| `acled` | https://api.acleddata.com/acled/read | Gratuit **non commercial**, inscription | selon compte | `ACLED_EMAIL`, `ACLED_KEY` | 6 h | l'API ACLED a évolué (OAuth récent) : vérifier |
| `reliefweb` | https://api.reliefweb.int/v1/disasters | Gratuit, `appname` déclaré | 1000 appels/jour | `RELIEFWEB_APPNAME` | 3 h | à confirmer |
| `quotes` | https://stooq.com/q/d/l/?s=…&i=d | Gratuit, usage perso | souple | non | 15 min | symboles écrits de mémoire ; **Alpha Vantage** (`ALPHAVANTAGE_KEY`, 25 req/jour) réservé en repli, non codé |
| `fred` | https://api.stlouisfed.org/fred/series/observations | Gratuit | 120 req/min | `FRED_API_KEY` | 12 h | à confirmer |
| `ecb` | https://data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata | Libre (citer BCE) | souple | non | 12 h | clés de séries à confirmer |
| `eurostat` | https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m | Libre (CC BY 4.0) | souple | non | 24 h | à confirmer |
| `worldbank` | https://api.worldbank.org/v2/country/…/indicator/… | CC BY 4.0 | souple | non | 3 jours | à confirmer |
| `eurlex` | https://eur-lex.europa.eu/EN/display-feed.rss?rssId=162 | Réutilisation libre | souple | non | 6 h | identifiant de flux à confirmer |
| `boe` | https://www.boe.es/datosabiertos/api/boe/sumario/AAAAMMJJ | Datos abiertos | souple | non | 6 h | à confirmer |
| `legifrance` | https://www.legifrance.gouv.fr/rss/jorf.xml | Licence ouverte (DILA) | souple | non | 6 h | **URL à confirmer** ; l'API PISTE (compte gratuit) est l'alternative robuste, non codée |
| `sanctions` | https://data.opensanctions.org/datasets/latest/sanctions/ (index.json, targets.simple.csv) | CC BY-NC 4.0 (non commercial) | fichiers statiques | optionnelle `OPENSANCTIONS_KEY` | 12 h | à confirmer |
| `wikidata_*` | https://query.wikidata.org/sparql + wbsearchentities | CC0 | 60 s CPU/min, UA obligatoire | non | 3-7 jours | à confirmer |
| `edgar_filings`, `edgar_13f` | https://data.sec.gov/submissions/CIK….json ; https://www.sec.gov/files/company_tickers.json ; Archives 13F | Domaine public | **10 req/s max, User-Agent avec e-mail obligatoire** | `NETWATCH_CONTACT` | 12 h / 7 j | CIK des gestionnaires de `MANAGERS` écrits de mémoire : vérifiés à l'exécution par comparaison du nom renvoyé |
| `lobbying_us` | https://lda.senate.gov/api/v1/filings/ | Domaine public | à confirmer | `LDA_API_KEY` si exigée | 7 j | l'API peut exiger une clé : erreur explicite sinon |
| `lobbying_eu` | Registre de transparence UE (export CSV) | Données ouvertes UE | — | non | 7 j | **import manuel** : dépose l'export dans `data/inbox/*transparency*.csv` |
| `regulators` | flux RSS SEC, FTC, DOJ, CMA, FCA, Commission UE, CNIL, EDPB (`data/corpos.yaml`) | Domaine public / licence ouverte | souple | non | 6 h | URLs à confirmer |
| `rsf` | https://rsf.org/sites/default/files/index_AAAA.csv, ou `data/inbox/rsf*.csv` | CC BY-NC-ND (RSF) — usage perso | — | non | 7 j | **URL non vérifiée** ; télécharger le CSV sur rsf.org/en/index et le déposer dans `data/inbox/rsf.csv` |
| `agenda` | `data/agenda.yaml` + FRED release calendar | — | — | FRED optionnelle | 12 h | dates du YAML écrites de mémoire : **à vérifier** |
| Traduction | Argos Translate (local, MIT) ; DeepL API Free (500 000 car./mois) | — | — | `DEEPL_API_KEY` optionnelle | à la demande | — |
| Dictionnaire | https://en.wiktionary.org/api/rest_v1/page/definition/{mot} | CC BY-SA | politesse | non | à la demande | à confirmer |

## Non couvert (honnêtement)
Votes parlementaires, API Légifrance/PISTE, notes de biais (AllSides, Ad Fontes, Media Bias/Fact Check : licences restrictives, saisie manuelle avec lien dans la fiche), décisions de banques centrales hors flux RSS, assemblées générales d'entreprises (à saisir dans `agenda.yaml`).
