# STATUS — France Transparence

- **Phase courante** : MISSION DÉPLOIEMENT ACCOMPLIE (19/08/2026 soir) — les phases R1-R4 sont closes et vérifiées (décisions 20-24).
- **SITE PUBLIC EN LIGNE** : https://koutakou.github.io/france-transparence/ — statique pré-rendu, reconstruit chaque matin (cron 04:45 UTC ≈ 06:45 Paris) par GitHub Actions ; échec d'ingestion = site de la veille conservé + issue `publication-echec` ; coût 0 €/mois.
- **Vérifié depuis l'extérieur le 19/08** : 23 routes en 200 (TTFB ~0,18 s), zéro cookie, CSP, 301 HTTPS, 14/14 pages sans débordement en 390 px, recherche client OK, cron testé par dispatch réel (4 min 59, ingestion → pytest → deploy), atomicité observée (aucune interruption pendant déploiement). Détail : docs/RAPPORT-MISSION.md §9.
- **Repo public** : https://github.com/koutakou/france-transparence (main). Pousser sur main = republication (~70 s, base en cache). Publication manuelle : `gh workflow run publication` (+ `-f ingestion=true` pour base neuve).
- **Exploitation** : docs/deploiement/RUNBOOK.md (tout depuis zéro) ; décision et limites : docs/deploiement/DECISION.md ; actions humaines optionnelles (domaine, e-mail contact, VPS OVH à vérifier) : docs/ACTIONS-HUMAINES.md.
- **v1 locale intacte** : `make dev` (SSR local, port 3620), `make ingest`, `make test` (150), `make build-static`/`serve-static` (export identique à la prod, sans basePath).
- **Reprise éventuelle** : lire JOURNAL.md (24 décisions) + docs/deploiement/DECISION.md + RUNBOOK.md — le site tourne seul ; toute suite = v2 (pistes : RAPPORT-MISSION §7 + ACTIONS-HUMAINES).
