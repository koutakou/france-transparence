# Plateformes d'hébergement — état de l'art vérifié (19/08/2026)

Recherche menée le **19 août 2026** par WebSearch + lecture réelle des pages officielles (WebFetch).
Chaque chiffre est daté et sourcé ; les pages bloquées (rendu JavaScript) sont signalées et croisées avec une seconde source, marquée *(tierce)*. Prix **HT sauf mention contraire** ; les mensuels dérivés d'un tarif horaire sont calculés sur 730 h et marqués « ≈ ».

*État constaté le 19/08/2026. Les tarifs, quotas et limites relevés ici décrivent ce jour-là et ont dérivé depuis : aucun n'est à reprendre sans re-vérification sur la page officielle citée. Ce document reste consultable comme comparatif daté ; la question de l'hébergement a depuis été tranchée en faveur d'un serveur dédié ([DECISION.md](DECISION.md)).*

Contexte marché important découvert pendant la recherche : **2026 est une année de hausses générales** (tension mondiale sur la RAM). Hetzner a relevé ses prix le 15/06/2026 (CX/CAX +30-40 %, CPX/CCX ×2,4+), OVH a fait évoluer sa gamme VPS en mars 2026. Les prix ci-dessous sont les prix **post-hausse**, pas ceux des comparatifs 2024-2025 qui traînent sur le web.

---

## 1. Contraintes à héberger (rappel)

| Contrainte | Valeur |
|---|---|
| App | Next.js 16.3.1 SSR (React 19.2.8, Tailwind 4), port 3620, Node ≥ 20 |
| Module natif | **better-sqlite3** : doit compiler (node-gyp + C++) ou disposer d'un prebuilt. Le README officiel confirme « Prebuilt binaries are available for major platforms/architectures » ([github.com/WiseLibs/better-sqlite3](https://github.com/WiseLibs/better-sqlite3)) → OK Linux glibc x86-64/arm64, **impossible en edge/workers** |
| Donnée | SQLite ~450 Mo sur **disque persistant**, ouverte en lecture seule par l'app |
| Ingestion | Job quotidien Python 3.14 (requests + duckdb, `make ingest`), 30-60 min, télécharge des centaines de Mo, écrit une **nouvelle** db puis bascule atomique (`rename` → exige **le même filesystem** que la db servie) |
| RAM | pic duckdb 2-4 Go → machine 4 Go = juste, **8 Go = confortable** |
| Disque | ≥ 15 Go (db + téléchargements temporaires + node_modules + venv) |
| Trafic | faible à modéré, public France/Europe |
| Critères | simplicité d'exploitation > coût > performance ; **UE de préférence** ; minimiser les actions humaines |

Conséquence structurante : la bascule atomique par `rename()` impose que **le job d'ingestion et l'app voient le même disque**. Toute plateforme où le cron est isolé du volume de l'app est disqualifiée d'office.

---

## 2. Tableau comparatif

| Plateforme | Offre exacte | Prix/mois | RAM / CPU / disque | Région UE | CLI / provisioning | Volume persistant | Cron long OK ? | CB obligatoire ? | Verdict (1 ligne) |
|---|---|---|---|---|---|---|---|---|---|
| **Hetzner Cloud** | **CX33** (x86 partagé) | **8,49 € HT** (+ IPv4 ~0,50 €) | 8 Go / 4 vCPU / 80 Go NVMe local, 20 To trafic | Falkenstein, Nuremberg, Helsinki | `hcloud` officiel + cloud-init (user-data 32 KiB) → 100 % scriptable après création du compte | Disque local inclus (+ Volumes en option) | Oui (VPS nu : systemd timer, aucune limite) | Oui (CB/PayPal/virement) + **vérif. d'identité possible** à l'inscription | **N°1 : le plus de machine par euro, provisioning entièrement API** |
| Hetzner Cloud | CX23 (x86) | 5,49 € HT (+ IPv4) | 4 Go / 2 vCPU / 40 Go, 20 To | idem | idem | idem | Oui | idem | Variante mini : 4 Go = duckdb au chausse-pied |
| Hetzner Cloud | CAX21 (ARM Ampere) | 10,49 € HT (+ IPv4) | 8 Go / 4 vCPU / 80 Go, 20 To | idem | idem (prebuilt better-sqlite3 arm64 OK) | idem | Oui | idem | ARM désormais **plus cher** que le x86 équivalent (CX33) : sans intérêt ici |
| **OVHcloud** | **VPS-2** (gamme 2026, EPYC) | **7,21 € HT / 8,65 € TTC** (engagement 12 mois) | 8 Go / 4 vCores / 75 Go NVMe, **trafic illimité** 1 Gbit/s, anti-DDoS + backup 1 j inclus | **Gravelines, Strasbourg** 🇫🇷 (+ Beauharnois CA) | API OVH mais **pas de cloud-init sur la gamme VPS** (demande au roadmap GitHub, oct. 2025) ; commande = panier ; clés SSH pré-installables | Disque local inclus | Oui (VPS nu) | Oui (checkout classique, engagement pour ce prix) | **N°2 : souveraineté FR maximale, mais provisioning le moins scriptable du trio** |
| OVHcloud | VPS-1 | 3,81 € HT / 4,57 € TTC (12 mois) | 4 Go / 2 vCores / 40 Go, 500 Mbit/s illimité | idem | idem | idem | Oui | idem | Le moins cher du marché vérifié, mais 4 Go + 40 Go = limites atteintes vite |
| **Scaleway** | **DEV1-M** | ≈ 14,75 € HT (0,0202 €/h) **+ IPv4 ≈ 3,65 €** (0,005 €/h) | 4 Go / 3 vCPU / 40 Go NVMe local | **Paris** (PAR-1/2/3), Amsterdam, Varsovie | `scw` officiel (`scw instance server create …`) + cloud-init (console/CLI/API) | Local inclus + Block Storage ≈ 0,095 €/Go/mois (5K IOPS) | Oui (VPS nu) | Oui | **N°3 : français et 100 % scriptable, mais ~2× le prix Hetzner à specs inférieures** |
| Scaleway | PRO2-XXS | ≈ 40,95 € HT (0,0561 €/h) + IPv4 | 8 Go / 2 vCPU (block storage en sus) | idem | idem | Block storage payant | Oui | Oui | 8 Go RAM au prix fort : hors budget pour ce projet |
| **Fly.io** | shared-cpu-1x 2 GB + volume 20 Go | ≈ **$14** ($11,11 machine + $3 volume à $0,15/Go + egress EU $0,02/Go) | 2 Go / 1 vCPU partagé / volume 20 Go | **Paris (cdg)**, Amsterdam, Francfort (société US) | `flyctl`, Dockerfile complet → better-sqlite3 OK | Oui mais **1 volume = 1 machine** (« a volume can be attached to only one Machine ») et doc officielle : « Always provision at least two volumes per app » | Pas de cron géré : supercronic **dans** la machine app (le volume mono-machine l'impose) | **Oui en pratique** : trial 7 j / 2 h de VM / machines coupées après 5 min → inutilisable sans CB | Le meilleur des PaaS Docker, mais US, CB obligatoire, volume fragile mono-machine |
| **Railway** | Hobby + service 2 Go/1 vCPU + 20 Go | ≈ **$33-43** (RAM $10/Go/mois ! + vCPU $20 + volume $0,15/Go + $5 plan incl. $5 d'usage) | à la carte | Amsterdam (« EU West Metal », `europe-west4-drams3a`) | Config as code, cron natif (min 5 min, pas de limite de durée documentée) | Oui ($0,15/Go/mois) | Oui | **Oui** : « Railway requires the use of a post-paid card » | RAM à $10/Go : 3-4× le prix d'un VPS complet — écarté sur le coût |
| **Render** | Standard $25 (2 Go/1 CPU) + disk | $25 + disque (prix/Go **non affiché** dans les docs ; page pricing JS-bloquée) | 2 Go / 1 CPU | **Francfort** (docs officielles) | Blueprint YAML, Docker OK | Oui, mais désactive les déploiements zero-downtime | Cron : ≤ 12 h, min $1/mois, **MAIS « Cron jobs can't provision or access a persistent disk »** | Oui pour tout service payant (free : 750 h, spin-down 15 min, sans disque) | **Disqualifié structurellement** : le cron ne peut pas écrire le disque de l'app → pas de bascule atomique |
| **Koyeb** 🇫🇷 | Standard medium (volumes interdits sur eco/free) | $21,43 (2 Go/2 vCPU) + volume | 2 Go / 2 vCPU / 20 Go SSD éphémère | **Paris (PAR)**, Francfort (FRA) — mais volumes **fra/was uniquement** | CLI koyeb, Docker OK | **Public preview** : « only suitable for testing », 1-10 Go max, downtime au redeploy, scale=1 | Workers OK | Free tier sans CB (1 instance 0,1 vCPU/512 Mo, scale-to-zero 1 h) | Française et prometteuse, mais **volumes pas production-ready en 2026** — à revoir dans un an |
| **Clever Cloud** 🇫🇷 | Node XS + FS Bucket | XS 1 Go/1 vCPU ≈ 16 €/mois *(tierce : europeanstack.com ; simulateur officiel JS-bloqué)* | 1 Go / 1 vCPU (2 Go → nettement plus) | **Paris** | clever-tools, git push | **FS Buckets réseau** : « not optimized for high-performance applications », flag `:async` = risque de corruption, **indisponible pour les apps Docker** | Crons supportés | Compte + moyen de paiement | Français et sympathique, mais **FS réseau incompatible avec better-sqlite3 mmap** — écarté techniquement |
| **Upsun** (Platform.sh) | Projet + 0,5 CPU/2 Go/15 Go | ≈ **60-70 €** (projet 9 € + user 10 € + CPU 0,033 €/h + RAM 0,013 €/Go/h + stockage 0,49 €/Go/mois) | à la carte, mounts persistants déclarés | Régions UE (facturation EUR) | Config YAML, git push, trial 15 j **sans CB** | Oui (mounts) | **Oui : crons timeout par défaut/max 86 400 s (24 h)**, min 5 min | Non pour le trial, oui ensuite | Le seul PaaS où tout marcherait techniquement… à 6-7× le prix du VPS — écarté sur le coût |

Notes de lecture :
- **Hetzner** : prix officiels du 15/06/2026, « All prices are excluding VAT », colonnes « Monthly price excl. IPv4 » ([docs.hetzner.com — Price Adjustment 15 June 2026](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)). Specs et 20 To de trafic croisés via [costgoat.com/pricing/hetzner](https://costgoat.com/pricing/hetzner) *(tierce, relevé 02/08/2026 — la page hetzner.com/cloud est en rendu JS)* et [northflank.com](https://northflank.com/blog/hetzner-cloud-server-price-increases) (CX23 : 3,99 € → 5,49 €). IPv4 ~0,50 €/mois *(tierce : onedollarvps.com « IPv6-only saves €0.50/month » — non retrouvé sur une page officielle lisible)*.
- **OVH** : [ovhcloud.com/fr/vps/](https://www.ovhcloud.com/fr/vps/) (lu le 19/08/2026 : VPS-1 3,81 €/4,57 €, VPS-2 7,21 €/8,65 €, VPS-3 10,40 €/12,48 €, VPS-4 8 vCores/24 Go/200 Go 19,96 €/23,95 €, « prix = engagement annuel », trafic illimité, anti-DDoS, sauvegarde 1 j). Localisations FR : [ovhcloud.com/en/vps/vps-france/](https://www.ovhcloud.com/en/vps/vps-france/). Cloud-init VPS : demande ouverte au roadmap ([github.com/ovh/infrastructure-roadmap #383](https://github.com/ovh/infrastructure-roadmap/issues/383)) — le VPS s'installe par template + clé SSH, pas par user-data.
- **Scaleway** : [scaleway.com/en/pricing/virtual-instances/](https://www.scaleway.com/en/pricing/virtual-instances/) (DEV1-S 0,00898 €/h, DEV1-M 0,0202 €/h, DEV1-L 0,04284 €/h, PLAY2-NANO 0,02754 €/h, PRO2-XXS 0,0561 €/h ; « List prices include egress » ; IPv4 exclue). IPv4 flexible : [pricing/network/](https://www.scaleway.com/en/pricing/network/) (0,005 €/h). Block storage : [pricing/storage/](https://www.scaleway.com/en/pricing/storage/) (5K : 0,000130 €/Go/h). Disque local DEV1-M 40 Go *(tierce : vpsbenchmarks/holori — la datasheet officielle n'était pas lisible en fetch)*. CLI : [github.com/scaleway/scaleway-cli](https://github.com/scaleway/scaleway-cli) ; cloud-init : [docs officielles](https://www.scaleway.com/en/docs/instances/how-to/use-cloud-init/).
- **Fly.io** : [fly.io/docs/about/pricing/](https://fly.io/docs/about/pricing/) (shared-cpu-1x 2 Go : $0,0154/h soit $11,11/mois ; volumes « $0.15/GB per month » ; egress Europe $0,02/Go). Trial : [fly.io/docs/about/free-trial/](https://fly.io/docs/about/free-trial/) (« 2 hours of machine runtime or 7 days », « automatically stop after running for 5 minutes », inscription sans CB mais rien ne tourne durablement sans). Volumes : [fly.io/docs/volumes/overview/](https://fly.io/docs/volumes/overview/). Régions : [fly.io/docs/reference/regions/](https://fly.io/docs/reference/regions/) (cdg Paris ✓). Les allocations gratuites historiques (3 VM) ont disparu en 2024.
- **Railway** : [docs.railway.com/reference/pricing/plans](https://docs.railway.com/reference/pricing/plans) (Hobby $5 incl. $5 ; RAM « $10 / GB / month » ; vCPU $20 ; volume $0,15/Go ; egress $0,05/Go ; « post-paid card » requise). Régions : [docs.railway.com/reference/regions](https://docs.railway.com/reference/regions). Crons : [docs.railway.com/reference/cron-jobs](https://docs.railway.com/reference/cron-jobs) (min 5 min, exécution sautée si la précédente tourne encore).
- **Render** : régions : [render.com/docs/regions](https://render.com/docs/regions) (Francfort ✓). Disques : [render.com/docs/disks](https://render.com/docs/disks) (paid only, snapshot 24 h, « Adding a disk … prevents zero-downtime deploys »). Crons : [render.com/docs/cronjobs](https://render.com/docs/cronjobs) (« Render stops an active run after 12 hours », « **Cron jobs can't provision or access a persistent disk** », min $1/mois). Tiers d'instances *(tierce : kuberns.com, 2026 — page pricing officielle JS-bloquée)* : Free 512 Mo/0,1 CPU, Starter $7 512 Mo/0,5, Standard $25 2 Go/1, Pro $85 4 Go/2 ; free : 750 h/mois, spin-down après 15 min.
- **Koyeb** : instances : [koyeb.com/docs/reference/instances](https://www.koyeb.com/docs/reference/instances) (free 0,1 vCPU/512 Mo fra+was ; eco-medium $10,71 1 vCPU/2 Go ; medium $21,43 2 vCPU/2 Go). Volumes : [koyeb.com/docs/reference/volumes](https://www.koyeb.com/docs/reference/volumes) (« public preview … only suitable for testing », 1-10 Go, fra/was, pas d'eco/free, downtime au redeploy). Régions : [koyeb.com/docs/reference/regions](https://www.koyeb.com/docs/reference/regions) (PAR, FRA, WAS, SIN, TYO).
- **Clever Cloud** : FS Buckets : [clever.cloud/developers/doc/addons/fs-bucket/](https://www.clever.cloud/developers/doc/addons/fs-bucket/) (« FS Buckets are not optimized for high-performance applications », `:async` = risque de corruption, indisponibles pour les apps Docker). Tarifs nano 6 €/XS 16 € *(tierce : [europeanstack.com](https://europeanstack.com/software/clever-cloud) — le [pricing officiel](https://www.clever.cloud/pricing/) est un simulateur JS illisible en fetch)*.
- **Upsun** : [upsun.com/pricing/](https://upsun.com/pricing/) (projet 9 €/mois, user 10 €/mois, CPU partagé 0,033 €/h, RAM 0,013 €/Go/h, stockage 0,49 €/Go/mois, trial 15 j « No credit card required »). Crons : [developer.upsun.com/docs/configure-apps/image-properties/crons](https://developer.upsun.com/docs/configure-apps/image-properties/crons) (timeout défaut/max 86 400 s).
- **Hetzner, création de compte** : moyen de paiement requis et vérification possible (« a copy of a valid government-issued ID » ou « an advance payment with your own credit card ») — [docs.hetzner.com — Fraud prevention FAQ](https://docs.hetzner.com/general/security-and-identify/fraud-prevention-faq/). À anticiper : c'est la seule étape potentiellement « humaine » du parcours Hetzner.

Aucun des treize fournisseurs examinés n'offre de chemin **totalement** sans action humaine : il faut partout créer un compte avec un moyen de paiement. La bonne lecture du critère : choisir la plateforme où l'humain n'intervient **qu'une fois** (inscription), après quoi tout — création, réinstallation, redimensionnement, DNS, firewall — passe par API/CLI. C'est le cas de Hetzner (`hcloud`) et Scaleway (`scw`), pas d'OVH VPS (panier + pas de cloud-init).

---

## 3. Pourquoi le serverless pur convient mal (preuves)

Quatre murs successifs, chacun suffisant à lui seul :

**Mur n°1 — le module natif et le filesystem.** better-sqlite3 est un addon C++ qui ouvre un fichier local. Cloudflare Workers exécute des isolates V8 sans filesystem ni addons natifs, avec **128 Mo de RAM par isolate** et un bundle max de **10 Mo gzip (payant, 3 Mo en free ; 64 Mo avant compression)** — [developers.cloudflare.com/workers/platform/limits/](https://developers.cloudflare.com/workers/platform/limits/). Une db de 450 Mo n'entre nulle part dans ce modèle. L'alternative maison, D1 (SQLite managé, **10 Go max en payant, 500 Mo en free** — [developers.cloudflare.com/d1/platform/limits/](https://developers.cloudflare.com/d1/platform/limits/)), accueillerait les 450 Mo, mais imposerait de réécrire toute la couche d'accès (API D1 ≠ better-sqlite3) et d'héberger l'ingestion duckdb ailleurs : ce n'est plus héberger l'app, c'est un autre projet.

**Mur n°2 — la taille de déploiement.** Sur Vercel, « the maximum uncompressed size is **250 MB** » pour une fonction Node (« These limits are enforced by AWS ») — [vercel.com/docs/functions/limitations](https://vercel.com/docs/functions/limitations). Embarquer la db dans le bundle est donc impossible en standard. La beta « Large functions » monte à 5 Go (Fluid + Active CPU), mais alors chaque rafraîchissement quotidien des données = un **redéploiement complet** de 450 Mo+, et le filesystem des fonctions reste éphémère et non partagé entre invocations : aucune bascule atomique possible.

**Mur n°3 — la durée des crons.** L'ingestion dure 30-60 min.
- Vercel : un cron invoque une fonction, donc hérite de ses limites — **Hobby : 300 s max** ; Pro : 800 s max, 1 800 s (30 min) en « extended maximum » **beta** ([limitations](https://vercel.com/docs/functions/limitations)). Et côté planification : « Hobby accounts are limited to cron jobs that run **once per day** » avec précision « Per-hour (±59 min) » — [vercel.com/docs/cron-jobs/usage-and-pricing](https://vercel.com/docs/cron-jobs/usage-and-pricing). 60 min de duckdb n'y tiennent jamais ; 30 min seulement en beta payante.
- Netlify : les Background Functions plafonnent à **15 minutes** (« run for up to 15 minutes ») — [docs.netlify.com/build/functions/background-functions/](https://docs.netlify.com/build/functions/background-functions/). Insuffisant.
- Cloudflare : un cron trigger payant a droit à **30 s de CPU (intervalle < 1 h) ou 15 min de CPU (intervalle ≥ 1 h)** — [workers/platform/limits](https://developers.cloudflare.com/workers/platform/limits/). Et pas de Python/duckdb de toute façon.

**Mur n°4 — le coût/l'architecture des 450 Mo.** Même en contournant tout (db sur un object storage, fonction qui la télécharge…), chaque cold start devrait rapatrier 450 Mo avant la première requête, ou payer un cache : latence et coût absurdes pour un projet civique à trafic modéré, là où un VPS à 8,49 € sert la db en mmap local.

Divers vérifiés en passant : Vercel Hobby limite la mémoire à 2 Go/1 vCPU (Pro 4 Go/2 vCPU) et l'upload CLI à 100 Mo de sources (Hobby) — [vercel.com/docs/limits](https://vercel.com/docs/limits). La limite de bundle Netlify (50 Mo zippé, héritée d'AWS Lambda) n'a pas pu être reconfirmée sur les docs 2026 réorganisées ; elle est cohérente avec la limite AWS que Vercel cite explicitement. Le timeout synchrone Netlify n'apparaît plus que via la page dépréciée « Lambda compatibility » (10 s en streaming) — non bloquant pour la conclusion, les murs 1 à 3 suffisent.

**Conclusion serverless : écarté.** Ce n'est pas une question de prix mais de modèle : pas de disque persistant partagé entre un job long et un serveur SSR, pas de module natif en edge, crons trop courts.

---

## 4. Conteneur vs systemd nu (pour UN petit serveur unique)

Les deux fonctionnent ; la question est le coût d'exploitation sur la durée.

**Option A — systemd nu** (recommandée ici) :
- `france-transparence.service` : `ExecStart=node .next/standalone/server.js`, `Environment=PORT=3620`, `Restart=always`, durcissement gratuit (`DynamicUser=` ou user dédié, `ProtectSystem=strict`, `ReadWritePaths=/srv/ft/data`, `MemoryMax=`).
- `ft-ingest.timer` + `ft-ingest.service` (`Type=oneshot`, `ExecStart=make ingest`, `Nice=10`, `MemoryMax=5G`) : un timer systemd remplace cron avec journalisation (`journalctl -u ft-ingest`), `OnCalendar=*-*-* 05:17:00`, `Persistent=true` (rattrape un run manqué après reboot).
- La bascule `rename()` est triviale : app et job partagent `/srv/ft/data` sur le même ext4 — atomicité POSIX garantie, l'app rouvre la db en lecture seule (SIGHUP ou watch + réouverture, déjà notre modèle).
- better-sqlite3 : prebuilt téléchargé au `npm ci` sur la machine (glibc x64/arm64), zéro cross-compilation.
- Ce qu'on perd : la reproductibilité d'image et la portabilité instantanée vers un PaaS.

**Option B — Docker** (compose, 2 services : `web` en Dockerfile multi-stage Next standalone, `ingest` en image Python lancée par un timer systemd hôte via `docker compose run ingest`, volume commun monté) :
- Gains réels : build reproductible, rollback = retag d'image, parité dev/prod, et surtout **portabilité** — le jour où Fly/Koyeb devient pertinent, on redéploie tel quel.
- Coûts réels sur un serveur unique : un démon de plus à maintenir et mettre à jour, rotation des logs à configurer, pièges classiques (UID/GID sur le volume partagé, `--init` pour les zombies, i/o overlay2 à éviter pour la db → volume bind obligatoire), et la RAM du démon sur une petite machine.

**Avis motivé** : pour un serveur unique et une équipe qui vit dans le shell, **systemd nu gagne sur le critère n°1 (simplicité d'exploitation)** — moins de couches entre un incident et son diagnostic, timers > cron, sandboxing natif. Le bon compromis : déployer en systemd nu **et garder un Dockerfile multi-stage à jour dans le repo** (coût marginal, testé en CI), comme police d'assurance de portabilité. Passer à Docker le jour où il y a un 2e serveur ou un 2e projet colocalisé.

---

## 5. TOP 3 recommandé

Critères appliqués : simplicité d'exploitation > coût > performance ; UE de préférence ; action humaine réduite au minimum (elle est partout ≥ 1 : l'inscription).

### 🥇 N°1 — Hetzner Cloud **CX33**, Falkenstein ou Helsinki — **8,49 €/mois HT** (+ IPv4 ~0,50 €)
4 vCPU / **8 Go RAM** / 80 Go NVMe / 20 To de trafic. C'est l'option désignée :
- **Simplicité** : une seule machine, systemd nu, aucune pièce mobile de plateforme. Après l'inscription (unique moment humain, prévoir l'éventuelle vérification d'identité — FAQ officielle), tout est API : `hcloud server create --type cx33 --image ubuntu-24.04 --location fsn1 --user-data-from-file cloud-init.yml` livre une machine provisionnée de bout en bout (Node 20, Python 3.14, venv, service + timer) en une commande rejouable.
- **Coût** : 8 Go de RAM — duckdb à l'aise pendant que Next sert — pour le prix d'un VPS 4 Go ailleurs ; le CX23 à 5,49 € reste le plan B si l'on accepte de serrer duckdb dans 4 Go.
- **Dimensionnement** : 80 Go ≫ 15 Go requis ; 20 To de trafic = ~44 000 téléchargements complets de la db par mois, insensible au succès du projet.
- Limites assumées : Allemagne/Finlande, pas France (UE et RGPD : oui ; cocorico : non) ; prix HT hors IPv4 ; hausse de juin 2026 déjà intégrée.

### 🥈 N°2 — OVHcloud **VPS-2**, Gravelines ou Strasbourg — **7,21 €/mois HT (8,65 € TTC)**, engagement 12 mois
4 vCores / 8 Go / 75 Go NVMe / trafic illimité, anti-DDoS et sauvegarde quotidienne inclus. **Le choix souveraineté** : data center français, entreprise française, idéal pour l'image d'un projet de transparence de la vie politique française — et le seul du trio avec backup géré inclus. Ce qui le relègue derrière Hetzner : provisioning nettement moins scriptable (pas de cloud-init sur la gamme VPS — confirmé par le roadmap public OVH —, commande via panier, engagement annuel pour ce prix), soit exactement le critère n°1. Si la souveraineté FR devient le critère dominant (probable pour la communication du projet), il passe n°1 en acceptant ~20 min de setup manuel de plus, une fois.

### 🥉 N°3 — Scaleway **DEV1-M**, Paris — **≈ 18,40 €/mois HT** (14,75 € instance + 3,65 € IPv4)
3 vCPU / 4 Go / 40 Go NVMe local. Français **et** scriptable (`scw` + cloud-init) : le meilleur des deux mondes sur le papier, mais deux fois le prix du CX33 pour moitié moins de RAM et de disque après les hausses 2026 — la RAM à 4 Go oblige à surveiller le pic duckdb. Retenu comme n°3 parce que c'est le seul chemin **Paris + 100 % API** ; à reconsidérer si Scaleway rebaisse ou si un PLAY2/PRO2 promo passe sous ~12 €.

**Mention** : Fly.io (~$14/mois, région cdg Paris, tout-Docker) est le meilleur PaaS pour ce profil si l'on veut absolument du PaaS — mais société US, CB obligatoire (trial de 2 h de VM inexploitable), volume mono-machine qui force l'ingestion dans la machine app, et la doc officielle elle-même recommande deux volumes par app. À trafic modéré, le VPS le bat sur tous nos critères.

**Décision proposée** : CX33 Hetzner + systemd nu + Dockerfile d'assurance dans le repo ; ingestion par timer systemd 05h17 Europe/Paris ; sauvegarde quotidienne de la db (elle est reconstruite chaque jour par `make ingest`, donc un simple `rclone` de la db du jour vers un object storage UE suffit — fournisseur et prix à vérifier dans un ticket séparé, non couverts par cette recherche).

---

*Méthode : 13 plateformes examinées le 19/08/2026, ~35 requêtes WebSearch/WebFetch sur pages officielles ; pages en rendu JavaScript (hetzner.com/cloud, render.com/pricing, clever.cloud/pricing, datasheet Scaleway) signalées et systématiquement croisées avec une seconde source datée. Tout chiffre sans URL a été exclu.*
