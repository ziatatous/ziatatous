# NETWATCH — feuille de route

## Limites connues de la version 1 (honnêteté)
- **Rien n'a été testé contre les vrais services** pendant la construction (pas d'accès réseau sortant) : les parseurs sont testés sur des fixtures (`backend/tests`), les URL de flux, symboles Stooq, CIK de gestionnaires 13F, formats ACLED/LDA/OpenSanctions sont écrits de mémoire. Premier lancement = vérifier la page Système.
- Fiches sources : faits pré-remplis depuis la connaissance publique, avec URL Wikipédia, **sans date de vérification** (affichées « to verify »). Aucune note de biais n'est pré-remplie (AllSides / Ad Fontes / MBFC : à saisir avec lien).
- Registre de transparence UE : pas d'API stable vérifiée → import d'un export CSV déposé dans `data/inbox/`.
- 13F : lecture d'une liste fixe de gros gestionnaires (partiel).
- Graphe : rendu SVG avec plafond de 250 nœuds ; rendu canvas/WebGL à ajouter pour de gros graphes.
- Clustering TF-IDF : les rapprochements entre langues reposent sur noms propres/chiffres ; `embeddings` recommandé.
- Votes parlementaires, Légifrance (API PISTE), RSF automatique : à compléter.

## Pistes (non codées volontairement)
1. **VPS** (40 Go, peu de RAM, sans domaine) : `--collector-only` + synchronisation de `netwatch.db` (rsync/SSH ou tunnel) vers le PC.
2. **iPhone** : l'interface est responsive + manifest ; ajouter un vrai service worker (offline des dernières données) puis empaquetage Capacitor.
3. **Module IA optionnel** : interface `Analyzer`, résumés/analyses clairement étiquetés « généré », jamais mélangés au contenu humain.
4. Alertes : webhooks / e-mail.
5. Import de listes de flux OPML, export OPML.
6. Détection de citations de sources primaires dans le texte intégral.
