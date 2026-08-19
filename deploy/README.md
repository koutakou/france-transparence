# deploy/ — infrastructure de déploiement

Le site public est un **export statique Next.js servi par GitHub Pages**, reconstruit
chaque matin par GitHub Actions (`.github/workflows/publication.yml`). Décision et
alternatives : `docs/deploiement/DECISION.md`. Exploitation de bout en bout :
`docs/deploiement/RUNBOOK.md`.

| Fichier | Rôle |
|---|---|
| `creer-repo-github.sh` | Création rejouable : clé SSH de déploiement dédiée, repo public, remote, push initial, label d'alerte, activation Pages en mode workflow. Idempotent. |
| `../.github/workflows/publication.yml` | Cron 04:45 UTC : ingestion (base neuve) → pytest → build statique → contrôles de santé → déploiement Pages atomique. Échec = pas de déploiement (site de la veille conservé) + issue `publication-echec`. Les pushes sur main rebuilder le site avec la dernière base en cache. |

- URL publique : https://koutakou.github.io/france-transparence/
- Déclenchement manuel : `gh workflow run publication --repo koutakou/france-transparence` (ou l'onglet Actions).
- Aucun secret requis : tout fonctionne avec le `GITHUB_TOKEN` automatique du workflow.
