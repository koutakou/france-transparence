# RUNBOOK — exploitation de France Transparence

Public : l'exploitant (ou un repreneur) qui doit tout faire depuis zéro, sans autre contexte.
Décision d'hébergement et alternatives : [DECISION.md](DECISION.md). Actions nécessitant un humain : [../ACTIONS-HUMAINES.md](../ACTIONS-HUMAINES.md).

## 1. Architecture d'exploitation

```
25 sources open data officielles (data.gouv.fr, DILA, AN, Sénat, HATVP, DGFiP, OFGL, CNCCFP…)
        │  re-téléchargées à chaque run — rien n'est hébergé chez nous
        ▼
GitHub Actions — workflow « publication » (runner éphémère ubuntu-latest, cron 04:45 UTC quotidien)
        make ingest (base SQLite neuve ~448 Mo) → make test (pytest) → next build (export statique)
        → contrôles de santé (index, meta.json, ≥ 900 fiches, taille < 950 Mo)
        ▼  déploiement ATOMIQUE (tout le site remplacé d'un coup, ou rien)
GitHub Pages (CDN Fastly, HTTPS) — https://koutakou.github.io/france-transparence/
```

Propriétés à connaître :

- **Échec de n'importe quelle étape = aucun déploiement** : le site de la veille reste servi tel quel, et une issue `publication-echec` est ouverte (ou commentée si déjà ouverte).
- **Aucune machine à entretenir, aucun secret** : le runner est éphémère, la base est reconstruite à chaque ingestion, tout fonctionne avec le `GITHUB_TOKEN` automatique.
- Trois déclencheurs (`.github/workflows/publication.yml`) : cron 04:45 UTC (06:45 Paris l'été — après le lot JO ~00h30 et les builds DECP) ; push sur `main` (rebuild avec la dernière base en cache Actions, ingestion complète si cache vide) ; déclenchement manuel avec ingestion forçable.
- Coût : 0 €/mois (repo public → Pages et minutes Actions gratuits).

## 2. URLs et accès

| Quoi | URL |
|---|---|
| Site public | https://koutakou.github.io/france-transparence/ |
| Repo (public) | https://github.com/koutakou/france-transparence |
| Runs du workflow | https://github.com/koutakou/france-transparence/actions/workflows/publication.yml |
| Issues d'échec | https://github.com/koutakou/france-transparence/issues?q=label%3Apublication-echec |
| Trafic (Insights) | https://github.com/koutakou/france-transparence/graphs/traffic |

Accès : tout est piloté par le **compte GitHub `koutakou`** (seul admin). En ligne de commande, `gh` doit être authentifié sur ce compte (`gh auth status`).

Pour **pousser** : le token OAuth de `gh` n'a pas le scope `workflow` (il ne peut pas pousser de modification sous `.github/workflows/`) ; le push passe donc par la **clé SSH dédiée `~/.ssh/id_ed25519_ft_deploy`** (sans passphrase, enregistrée sur le compte sous le titre `france-transparence-deploy`), le remote étant en SSH (`git@github.com:koutakou/france-transparence.git`) :

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_ft_deploy -o IdentitiesOnly=yes" git push
```

Clé absente (machine neuve) : rejouer `deploy/creer-repo-github.sh` (§6), qui régénère et enregistre la clé.

## 3. Opérations courantes

### Déclencher une publication manuelle

```bash
# Publication complète (ingestion neuve, ~25-60 min) :
gh workflow run publication --repo koutakou/france-transparence

# Rebuild du site sans ré-ingérer (réutilise la dernière base en cache, ~10 min) :
gh workflow run publication --repo koutakou/france-transparence -f ingestion=false
```

Équivalent web : repo → onglet **Actions** → workflow **publication** → bouton **Run workflow** (case « Ingestion complète » cochée par défaut).

### Suivre un run

```bash
gh run list  --repo koutakou/france-transparence --workflow publication --limit 5
gh run watch <run-id> --repo koutakou/france-transparence        # suit en direct jusqu'à la fin
gh run view  <run-id> --repo koutakou/france-transparence --log-failed   # logs des étapes échouées
```

### Lire et fermer une issue d'échec

Le workflow ouvre une issue `publication-echec` au premier échec, puis **commente la même issue** pour les échecs suivants — il ne la ferme jamais lui-même.

```bash
gh issue list  --repo koutakou/france-transparence --label publication-echec
gh issue view  <numéro> --repo koutakou/france-transparence --comments
# Une fois un run redevenu vert :
gh issue close <numéro> --repo koutakou/france-transparence -c "Rétabli par le run <url du run vert>"
```

### Pousser un changement de code

```bash
git add -p && git commit -m "…"
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_ft_deploy -o IdentitiesOnly=yes" git push
```

Tout push sur `main` déclenche une republication **avec la dernière base en cache** (données du matin) : idéal pour livrer un correctif d'app sans attendre le cron ni payer une ingestion. Si le cache est vide (évincé après ~7 jours sans usage, ou tout premier run), le workflow fait l'ingestion complète tout seul.

## 4. Diagnostic d'un échec

Où regarder : issue `publication-echec` → lien vers le run → job rouge (`construire`, `deployer`) → première étape rouge ; ou directement `gh run view <run-id> --log-failed`.

Trois familles de panne, reconnaissables à l'étape rouge :

1. **Source amont cassée** (étapes « Ingestion complète » ou « Tests pipelines ») — un producteur de données a changé une URL, un format, ou est indisponible.
   Conséquence : **aucune** — le site reste sur la veille, et la page [/donnees](https://koutakou.github.io/france-transparence/donnees/) continue d'afficher la vraie fraîcheur de chaque source (elle est calculée depuis `meta_sources` de la base réellement déployée : l'honnêteté ne se dégrade pas, elle se constate).
   Conduite : lire le log pour identifier le pipeline fautif ; reproduire en local avec `make ingest-<source>` (les 13 sources sont listées dans le README) ; si l'amont est juste indisponible, ne rien faire (le cron réessaie demain) ou relancer manuellement plus tard ; si le format a changé, corriger `pipelines/ingest_<source>.py` (et ses tests), pousser.
2. **Échec build/app** (étapes `npm ci`, « Build statique », « Contrôles de santé ») — régression de code ou site généré invalide (< 900 fiches, ≥ 950 Mo…).
   Conduite : reproduire en local (`make build-static` avec une base fraîche), corriger, pousser ; si le coupable est un commit récent → rollback (§5).
3. **Quota/infra GitHub** (runner perdu, timeout 150 min, étapes cache/upload/deploy-pages, erreurs 5xx) — rien à corriger dans le projet.
   Conduite : vérifier https://www.githubstatus.com/ puis relancer : `gh run rerun <run-id> --repo koutakou/france-transparence --failed` (ne rejoue que les jobs échoués) ; si ça persiste, attendre le cron suivant — le site, lui, reste en ligne.

## 5. Rollback

**Revenir au code d'avant** = revert + push (jamais de force-push sur `main`) :

```bash
git revert <sha-fautif>
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_ft_deploy -o IdentitiesOnly=yes" git push
```

Le push déclenche un nouveau build avec la dernière base en cache : le site revient à l'ancien code **avec les données du jour** — c'est le comportement voulu.

**Ce qu'un re-run ne fait PAS** : `gh run rerun <ancien-run-réussi>` rejoue le workflow au même commit (même code, re-run possible ~30 jours), mais l'étape d'ingestion **re-télécharge les sources du moment** — ce n'est pas un snapshot des données de ce jour-là. Personne ne conserve les bases passées : le cache Actions ne garde que les dernières (évincées après ~7 jours sans usage et par le plafond de 10 Go/repo).

**Il n'y a pas de rollback des données, par principe** : les sources amont font foi ; le site publie ce que l'open data officiel dit aujourd'hui. Si une source amont publie une donnée aberrante, le recours est de corriger ou désactiver le pipeline concerné (et de le documenter), pas de restaurer un état antérieur.

## 6. Reconstruction totale depuis zéro (machine neuve)

Prérequis : `python3.14`, Node.js ≥ 24, `make`, `git`, `gh` authentifié sur le compte `koutakou` (`gh auth login`, scopes `repo` et `admin:public_key`).

```bash
git clone https://github.com/koutakou/france-transparence.git
cd france-transparence
make venv          # crée .venv (requests, duckdb, pytest)
make ingest        # reconstruit data/france.db (~448 Mo) — 5-10 min en local, ~1 Go téléchargé
make test          # 150 tests pytest (exclure le réseau : .venv/bin/pytest pipelines/tests -m 'not reseau')
make app-install   # npm install dans app/
make build-static  # export statique → app/out/ (FT_EXPORT=1, lit data/france.db)
make serve-static  # sert app/out/ sur http://localhost:3620/
```

NB : en local le build se fait **sans** `NEXT_PUBLIC_BASE_PATH` → site à la racine ; en prod il vit sous `/france-transparence/`. Pour le mode développement : `make dev` (même port 3620).

**Re-créer l'hébergement** (repo supprimé, compte à remonter, ou première fois) :

```bash
bash deploy/creer-repo-github.sh
```

Le script est **idempotent** (chaque étape teste avant d'agir) : génère la clé SSH `~/.ssh/id_ed25519_ft_deploy` si absente et l'enregistre sur le compte, crée le repo public si absent, pose le remote et pousse `main`, crée le label `publication-echec`, active GitHub Pages en mode « GitHub Actions » (`build_type=workflow`). Le push initial déclenche la première publication ; le site est en ligne à la fin du premier run vert (le temps du run, l'URL répond 404 — normal).

## 7. Surveillance

- **Quotidien (une commande)** : `gh run list --repo koutakou/france-transparence --workflow publication --limit 3` — un `success` daté du matin = tout va bien.
- **Passif** : les échecs ouvrent/commentent une issue → activer les notifications GitHub sur le repo (Watch → Custom → Issues) pour être prévenu par e-mail sans rien scruter.
- **Moniteur public de fraîcheur** : la page `/donnees` du site affiche la date réelle de chaque source (table `meta_sources`) — c'est le healthcheck lisible par n'importe qui : si le site a un jour de retard, ça s'y lit.
- **Limites à surveiller** :
  - Taille du site : plafond Pages ~1 Go ; le workflow **échoue de lui-même à ≥ 950 Mo** (contrôle de santé) ; actuellement ~232 Mo — la marge est large, la taille est loggée à chaque run (« Taille du site : N Mo »).
  - Bande passante Pages : ~100 Go/mois (limite *soft*). GitHub n'expose pas de compteur exact de bande passante Pages : **Insights → Traffic** (URL en §2) donne l'ordre de grandeur des visites, et GitHub prévient par e-mail en cas d'approche de la limite.
  - Minutes Actions : illimitées sur repo public — non surveillé.
- **Migration VPS** : si le trafic dépasse durablement Pages (ou pour un domaine + vrais headers HTTP), suivre [docs/ACTIONS-HUMAINES.md §4](../ACTIONS-HUMAINES.md) (Hetzner recommandé, architecture cible dans `plateformes.md` §4).

## 8. Sécurité

- **Repo public sans secret** — audité avant publication (cf. DECISION.md) ; la règle à maintenir : aucun token, aucune clé, aucun `.env` commité. Tout le workflow fonctionne avec le **`GITHUB_TOKEN` automatique**, aux permissions minimales déclarées en tête de `publication.yml` : `contents: read`, `pages: write`, `id-token: write`, `issues: write`. Rien à faire tourner, rien à renouveler.
- **Clé SSH de déploiement** `~/.ssh/id_ed25519_ft_deploy` : dédiée à ce projet, **sans passphrase** — si la machine locale est compromise ou perdue, révoquer la clé `france-transparence-deploy` sur https://github.com/settings/keys (le site continue de se publier tout seul ; seule la capacité de push est touchée, et `deploy/creer-repo-github.sh` recrée une clé neuve).
- Le compte `koutakou` est le seul point de contrôle : le protéger (2FA) protège tout.
- **Aucune donnée visiteur collectée** : site 100 % statique, zéro cookie, zéro analytics, aucun formulaire, aucun process serveur à nous ; les visiteurs ne parlent qu'au CDN de GitHub Pages.
