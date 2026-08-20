# Inventaire machine locale pour le déploiement

Relevé du 2026-08-19 sur le M4 Max (Darwin 25.6.0, arm64). Méthode : `command -v`, versions, statuts d'auth avec timeout, tests réseau réels. Aucune valeur de token/clé/mot de passe n'a été lue ni recopiée — présence et identités seulement.

## CLIs présents

### Plateformes de déploiement (PaaS)

| CLI | Statut |
|---|---|
| flyctl / fly | non installé |
| vercel | non installé |
| railway | non installé |
| render | non installé |
| netlify | non installé |
| wrangler (Cloudflare) | non installé |
| koyeb | non installé |
| heroku | non installé |
| dokku | non installé |
| kamal | non installé |

Aucun CLI PaaS, aucun dossier de config associé (`~/.fly`, `~/.vercel`, `~/.config/railway`, `~/.netlify`, `~/.wrangler`, `~/.heroku` : tous absents). Aucune session PaaS n'existe sur cette machine.

### Cloud / VPS / IaC

| CLI | Version | Statut d'auth |
|---|---|---|
| terraform | v1.14.7 (darwin_arm64) | installé, **non authentifié** : `~/.terraform.d/` ne contient que `checkpoint_cache` et `checkpoint_signature`, pas de `credentials.tfrc.json` |
| hcloud (Hetzner) | — | non installé (`~/.config/hcloud` absent) |
| scw (Scaleway) | — | non installé (`~/.config/scw` absent) |
| ovh / ovhcloud | — | non installé (aucun `~/.ovh*`) |
| aws | — | non installé (`~/.aws` absent, pas de credentials) |
| gcloud | — | non installé (`~/.config/gcloud` absent) |
| az (Azure) | — | non installé (`~/.azure` absent) |
| doctl (DigitalOcean) | — | non installé (`~/.config/doctl` absent) |
| tofu, pulumi, ansible | — | non installés |

`~/.kube/` existe mais est **vide** (aucun contexte Kubernetes).

### GitHub

| CLI | Version | Statut d'auth |
|---|---|---|
| gh | 2.97.0 | **authentifié en tant que `koutakou`** sur github.com (token en keyring, scopes : `admin:public_key`, `gist`, `read:org`, `repo`) |

Deux nuances vérifiées par commandes réelles :
- `gh` est réglé en protocole git **ssh**, or `ssh -T git@github.com` répond `Permission denied (publickey)` : **aucune clé locale n'est enregistrée sur le compte GitHub**. Un `git push` ssh échouerait aujourd'hui.
- Réparable sans humain, deux voies : `gh ssh-key add ~/.ssh/id_ed25519.pub` (le scope `admin:public_key` le permet), ou basculer en https avec `gh auth setup-git` (le scope `repo` suffit).
- Rappel : `~/france-transparence` n'est **pas un dépôt git** à ce jour ; il faudra `git init` + création du repo (que `gh repo create` peut faire immédiatement).

## SSH

### Hôtes configurés (`~/.ssh/config`)

Un seul hôte :

| Host | HostName | User | Port |
|---|---|---|---|
| koutakou.fr | 51.83.96.83 | ubuntu | 24533 |

- Reverse DNS : `ns3147856.ip-51-83-96.eu` → VPS **OVH**.
- **Injoignable au moment du relevé** : timeout de connexion sur les ports 24533, 22, 80 et 443, alors que la sortie réseau générale de la machine fonctionne (contrôle : HTTPS vers un site tiers en 0,08 s). Serveur éteint, résilié, ou IP changée — à vérifier dans le manager OVH avant de compter dessus.
- La config date de sept. 2024.

### Clés présentes (noms de fichiers seulement)

- `id_ed25519` + `id_ed25519.pub` (mars 2025)
- `id_rsa` + `id_rsa.pub` (sept. 2024)
- 3 exports PuTTY/FileZilla : `id_rsa.ppk`, `id_rsa.filezilla.ppk`, `id_rsa.filezilla - Copie.ppk` (sept. 2024)
- Agent ssh : aucune identité chargée au moment du relevé (chargement à la demande possible).
- Aucune des clés n'est acceptée par github.com (testé) ; leur validité côté VPS n'a pas pu être testée (serveur injoignable).

## Docker / conteneurs

| Outil | Version | État |
|---|---|---|
| docker CLI | 28.5.1 | présent |
| Docker Desktop | — | installé (contexte `desktop-linux` actif) mais **daemon éteint** (`Cannot connect to the Docker daemon`) |
| OrbStack (`orb`) | 2.2.3 | installé mais **arrêté** (`orb status` → Stopped) |
| podman, colima | — | non installés |

- `docker context ls` : `default` et `desktop-linux` (courant). Pas de contexte `orbstack` visible tant qu'OrbStack n'a pas tourné.
- `docker run --rm hello-world` **non testé** : aucun daemon actif. Deux moteurs sont disponibles au choix, il suffit de lancer Docker Desktop ou OrbStack manuellement (ou `orb start`).
- Une fois un daemon lancé : builds **linux/arm64 natifs** (machine arm64) ; linux/amd64 via émulation (Rosetta/QEMU), plus lent mais possible avec buildx (inclus dans Docker 28.x).
- `~/.docker/config.json` : `credsStore=desktop`, **aucun registre authentifié** (`auths` vide). Un `docker push` (Docker Hub, ghcr.io…) demanderait un login ; à noter que le token gh actuel n'a pas le scope `write:packages`, donc pas de push ghcr.io avec lui en l'état.

## Variables d'environnement suspectes (noms seulement)

Une seule variable matche `token|key|secret|api|credential|passw`, et elle appartient à un
outil de développement local sans aucun rapport avec le déploiement : elle n'est ni lue par les
pipelines, ni par le build, ni par le serveur. Son nom n'est pas reproduit ici — ce relevé sert à
repérer un secret de plateforme qui aurait fui dans l'environnement, pas à cataloguer l'outillage
du poste.

Aucune variable de plateforme (pas de `FLY_API_TOKEN`, `VERCEL_TOKEN`, `HCLOUD_TOKEN`, `AWS_*`, `SCW_*`, etc.).

## Outils utiles au déploiement

| Outil | Version | Remarque |
|---|---|---|
| node | v24.15.0 | via **fnm** (chemin multishell non stable — pour un cron local, viser un chemin absolu) |
| npm | 12.0.2 | `npx vercel`/`npx wrangler` possibles sans install globale |
| python3 | 3.14.7 (Homebrew) | pip 26.2.1 ; module `sqlite3` OK (SQLite 3.53.4) |
| sqlite3 (CLI) | 3.51.0 | |
| git | 2.55.0 | |
| make | 3.81 (Apple) | vieux — piège `.PHONY` vs pattern rules déjà rencontré sur ce projet |
| rsync | openrsync (protocole 29) | ce n'est **pas** GNU rsync ; compatible pour un déploiement simple, GNU rsync installable via `brew install rsync` si besoin d'options avancées |
| brew | 6.0.18 | permet d'installer n'importe quel CLI manquant en une commande |
| caddy / nginx | — | non installés localement (sans importance pour un déploiement distant) |

## Verdict

**Utilisable immédiatement, sans action humaine :**

- **GitHub** (compte `koutakou`) : seule authentification réelle de la machine. Création de repo, push (après `gh ssh-key add` ou `gh auth setup-git`), Actions — tout est accessible. C'est le socle : n'importe quelle plateforme « connectée à GitHub » pourra ensuite builder depuis le repo.
- **Docker en local** : utilisable pour builder des images dès qu'on démarre Docker Desktop ou OrbStack (déjà installés, un seul geste) ; aucun registre pour pousser les images sans login supplémentaire.

**Configuré mais hors service :**

- **VPS OVH `koutakou.fr` (51.83.96.83:24533, user ubuntu)** : le seul serveur que la machine connaisse. Injoignable au relevé (aucun port ne répond). S'il est simplement éteint, le rallumer en ferait la cible de déploiement la plus directe (clés ssh locales disponibles) ; s'il est résilié, il ne compte pas.

**Tout le reste demande création de compte + installation de CLI :**

Fly.io, Railway, Render, Netlify, Vercel, Cloudflare, Koyeb, Heroku, Hetzner, Scaleway, OVH (API), AWS, GCP, Azure, DigitalOcean : rien d'installé, rien d'authentifié, aucune trace de compte. Chaque CLI s'installe en une commande brew/npm, mais le login initial exigera un humain (navigateur/email).

**Note d'adéquation à l'app** (Next.js + SQLite 447 Mo + cron Python) : il faut un disque persistant et un vrai processus long — donc VPS, ou PaaS à volumes (Fly.io, Railway, Render disk). Les plateformes serverless pures (Vercel, Netlify) sont inadaptées au SQLite fichier + cron en l'état.
