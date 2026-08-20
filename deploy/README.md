# deploy/ — infrastructure de déploiement

**Depuis le 20/08/2026, ce répertoire ne publie plus le site.** Le site public
(https://francetransparence.fr) est un export statique servi par nginx sur un serveur
dédié, reconstruit et basculé chaque matin par le script serveur `ft-deploy` — lequel
vit sur le serveur, pas dans ce dépôt. Décision et alternatives :
`docs/deploiement/DECISION.md`. Exploitation de bout en bout :
`docs/deploiement/RUNBOOK.md`.

Ce qui reste ici concerne le **dépôt GitHub** et la **CI**, pas la mise en ligne :

| Fichier | Rôle |
|---|---|
| `creer-repo-github.sh` | Création rejouable du dépôt public : clé SSH de déploiement dédiée, repo, remote, push initial, label d'alerte, activation de GitHub Pages en mode workflow. Idempotent. À rejouer seulement si le dépôt doit être recréé de zéro. Il décrit encore l'ancienne mise en ligne du site sur Pages : depuis la migration, ce que Pages reçoit n'est plus le site mais la page de redirection de `pages-redirection/`. |
| `../.github/workflows/publication.yml` | **Ne déploie plus le site.** Valide la chaîne complète chaque jour (cron 04:45 UTC : ingestion de tous les pipelines dans une base neuve → pytest → build statique → contrôles de santé) dans un environnement indépendant du serveur, et vérifie chaque proposition de fusion avant qu'elle n'atteigne `main`. Seule la page de redirection de `pages-redirection/` part sur GitHub Pages, et uniquement depuis `main` (job `deployer`, condition `github.ref == 'refs/heads/main'`). Tout échec hors proposition de fusion ouvre ou commente une issue `publication-echec`. |
| `../pages-redirection/` | La page servie à l'ancienne adresse GitHub Pages : canonique + rafraîchissement méta vers le domaine. C'est le seul endroit du dépôt où l'ancienne URL doit encore figurer. |

- URL publique : https://francetransparence.fr
- Déclencher la validation CI à la main : `gh workflow run publication --repo koutakou/france-transparence` (ou l'onglet Actions). Cela **ne met pas le site à jour** : la production se reconstruit au cycle suivant de `ft-deploy`, ou immédiatement par un `ft-deploy` lancé sur le serveur.
- Aucun secret requis côté CI : tout fonctionne avec le `GITHUB_TOKEN` automatique du workflow.
