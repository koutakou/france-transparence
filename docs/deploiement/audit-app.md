# Audit pré-durcissement — France Transparence

- **Date** : 19/08/2026, ~20 h 30 — commit `68ef8aa` (« chore: clôture mission »).
- **Cible mesurée** : build de production locale (`next start -p 3620`, next-server v16.3.1, PID 50397), base `data/france.db` 447 Mo.
- **Méthode** : mesures réelles `curl` sur http://localhost:3620 (aucune simulation) + lecture du code. Audit pur : **rien n'a été modifié**.
- **TTFB** : mesuré à chaud, en local (pas de latence réseau) — sert de plancher, pas de prévision prod.

---

## 1. Poids et TTFB par route (mesures réelles)

Passe 1 sans `Accept-Encoding` (corps brut), passe 2 avec `Accept-Encoding: gzip, br`.

| Route | Code | Brut (octets) | Compressé (octets) | Encodage servi | TTFB brut (s) | TTFB compressé (s) |
|---|---|---:|---:|---|---:|---:|
| `/` | 200 | 744 116 | 225 818 | gzip | 0,052 | 0,036 |
| `/depenses` | 200 | 193 871 | 21 386 | gzip | 0,077 | 0,077 |
| `/marches` | 200 | **1 290 695** | 252 092 | gzip | 0,055 | 0,049 |
| `/elus` | 200 | **2 276 593** | 103 672 | gzip | 0,079 | 0,074 |
| `/lobbying` | 200 | **950 607** | 59 039 | gzip | 0,018 | 0,018 |
| `/financement` | 200 | 243 428 | 25 319 | gzip | 0,012 | 0,012 |
| `/frais` | 200 | 221 558 | 26 260 | gzip | 0,012 | 0,006 |
| `/collectivites` | 200 | **1 848 314** | **420 989** | gzip | 0,057 | 0,052 |
| `/documents` | 200 | 279 878 | 23 986 | gzip | 0,010 | 0,009 |
| `/alertes` | 200 | 270 958 | 15 735 | gzip | 0,006 | 0,006 |
| `/donnees` | 200 | 210 978 | 23 786 | gzip | 0,006 | 0,006 |
| `/elus/PA719930` (fiche réelle) | 200 | 323 276 | 19 633 | gzip | 0,012 | 0,011 |
| `/api/meta` | 200 | 16 036 | 16 036 | **(aucun)** | 0,002 | 0,001 |
| `/api/alertes` | 200 | **78 931** | **78 931** | **(aucun)** | 0,002 | 0,002 |
| `/api/budget/mensuel` | 200 | 10 829 | 10 829 | **(aucun)** | 0,001 | 0,001 |
| `/api/elus` | 200 | 19 436 | 19 436 | **(aucun)** | 0,001 | 0,001 |
| `/api/marches/agregats` | 200 | 17 902 | 17 902 | **(aucun)** | 0,003 | 0,001 |
| `/api/recherche?q=vallaud` | 200 | 123 | 123 | (aucun) | 0,005 | 0,004 |

**Constats** :
- **5 pages > 500 Ko brut** : `/elus` (2,28 Mo), `/collectivites` (1,85 Mo), `/marches` (1,29 Mo), `/lobbying` (951 Ko), `/` (744 Ko). Cause structurelle : tables/dataviz entièrement rendues serveur **+ payload RSC (flight data) qui duplique le contenu dans le même HTML** — le DOM à parser côté client reste de cette taille même quand le transfert est compressé.
- **Compression** : Next compresse le HTML en **gzip** (défaut `compress: true` de `next start` — rien d'explicite dans `next.config.ts`). **Jamais de brotli** (non supporté par `next start`). Après gzip, aucune page ne dépasse 500 Ko ; la pire est `/collectivites` à **421 Ko compressés** (ratio 4,4× seulement — probable GeoJSON/données de carte peu redondants).
- **Les 6 routes API ne sont JAMAIS compressées**, même avec `Accept-Encoding: gzip, br` : `/api/alertes` part en 78 931 octets bruts à chaque hit. Les route handlers (`NextResponse.json`) court-circuitent la compression de `next start`. À traiter au reverse proxy en prod.
- TTFB local : 1 à 79 ms, corrélé à la taille (rendu force-dynamic complet à chaque hit, cf. § 4). Excellent en local M4 Max ; sur VPS, ajouter CPU plus lent + latence réseau.

---

## 2. Headers de réponse : état et manques

`curl -sI http://localhost:3620/` :

```
HTTP/1.1 200 OK
Vary: rsc, next-router-state-tree, next-router-prefetch, next-router-segment-prefetch, Accept-Encoding
X-Powered-By: Next.js
Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate
Content-Type: text/html; charset=utf-8
Date / Connection / Keep-Alive
```

`curl -sI http://localhost:3620/api/meta` :

```
HTTP/1.1 200 OK
vary: rsc, next-router-state-tree, next-router-prefetch, next-router-segment-prefetch
cache-control: public, max-age=300, stale-while-revalidate=3600
content-type: application/json
```

**Absents partout** (mesuré sur `/` et `/api/meta`) :

| Header | État |
|---|---|
| `Content-Security-Policy` | **absent** |
| `Strict-Transport-Security` (HSTS) | **absent** (normal en HTTP local ; à poser au proxy TLS en prod) |
| `X-Content-Type-Options: nosniff` | **absent** |
| `Referrer-Policy` | **absent** |
| `X-Frame-Options` / CSP `frame-ancestors` | **absent** |
| `Permissions-Policy` | **absent** |
| `Cache-Control` pertinent sur le HTML | **absent** — `private, no-cache, no-store` sur les 12 pages (défaut force-dynamic) : aucun cache navigateur ni CDN possible en l'état |

En plus : **`X-Powered-By: Next.js` exposé** (fuite d'info ; `poweredByHeader: false` non posé). **`/api/recherche` n'a AUCUN `Cache-Control`** — les 5 autres routes API posent `public, max-age=300, stale-while-revalidate=3600` (const `CACHE_OK`), la recherche a été oubliée (`app/src/app/api/recherche/route.ts` : pas de header sur la réponse).

Piège à connaître pour la CSP : les pages embarquent des scripts inline RSC et des `style=` inline — une CSP stricte sans nonce cassera le site ; prévoir nonces Next ou `'unsafe-inline'` assumé sur `style-src`.

---

## 3. Façade publique manquante

Mesures réelles :

| URL | Code | Constat |
|---|---|---|
| `/robots.txt` | **404** | aucun `app/robots.ts` ni fichier public |
| `/sitemap.xml` | **404** | aucun `app/sitemap.ts` |
| `/favicon.ico` | 200 | 25 931 o, 256×256 (`app/src/app/favicon.ico`) — OK |
| `/apple-touch-icon.png` | **404** | absent |
| `/xyz-404` | 404 | page 404 rendue **dans le layout complet** (header, nav, footer) mais le corps est le défaut Next **en anglais** (« 404 — This page could not be found. ») : aucun `app/not-found.tsx`. Poids 19 238 o. Point positif : `<meta name="robots" content="noindex">` présent. |
| `/mentions-legales` | **404** | **aucune page mentions légales** ; le footer ne porte que la licence des données et un lien `/donnees` |

**Métadonnées** (grep `export const metadata` — aucun `generateMetadata` dans tout le projet) :
- `app/src/app/layout.tsx:8` : title default + template `%s · France Transparence` + description globale. **Pas de `metadataBase`, pas d'`openGraph`, pas de `twitter`** — zéro occurrence dans tout `app/` : **aucun partage social ne produira de carte**.
- Avec metadata propre (title + description, sans OG) : `alertes:22`, `donnees:17`, `elus:29`, `collectivites:31`, `marches:27`, `frais:18`, `documents:25`, `depenses:24`.
- **Sans metadata** : `/lobbying` et `/financement` (title mesuré : « France Transparence » nu) et surtout **`elus/[id]/page.tsx` : toutes les fiches élus partagent le title générique** (mesuré sur /elus/PA719930).
- **Bug title doublonné** mesuré sur `/elus` : `Élus & institutions — France Transparence · France Transparence` — `app/src/app/elus/page.tsx:30` inclut le suffixe que le template du layout rajoute.
- `app/public/` contient encore les **5 SVG de create-next-app** (file, globe, next, vercel, window.svg), servis publiquement.

---

## 4. Cache et rendu actuels

**Tout est force-dynamic.** 12/12 pages et 6/6 routes API (`grep` exhaustif, aucun `revalidate` ni `unstable_cache` dans le projet) :

- Pages : `app/page.tsx:22`, `alertes/page.tsx:20`, `financement/page.tsx:20`, `lobbying/page.tsx:22`, `donnees/page.tsx:15`, `elus/page.tsx:27`, `elus/[id]/page.tsx:19`, `collectivites/page.tsx:29`, `marches/page.tsx:25`, `frais/page.tsx:16`, `documents/page.tsx:23`, `depenses/page.tsx:22`.
- API : `api/alertes/route.ts:21`, `api/elus/route.ts:23`, `api/marches/agregats/route.ts:15`, `api/meta/route.ts:12`, `api/recherche/route.ts:20`, `api/budget/mensuel/route.ts:19`.

Conséquences mesurées : chaque hit HTML relance requêtes SQLite + rendu complet, et sort en `no-store` (aucun cache possible), alors que **la donnée ne change qu'à l'ingestion** (quotidienne au mieux). Les API compensent avec `CACHE_OK = public, max-age=300, stale-while-revalidate=3600` (sauf `/api/recherche`, rien). Le no-store HTML est le vrai paradoxe : la page la plus lourde (2,28 Mo) est aussi celle qu'aucun CDN ne peut retenir.

**`app/next.config.ts`** (13 lignes, minimal) : `serverExternalPackages: ["better-sqlite3"]` + `turbopack.root`. **Pas de** `compress` explicite (défaut on), **pas de** `headers()`, **pas de** `output: "standalone"`, **pas de** `poweredByHeader: false`.

---

## 5. Base de données côté app

`app/src/lib/db.ts` — sain et vérifié :

- **Lecture seule triple-verrouillée** : `new Database(DB_PATH, { readonly: true, fileMustExist: true })` + `db.pragma("query_only = ON")` (lignes 32-34). Grep confirmé : **aucun** `INSERT/UPDATE/DELETE/CREATE` dans `app/src`. **L'app ne peut pas écrire en base.**
- **Chemin configurable** : env `FRANCE_DB_PATH` (résolu en absolu), sinon `path.resolve(process.cwd(), "..", "data", "france.db")` (lignes 19-21) — **relatif au cwd** : fonctionne parce que `npm run start` tourne depuis `app/` ; un lancement depuis un autre cwd (systemd sans `WorkingDirectory`) casserait le défaut → **en prod, toujours poser `FRANCE_DB_PATH` absolu**.
- **Garde base absente** : `getDb()` renvoie `null` si le fichier manque (pas de crash ; les API répondent 503, les pages un état « ingestion en cours »).
- **Point critique pour la bascule** : la connexion est mémoïsée dans `globalThis.__franceDb` (lignes 23, 30-31) et **jamais rouverte**. Remplacer `france.db` sous le serveur (même `mv` atomique) ne sera **pas vu** : l'ancien inode reste ouvert. **Un restart du process est obligatoire après bascule.**
- **WAL** : les pipelines posent `journal_mode = WAL` (persistant dans le fichier) ; le serveur, même readonly, maintient un `france.db-shm` (constaté : 32 Ko, touché à 19:53) → le répertoire de la base doit rester inscriptible par l'utilisateur du serveur, et toute copie vers la prod doit se faire **wal checkpointé** (constaté : `france.db-wal` 0 octet, propre) — ne jamais copier la db seule pendant une ingestion.
- SQL : **100 % paramétré** (placeholders `?`, ex. `lib/queries/alertes.ts:130-152`, `lib/queries/elus.ts:185-205`) ; les interpolations `${...}` détectées ne construisent que des listes de `?` ou des clauses à partir de littéraux internes. Pas d'injection possible via `searchParams` ou `?q=`.

---

## 6. Ingestion et faisabilité de la bascule atomique

**Mécanique réelle** (`Makefile` + `pipelines/db.py`) :
- `make ingest` = 13 pipelines **séquentiels, ordre imposé** (`referentiels budget_mensuel budget_structure decp boamp approch jorf parlement integrite lobbying financement collectivites trainvie`) via la règle pattern `ingest-%: venv → $(PY) -m pipelines.ingest_$*` (attention historique : ces cibles ne doivent **pas** être `.PHONY`, commentaire Makefile lignes 15-17).
- **`FT_DB_PATH` marche pour la bascule** : `pipelines/db.py:25-32` (`_chemin_db()` : env `FT_DB_PATH` sinon `data/france.db`) et **tous** les pipelines passent par `connexion()/init_db()` sans chemin en dur (grep : `CHEMIN_DB` n'est utilisé que dans `db.py`). Donc `FT_DB_PATH=/srv/ft/france.new.db make ingest` construit une base complète ailleurs. Le cache de téléchargements `data/raw/` reste, lui, relatif au dépôt (`pipelines/common.py:23-25`) — partagé entre runs, sans impact sur la bascule.
- **Bascule atomique réaliste** : `FT_DB_PATH=<nouveau> make ingest` → vérifs (25 lignes `meta_sources`, volumétrie) → `mv` atomique sur le chemin servi → **restart de l'app** (obligatoire, cf. § 5 connexion mémoïsée). Downtime = durée du restart, pas de l'ingestion.
- **Durée** : aucune durée loggée (rien dans JOURNAL.md/STATUS.md/docs). Estimation par mtimes du run du 19/08 : premiers téléchargements lourds 15:47 (`decp.parquet`, 243 Mo) → `france.db` finalisée 16:14, soit **≈ 25-30 min téléchargements compris sur M4 Max** ; prévoir sensiblement plus sur un VPS (CPU + bande passante). Un re-run partiel lobbying est visible à 19:59.
- **Python** : `PYTHON ?= python3.14` (Makefile ligne 4) — seule codification de la version. `requirements.txt` minimal et non pinné exactement : `requests>=2.32`, `duckdb>=1.3`, `pytest>=8.3`. Tests : `make test` = 150 pytest.

---

## 7. Dépendances serveur

- `app/package.json` : `start = next start -p 3620`, `build = next build`. **Pas de champ `engines`** ; contrainte réelle : Next 16.3.1 exige **Node ≥ 20.9.0** (engines de next), mais le **README ligne 9 exige Node ≥ 24** (Node local : v24.15.0) — à trancher/codifier.
- **Lockfile présent** : `app/package-lock.json` (240 Ko).
- **better-sqlite3 13.0.3** : le paquet **embarque ses prebuilds** — `darwin-arm64/x64`, **`linux-x64`, `linux-arm64`, `linuxmusl-x64/arm64`**, win32 (constaté dans `node_modules/better-sqlite3/prebuilds/`). **Aucune compilation nécessaire sur un VPS Linux x64 ou arm64, glibc ou musl.**
- Runtime : react 19.2.8, d3-geo 3.1.1. Aucun fetch externe au runtime (app 100 % locale sur SQLite).

---

## 8. Secrets — verdict

**Aucun secret réel dans le repo.** Vérifications :
- Grep `api[_-]?key|token|secret|password|Bearer` (hors node_modules/.venv/.git/data/.next) : uniquement des **faux positifs documentaires** — docs de recherche décrivant l'OAuth PISTE testé avec identifiants bidons (`docs/recherche/07-documents-juridique.md:130-135`, `docs/SOURCES.md:227`), prose « secret professionnel » (trainvie, docs), variable `parisEcrete` (collectivites/page.tsx:333).
- **Aucun `.env*` sur disque**, et `git log --diff-filter=A` : **aucun `.env`/secret/credential jamais commité** (3 commits au total).
- `.gitignore` sain : `.env*` (avec exception `!.env.example`), `data/france.db`, `data/raw/`, `data/tmp/`, `node_modules/`, `.venv/`, `*.db-wal/-shm` couverts.
- Aucune clé nécessaire au runtime (pas d'API externe appelée par l'app). Seule « fuite » : `X-Powered-By: Next.js` (§ 2).

---

## 9. Risques mobile probables (grep, sans screenshots)

Plutôt sain côté layout :
- **Tables** : un composant unique `components/ui/DataTable.tsx` avec wrapper `overflow-x-auto` (ligne 98) ; wrapper aussi sur `documents/page.tsx:303` et le `<pre>` de `donnees/page.tsx:502`. Aucune table nue détectée.
- **Nav** : `components/MainNav.tsx:149` `overflow-x-auto` + `whitespace-nowrap` — les 10 onglets défilent horizontalement au lieu de casser (constaté dans le HTML).
- **Grids** : aucune `grid-cols-N` fixe sans variante responsive détectée (grep incluant template literals).

Risques réels restants :
1. **Volume DOM** : 2,28 Mo de HTML sur `/elus` et 1,85 Mo sur `/collectivites` = parse/layout lourds sur mobile modeste, même bien compressés au transfert (le § 1 est le vrai chantier mobile).
2. Nav horizontale scrollable sans indicateur : les onglets de droite (Documents, Données) risquent d'être hors champ sans affordance — à vérifier par l'agent screenshots.
3. SVG/dataviz serveur à largeurs calculées (d3-geo sur /collectivites) — à vérifier visuellement en 375 px.

---

## 10. Chantiers R2 recommandés — LISTE FERMÉE (16)

Classés par fichier/page ; chaque chantier a son critère d'acceptation mesurable.

| # | Chantier | Fichier(s) | Critère d'acceptation (mesurable) |
|---|---|---|---|
| R2-1 | Headers de sécurité globaux (CSP avec nonces ou `style-src 'unsafe-inline'` assumé, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors`/`X-Frame-Options`, `Permissions-Policy`) + `poweredByHeader: false` ; HSTS au proxy TLS | `app/next.config.ts` (fonction `headers()`) + config proxy | `curl -sI /` et `/api/meta` montrent les 5 headers ; `X-Powered-By` absent ; les 12 pages rendent sans erreur CSP console |
| R2-2 | Sortir du no-store HTML : la donnée ne change qu'à l'ingestion → retirer `force-dynamic` des pages sans `searchParams` ou poser `Cache-Control: public, s-maxage=300, stale-while-revalidate` via `headers()` | les 12 `page.tsx` listés § 4 | plus aucun `private, no-cache, no-store` sur les 12 pages (`curl -sI`) ; 2e hit servi par le cache proxy/CDN |
| R2-3 | Poids `/elus` : pagination/limite serveur des tables d'élus | `app/src/app/elus/page.tsx` + `lib/queries/elus.ts` | `curl size_download` brut < 500 000 o (aujourd'hui 2 276 593) |
| R2-4 | Poids `/collectivites` : alléger la carte/GeoJSON inline (simplification topologie ou chargement client) | `app/src/app/collectivites/page.tsx` | brut < 500 000 o ET compressé < 150 000 o (aujourd'hui 1 848 314 / 420 989) |
| R2-5 | Poids `/marches` : tronquer/paginer les listes DECP/BOAMP rendues | `app/src/app/marches/page.tsx` | brut < 500 000 o (aujourd'hui 1 290 695) |
| R2-6 | Poids `/lobbying` | `app/src/app/lobbying/page.tsx` | brut < 500 000 o (aujourd'hui 950 607) |
| R2-7 | Poids `/` (accueil) | `app/src/app/page.tsx` | brut < 500 000 o (aujourd'hui 744 116) |
| R2-8 | Compression des API : gzip/brotli au reverse proxy (les route handlers ne sont pas compressés par `next start`) | config nginx/caddy (hors repo) | `curl -H 'Accept-Encoding: gzip' /api/alertes` renvoie `Content-Encoding` et < 20 000 o (aujourd'hui 78 931 non compressé) |
| R2-9 | `Cache-Control` manquant sur la recherche | `app/src/app/api/recherche/route.ts` | `curl -sI '/api/recherche?q=a'` montre un `cache-control` explicite (ex. `public, max-age=60`) |
| R2-10 | `robots.ts` + `sitemap.ts` (12 pages + fiches élus) + `apple-touch-icon` | `app/src/app/robots.ts`, `sitemap.ts`, icône | `/robots.txt` 200 `text/plain` ; `/sitemap.xml` 200 XML valide ; `/apple-touch-icon.png` 200 |
| R2-11 | Page 404 en français | `app/src/app/not-found.tsx` | `curl /xyz-404` : code 404 + texte français (« Page introuvable ») dans le layout |
| R2-12 | Metadata : ajouter `/lobbying` et `/financement` ; `generateMetadata` sur la fiche élu ; corriger le doublon `/elus` ; `metadataBase` + `openGraph` (title/description/image) sur le layout et les 12 pages | `layout.tsx`, `lobbying/page.tsx`, `financement/page.tsx`, `elus/[id]/page.tsx`, `elus/page.tsx:30` | title de `/elus` sans doublon ; title de `/elus/PA719930` contient le nom de l'élu ; `og:title` présent dans le HTML de `/` |
| R2-13 | Mentions légales (éditeur, hébergeur, licences, contact) + lien footer | nouvelle page + `layout.tsx` (footer) | `/mentions-legales` 200 ; lien présent dans le footer des 12 pages |
| R2-14 | Purger les 5 SVG create-next-app | `app/public/{file,globe,next,vercel,window}.svg` | `/vercel.svg` → 404 |
| R2-15 | Script de bascule atomique documenté : `FT_DB_PATH=<neuf> make ingest` → vérifs meta_sources → `mv` → restart app ; app lancée avec `FRANCE_DB_PATH` **absolu** (unit systemd avec `WorkingDirectory` + env) | script deploy + unit systemd (hors repo app) | bascule rejouée : downtime mesuré < 5 s, `derniere_ingestion` de `/api/meta` reflète la nouvelle base après restart |
| R2-16 | Codifier les versions : champ `engines` dans `app/package.json` (trancher README ≥ 24 vs next ≥ 20.9) ; envisager `output: "standalone"` pour un artefact de déploiement léger | `app/package.json`, `next.config.ts` | `npm ci` échoue/avertit sous la version choisie ; si standalone : taille de l'artefact documentée |

**Hors liste (constat, pas un chantier)** : TTFB actuels excellents en local ; SQL paramétré partout ; db readonly verrouillée ; secrets absents — ces points n'appellent aucune action.
