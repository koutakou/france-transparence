# RUNBOOK — exploitation de France Transparence

Public : l'exploitant (ou un repreneur) qui doit tout faire depuis zéro, sans autre contexte.
Décision d'hébergement et alternatives : [DECISION.md](DECISION.md). Ce qui exige un humain : [../ACTIONS-HUMAINES.md](../ACTIONS-HUMAINES.md).

**Deux chaînes cohabitent, et il faut savoir laquelle fait quoi** — c'est le point que ce document doit rendre évident :

| | Ce qui publie le site | Ce qui valide le code |
|---|---|---|
| Où | Le **serveur dédié** (scripts `ft-*`, minuteries systemd) | **GitHub Actions** (`.github/workflows/publication.yml`) |
| Quand | Tous les jours ~**05:17 Paris** | Cron **04:45 UTC**, plus chaque push et chaque proposition de fusion sur `main` |
| Effet d'un échec | L'ancienne version reste servie, une alerte part | Une issue `publication-echec` s'ouvre ; **le site n'est pas concerné** |
| Effet d'un succès | Le site public change | Rien n'est mis en ligne (seule la page de redirection part sur Pages, depuis `main`) |

Un run CI rouge n'est **jamais** une panne du site ; un site figé n'est **jamais** visible dans GitHub Actions. Ne cherchez pas la cause de l'un dans les journaux de l'autre.

## 1. Architecture d'exploitation

```
42 sources open data officielles (data.gouv.fr, DILA, AN, Sénat, HATVP, DGFiP, OFGL, CNCCFP, Eurostat, DREES, INSEE, Direction du Budget…) — catalogue vivant : `/donnees`
        │  re-téléchargées à chaque cycle — rien n'est hébergé chez nous
        ▼
SERVEUR DÉDIÉ (Scaleway Dedibox, Ubuntu 22.04) — ft-deploy.timer, tous les jours 05:17 Paris
        git pull → ft-localiser (55 contrôles d'identité de déploiement, ne modifie rien)
        → make ingest (base SQLite neuve) → make test (pytest) → build export (FT_EXPORT=1)
        → contrôles de santé → pré-compression zopfli → BASCULE ATOMIQUE du lien « current »
        ▼
nginx sert /srv/france-transparence/current/ — https://francetransparence.fr
        aucun process Node en production : que des fichiers déjà écrits, déjà compressés
```

Propriétés à connaître :

- **Tout ou rien.** Le lien `current` ne bascule qu'après les contrôles de santé et la pré-compression. Une étape en échec = **rien n'est publié**, la version de la veille continue d'être servie sans interruption, et `ft-alerte` notifie. La bascule est un `ln -sfnT` puis un `mv -Tf` — un `rename(2)` : aucun visiteur ne voit d'état intermédiaire.
- **Contrôles de santé du site généré** : `index.html` présent et titré, `404.html` présent, `api/meta.json` parsable et porteur de `meta.genere_le`, **≥ 900 fiches d'élus**, export **< 950 Mo**, et **aucune URL `koutakou.github.io` résiduelle**.
- **Retour arrière sans rebuild** : les **5** dernières releases sont conservées sous `/srv/france-transparence/releases/`, `ft-rollback` rebascule le lien en quelques secondes.
- **La fraîcheur affichée reste vraie par construction** : elle est calculée depuis `meta_sources` de la base réellement déployée. Un cycle raté ne dégrade pas l'honnêteté du site, il la laisse constater un jour de retard.
- **Coût** : abonnement au serveur dédié + nom de domaine. Ce n'est plus gratuit ; c'est le prix des en-têtes HTTP maîtrisés et du domaine propre (voir DECISION.md).

## 2. URLs et accès

| Quoi | URL |
|---|---|
| Site public | https://francetransparence.fr |
| Ancienne adresse (page de redirection seule) | https://koutakou.github.io/france-transparence/ |
| Dépôt (public) | https://github.com/koutakou/france-transparence |
| Runs de validation CI | https://github.com/koutakou/france-transparence/actions/workflows/publication.yml |
| Issues d'échec CI | https://github.com/koutakou/france-transparence/issues?q=label%3Apublication-echec |

Deux accès distincts, à ne pas confondre :

- **Le serveur**, en SSH, avec les droits root pour les scripts `ft-*` (l'arbre de build appartient à l'utilisateur `ftweb`). C'est le seul accès qui permet de changer ce qui est en ligne.
- **Le compte GitHub `koutakou`**, seul admin du dépôt. Le token OAuth de `gh` n'a pas le scope `workflow` (il ne peut pas pousser de modification sous `.github/workflows/`) ; le push passe donc par une clé SSH dédiée sans passphrase, le remote étant en SSH :

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_ft_deploy -o IdentitiesOnly=yes" git push
```

Clé absente (machine neuve) : rejouer `deploy/creer-repo-github.sh` (§ 6), qui la régénère et l'enregistre.

**La documentation d'exploitation détaillée vit sur le serveur**, dans `/srv/france-transparence/doc/` : `EXPLOITATION.md` en est la porte d'entrée (ce qui tourne, publication, diagnostic, TLS, sécurité, sauvegardes, audience), complétée par des documents spécialisés (performance, fraîcheur, sauvegardes, incidents). Ce RUNBOOK-ci en est le résumé public : en cas de divergence, la doc du serveur fait foi, parce qu'elle est révisée en même temps que les scripts.

## 3. Opérations courantes (sur le serveur)

### Publier maintenant

```bash
ft-deploy                  # cycle complet : git pull → contrôles → ingestion → tests → build → bascule
ft-deploy --sans-ingest    # rebuild sans ré-ingérer (réutilise la base existante) — livrer un correctif d'app
ft-deploy --sans-pull      # rejoue un build sans toucher au dépôt
```

Un `git push` sur `main` ne met **plus rien** en ligne par lui-même : la production se met à jour au cycle suivant, ou immédiatement par un `ft-deploy` lancé à la main. C'est le changement d'habitude le plus important par rapport à l'ancienne chaîne GitHub Pages.

Journal : `/var/log/france-transparence/deploiement.log` (le script y écrit lui-même — un cycle lancé à la main y laisse aussi sa trace), et `journalctl -u ft-deploy`.

### Revenir à une version précédente

```bash
ft-rollback                     # liste les releases disponibles, ne change rien
ft-rollback 20260820-150748     # bascule current vers cette release
ft-rollback --precedente        # bascule vers la release juste avant l'actuelle
```

Instantané, sans rebuild : c'est une bascule de lien symbolique, atomique comme celle de `ft-deploy`.

### Diagnostiquer

```bash
ft-etat              # tableau de bord : révision servie, fraîcheur, dernière sonde, TLS, services, disque
ft-sonde --verbeux   # rejoue les 10 contrôles de disponibilité et les détaille
ft-fraicheur         # fraîcheur RÉELLE des 42 sources amont (--json, --silencieux)
ft-alerte --test     # vérifie que le canal de notification fonctionne vraiment
```

**Ne rechargez jamais nginx par `systemctl reload nginx` seul** : nginx peut refuser une configuration à chaud, journaliser un `[emerg]` et **conserver silencieusement l'ancienne** — pendant que `nginx -t` réussit et que systemd affiche « Reloaded ». Utilisez `ft-nginx-reload`, qui relit `error.log` après le rechargement et vous dit si un `restart` est nécessaire.

### Minuteries en place

| Heure | Unité | Rôle |
|---|---|---|
| toutes les 5 min | `ft-sonde.timer` | disponibilité (10 contrôles) |
| 03:30 | `ft-sauvegarde.timer` | sauvegarde locale |
| 04:12 | `ft-audience.timer` | rapport d'audience quotidien |
| 04:15 | `ft-sauvegarde-distante.timer` | copie hors-site chiffrée |
| **05:17** | **`ft-deploy.timer`** | **reconstruction et publication** |
| 06:30 | `ft-fraicheur.timer` | fraîcheur des sources amont |

Toutes en `Persistent=true` : un déclenchement manqué (serveur éteint) est rattrapé au démarrage.

## 4. Diagnostic d'un échec de publication

Où regarder, dans l'ordre : `ft-etat` → `tail -n 40 /var/log/france-transparence/deploiement.log` → `journalctl -u ft-deploy -n 50`. L'étape en échec est nommée dans le journal.

Quatre familles de panne :

1. **Contrôle d'identité de déploiement** (`ft-localiser`, sortie 4) — l'arbre qui allait être construit n'annonce pas la bonne adresse, le bon hébergeur ou le bon responsable de traitement.
   Conséquence : aucune. Le build n'a pas eu lieu, le site de la veille est servi.
   Conduite : lire les contrôles KO — chacun dit quoi faire. **La correction se fait en amont** (dépôt), ou par variables d'environnement de build (`NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_HEBERGEUR_*`). Le script ne corrige rien, et c'est voulu : ce qui est publié doit être ce qui est versionné.
2. **Source amont cassée** (ingestion ou tests) — un producteur de données a changé une URL, un format, ou est indisponible.
   Conséquence : **aucune** — le site reste sur la veille, et la page [/donnees](https://francetransparence.fr/donnees/) continue d'afficher la vraie fraîcheur de chaque source.
   Conduite : identifier le pipeline fautif ; reproduire avec `make ingest-<source>` ; si l'amont est juste indisponible, ne rien faire (le cycle réessaie demain) ; si le format a changé, corriger `pipelines/ingest_<source>.py` et ses tests, ouvrir une proposition de fusion (la CI la vérifiera), fusionner. La CI de 04:45 UTC voit souvent ces pannes **avant** le serveur : c'est tout son intérêt.
3. **Échec build ou contrôles de santé** — régression de code, ou site généré invalide (< 900 fiches, ≥ 950 Mo, `koutakou.github.io` résiduel…).
   Conduite : reproduire en local (`make build-static`), corriger, fusionner ; si le coupable est un commit récent, `ft-rollback` remet immédiatement le site d'avant pendant que la correction se prépare.
4. **Problème machine ou réseau** (disque plein, inodes, nginx tombé, certificat) — `ft-sonde` le voit dans les 5 minutes et alerte ; `ft-etat` le résume.

**Un échec de la CI GitHub Actions ne relève d'aucune de ces familles** : il ouvre ou commente une issue `publication-echec` et signale un problème de code ou de source amont à corriger avant que le serveur ne le rencontre. Le site en ligne, lui, n'en dépend pas.

## 5. Rollback

Deux rollbacks distincts, pour deux problèmes distincts :

- **Le site est mauvais maintenant** (données amont aberrantes, régression visuelle passée entre les mailles) → `ft-rollback` : retour en quelques secondes à une release précédente, sans rebuild, sans réseau. C'est le geste d'urgence.
- **Le code est mauvais** → `git revert <sha>` + push sur `main`. Le serveur reprendra ce code au cycle suivant (ou tout de suite avec `ft-deploy`). Jamais de force-push sur `main`.

**Il n'y a pas de rollback des données, par principe** : les sources amont font foi ; le site publie ce que l'open data officiel dit aujourd'hui. Si une source publie une donnée aberrante, le recours est de corriger ou désactiver le pipeline concerné (et de le documenter), pas de maquiller un état antérieur. Le serveur conserve tout de même deux générations compressées de la base — non contre la perte (elle se reconstruit par `make ingest`), mais précisément pour pouvoir revenir en arrière quand une source amont a publié un jeu corrompu, cas où la reconstruction ne ferait que réimporter la corruption.

## 6. Reconstruction totale depuis zéro

### Le projet, sur n'importe quelle machine

Prérequis : `python3.14`, Node.js ≥ 24, `make`, `git`.

```bash
git clone https://github.com/koutakou/france-transparence.git
cd france-transparence
make venv          # crée .venv (requests, duckdb, pytest)
make ingest        # reconstruit data/france.db — ~1 Go téléchargé
make test          # suite pytest complète (hors réseau : .venv/bin/pytest pipelines/tests -m 'not reseau')
make app-install   # npm install dans app/
make build-static  # export statique → app/out/ (FT_EXPORT=1, lit data/france.db)
make serve-static  # sert app/out/ sur http://localhost:3620/
```

Le build local produit le **même site que la production** : plus de `basePath`, le site vit à la racine. Pour publier ailleurs, poser `NEXT_PUBLIC_SITE_URL` (et `NEXT_PUBLIC_HEBERGEUR_*` pour les mentions légales) au build — aucune source n'est à modifier. Mode développement : `make dev` (même port 3620).

### Le serveur

Ce dépôt ne contient pas la configuration du serveur : elle vit sur la machine (nginx, unités systemd `ft-*`, scripts `/usr/local/bin/ft-*`, `/etc/france-transparence/`) et c'est **elle** qui est sauvegardée hors-site, chiffrée — le reste (site, export, `node_modules`, releases, cache `data/raw/`, base) est intégralement régénérable par `ft-deploy`. Procédure de restauration : `SAUVEGARDES.md` dans `/srv/france-transparence/doc/`, à exécuter depuis la machine qui détient la clé privée `age` — **jamais** depuis le serveur, qui ne détient que la clé publique. C'est ce qui fait qu'un root distant compromis ne peut pas relire les sauvegardes.

### Le dépôt GitHub

```bash
bash deploy/creer-repo-github.sh
```

Idempotent (chaque étape teste avant d'agir) : génère la clé SSH `~/.ssh/id_ed25519_ft_deploy` si absente et l'enregistre sur le compte, crée le dépôt public si absent, pose le remote et pousse `main`, crée le label `publication-echec`, active GitHub Pages en mode « GitHub Actions ». **Ce script ne met plus le site en ligne** : ce que Pages reçoit désormais est la page de redirection de `pages-redirection/`.

## 7. Surveillance

- **Automatique, toutes les 5 minutes** : `ft-sonde` vérifie 10 points — point de santé, page d'accueil et son titre, jours restants sur le certificat, espace disque, inodes, cohérence du lien `current`, **âge des données générées** (c'est lui qui détecte qu'une reconstruction quotidienne a cessé de fonctionner), `nginx.service` actif, `ft-deploy.timer` actif, absence de plantages répétés de workers nginx. Chaque passage écrit une ligne dans `sonde.log`.
- **Quotidien, une commande** : `ft-etat` — révision servie, issue du dernier déploiement, fraîcheur, TLS, services, sauvegardes, disque, le tout recoupé entre plusieurs sources pour signaler un journal incomplet plutôt que de rassurer à tort.
- **Fraîcheur réelle des sources** : `ft-fraicheur` compare, pour chacune des 42 sources, la date de la donnée la plus récente en base (`meta_sources.date_donnees`) à un seuil calibré par source. C'est le complément indispensable de la sonde : le site peut être fraîchement régénéré chaque nuit alors qu'une source amont a cessé de publier depuis des semaines.
- **Alertes** : `ft-alerte` est le point d'extension unique — il écrit **toujours** dans le journal systemd en priorité `err` (`journalctl -t ft-alerte -p err`), puis pousse vers un webhook si l'un est configuré. Un échec du webhook n'est jamais remonté à l'appelant : le journal reste le canal de dernier recours.
- **Moniteur public de fraîcheur** : la page `/donnees` affiche la date réelle de chaque source — le healthcheck lisible par n'importe qui, sans accès au serveur.
- **CI** : un run rouge sur `publication.yml` ouvre une issue `publication-echec`. Activer les notifications GitHub sur le dépôt (Watch → Custom → Issues) pour être prévenu.
- **Le trou de couverture, à connaître** : la sonde interroge le site **depuis la machine elle-même**. Une panne de DNS, de routage ou de datacenter la laisse parfaitement satisfaite. Seule une supervision externe comble ce trou.

## 8. Sécurité

- **En-têtes HTTP servis par nginx** — c'est ce que l'hébergement précédent ne permettait pas : `Strict-Transport-Security`, `Content-Security-Policy` (en en-tête, donc `frame-ancestors` réellement appliqué), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`. Redirection 301 HTTP→HTTPS, certificat renouvelé automatiquement (certbot, hook passant par `ft-nginx-reload` — sinon un certificat renouvelé pourrait n'être jamais pris en compte).
- **Aucun process applicatif exposé** : pas de Node en production, pas de base accessible depuis le réseau, pas de formulaire. La surface d'attaque du site se réduit à nginx servant des fichiers.
- **Dépôt public sans secret** — la règle à maintenir : aucun token, aucune clé, aucun `.env` commité. Les secrets d'exploitation vivent sur le serveur en `0600` (`/etc/france-transparence/`) et n'ont pas à être recopiés dans un document, un journal ou un ticket. La CI, elle, fonctionne avec le `GITHUB_TOKEN` automatique, aux permissions minimales déclarées en tête de `publication.yml`.
- **Clé SSH de déploiement** `~/.ssh/id_ed25519_ft_deploy` : dédiée, sans passphrase — si la machine de travail est perdue ou compromise, révoquer la clé sur https://github.com/settings/keys. Le site continue de se publier tout seul : le serveur tire le dépôt, il ne dépend pas de cette clé.
- **Sauvegardes chiffrées hors-site** en clé publique `age` : la clé de déchiffrement ne vit jamais sur le serveur.
- **Aucune donnée visiteur collectée** : site 100 % statique, zéro cookie, zéro traceur, aucun compte, aucun formulaire. Les journaux nginx contiennent des adresses IP — donnée personnelle — traitées et documentées comme telles dans les pages légales du site.
