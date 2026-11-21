# STATUS, France Transparence

État au 21/11/2026. L'historique et les motifs sont dans JOURNAL.md, les gestes à faire hors du dépôt dans docs/ACTIONS-HUMAINES.md.

- **Site public** : https://francetransparence.fr, export statique Next.js servi par nginx sur un serveur dédié (Scaleway Dedibox, Ubuntu 22.04), sans processus Node. Reconstruit chaque nuit vers 05:17, heure de Paris, par `ft-deploy` (minuterie `ft-deploy.timer`), en tout ou rien : un échec laisse la version précédente en ligne. Description publique de l'exploitation : docs/deploiement/RUNBOOK.md.
- **Dernier cycle vérifié** : 21/11/2026, release `20261121-052022`, révision `8f44c4b`, en 11 min 20 s. `npm test` 233/233, budget de poids tenu, 1 027 fiches d'élus, sitemap complet, 23 redirections d'élus sur 23.
- **Incident du 08 au 20/11/2026, clos** : le site est resté figé douze jours, puis a été réparé le 20/11 (JOURNAL.md, décision 55). Les correctifs fusionnés le 11/11 sont en ligne depuis le cycle du 20/11 au soir.
- **Contenu** : 11 onglets (`app/src/components/MainNav.tsx`), plus `/alertes`, `/comprendre`, `/elus/annuaire/` et les fiches hors navigation. 44 sources (`meta_sources`, seuils de `app/src/lib/fraicheur.ts`). 31 pipelines (`make pipelines`).
- **Promesse sur les sources** (décision du propriétaire du 20/11) : sources publiques officielles, plus quelques consolidations reconnues et créditées. S1, S7 (Datan) et S31 sont étiquetées sur `/donnees`.
- **Pile** : Python 3.14 pour les pipelines (CI, et venv du serveur en 3.14.10), dépendances figées en `==`. Next.js 16.4.6, React 19.3.1, TypeScript 6, better-sqlite3 13.2, Node 24 en CI.
- **CI** (`.github/workflows/publication.yml`, job `construire`, check requis sur `main`) : ne publie rien. Elle valide chaque proposition de fusion et rejoue chaque jour à 04:45 UTC la chaîne complète dans une base neuve. Le job `tests-python-3-10` rejoue les tests des pipelines sous Python 3.10. Le job `veiller` tient les issues `redirections-301` et `cron-echeance`. Les issues d'alerte sont assignées au propriétaire du dépôt.
- **Vigie externe** (`.github/workflows/vigie.yml`, 11:23 UTC) : lit le site du dehors et tient les issues `site-fige` et `site-echeances`. #137 et #138 sont fermées depuis la réparation du 20/11.
- **Dépendances** : Dependabot #152 et #153 fusionnées le 21/11. #133 et #134 fermées le 20/11.
- **Points ouverts** :
  - docs/ACTIONS-HUMAINES.md, section du 20 et 21/11/2026 : compte des fiches sans `annuaire` à la ligne 290 de `publication.yml` (le jeton n'a pas le scope `workflow`), journées d'audience partielles, contrainte Python 3.10 à revoir maintenant que le serveur est en 3.14.
  - à vérifier au cycle du 22/11 : `npm ci` installe better-sqlite3 13.2 sur le serveur.
  - données d'élus : doublons et rattachements à relire dans un lot dédié.
- **Reprise** : lire JOURNAL.md, docs/deploiement/RUNBOOK.md et docs/ACTIONS-HUMAINES.md. `docs/RAPPORT-MISSION.md` est un journal daté des 19 et 20/08 : il se lit au passé.
