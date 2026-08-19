# ARCHITECTURE.md — France Transparence

**Document de référence technique · Établi le 19/08/2026.**
Complète `docs/SOURCES.md` (le *quoi* : 13 pipelines v1, 11 modules) et `docs/DATAVIZ.md` (le *comment visuel*). Ici : le *comment technique*.

---

## 1. Stack et justifications

| Choix | Pourquoi |
|---|---|
| **Python 3.14 + requests + DuckDB** (`pipelines/`) | L'ingestion est un problème de fichiers hétérogènes (Parquet 243 Mo, CSV cp1252/ISO-8859-1, JSON zippés, XML) : Python les couvre tous. DuckDB lit Parquet/CSV volumineux en mémoire bornée et exporte vers SQLite sans étape intermédiaire — indispensable pour les DECP (3,2 M lignes) sans jamais charger un DataFrame géant. |
| **SQLite unique** (`data/france.db`) | Une seule base servie, zéro serveur à opérer, sauvegarde = un fichier. Volumétrie v1 < 2 Go : très en dessous des limites SQLite. Écrite par les pipelines (WAL), lue en lecture seule par l'app — le fichier EST le contrat entre Python et Next. |
| **Next.js 16 (App Router, TypeScript, Tailwind 4)** (`app/`) | Server Components : le SQL s'exécute côté serveur, au plus près de la base, sans API intermédiaire obligatoire ; TypeScript fiabilise les schémas de lignes ; Tailwind 4 consomme directement nos jetons CSS (`@theme inline`). |
| **better-sqlite3** (retenu ; secours : `node:sqlite`) | API synchrone idéale en Server Components (pas de pool, pas d'await), le plus rapide des drivers SQLite node. Prebuilt arm64 vérifié sur node 24 (v13.0.3). Tout passe par `app/src/lib/db.ts` : si la compilation native cassait un jour, seul ce fichier bascule sur `node:sqlite`. |
| **Aucun fetch externe au runtime** | L'app ne lit QUE `data/france.db`. La fraîcheur est celle de l'ingestion, jamais celle d'un appel caché : c'est la condition pour afficher une fraîcheur honnête (règle SOURCES.md §0.2 : date de modif d'un dataset ≠ fraîcheur des données). |
| **Thème sombre unique** | `docs/DATAVIZ.md` : toutes les couleurs sont validées (OKLCH, daltonisme, WCAG) pour `#0a1628`/`#0f1d33` et n'ont pas de jumelle claire. `color-scheme: dark`, aucun `prefers-color-scheme`. |

---

## 2. Arborescence

```
france-transparence/
├── Makefile                  # venv, ingest, ingest-<source>, test, dev, build, app-install
├── requirements.txt          # requests, duckdb, pytest
├── .venv/                    # venv Python 3.14 locale (make venv)
├── data/
│   ├── raw/                  # téléchargements bruts, cache (gitignoré)
│   └── france.db             # LA base servie (produite par make ingest)
├── docs/
│   ├── SOURCES.md            # référentiel des sources (13 pipelines v1)
│   ├── DATAVIZ.md            # jetons couleur + règles dataviz
│   ├── ARCHITECTURE.md       # ce document
│   └── recherche/            # rapports Phase 0 (01 à 09)
├── pipelines/
│   ├── common.py             # session HTTP (UA projet, retries), telecharger(), log
│   ├── db.py                 # connexion(), init_db(), upsert_meta(), schéma noyau
│   ├── ingest_<source>.py    # un module par pipeline (voir §6)
│   └── tests/
│       └── test_socle.py     # tests du socle (base temporaire)
└── app/                      # Next.js 16 — port 3620
    ├── next.config.ts        # serverExternalPackages: better-sqlite3 ; turbopack.root
    └── src/
        ├── lib/db.ts         # ouverture lecture seule + garde « base absente »
        └── app/
            ├── globals.css   # jetons DATAVIZ.md §0 en variables CSS + @theme
            ├── layout.tsx    # header FRANCE TRANSPARENCE + nav des modules
            └── page.tsx      # (pages des modules au fur et à mesure)
```

---

## 3. Flux de données

```
Sources officielles (HTTP, licences ouvertes)
      │  pipelines/common.telecharger() — UA projet, 3 retries backoff,
      │  écriture atomique (.part → rename), cache max_age_heures
      ▼
data/raw/<source>/…              (brut, jetable, gitignoré)
      │  transformation : DuckDB pour les gros Parquet/CSV
      │  (dédup uid, donneesActuelles=true, encodages cp1252/ISO-8859-1),
      │  Python pur pour JSON/XML petits et moyens
      ▼
data/france.db                   (SQLite, WAL ; tables métier par pipeline)
      │  + upsert_meta(source_id, …, date_donnees, date_ingestion, lignes)
      │    dans meta_sources À CHAQUE ingestion réussie
      ▼
app/src/lib/db.ts                (better-sqlite3, readonly, query_only=ON)
      │  Server Components : requêtes directes dans les pages ;
      │  route handlers app/src/app/api/* seulement pour l'interactif
      │  (recherche, filtres client) et le ré-export /donnees
      ▼
Composants React (jetons DATAVIZ.md, badge de fraîcheur obligatoire)
```

Règles du flux :
- **data/raw est jetable** : tout pipeline doit pouvoir reconstruire ses tables depuis un répertoire vide (re-téléchargement).
- **Remplacement complet par défaut** (le fichier source EST l'état — DECP, HATVP, RNE) ; l'incrémental est l'exception documentée (JORF : deltas quotidiens cumulés).
- **Jamais de donnée fabriquée** : un champ absent reste NULL ; une source en panne laisse l'ancienne donnée en place avec sa `date_ingestion` inchangée (le moniteur de fraîcheur A11 la signalera).
- Les URLs `static.data.gouv.fr` horodatées sont re-résolues via l'API data.gouv à chaque ingestion (SOURCES.md §0.3).

---

## 4. Schéma des tables noyau (`pipelines/db.py`, `init_db()` idempotent)

```sql
CREATE TABLE meta_sources (           -- fraîcheur : donnée de premier rang
    source_id      TEXT PRIMARY KEY,  -- 'S1'…'S31' (ids de SOURCES.md)
    nom            TEXT NOT NULL,
    url            TEXT NOT NULL,
    licence        TEXT NOT NULL,     -- 'Licence Ouverte 2.0', 'ODbL'…
    frequence      TEXT NOT NULL,     -- 'quotidienne', 'hebdomadaire', 'mensuelle'…
    date_donnees   TEXT NOT NULL,     -- ISO — date de la donnée la plus récente INGÉRÉE
    date_ingestion TEXT NOT NULL,     -- ISO — dernier passage du pipeline
    lignes         INTEGER NOT NULL DEFAULT 0,
    notes          TEXT
);

CREATE TABLE entites (                -- personnes morales
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN
                  ('ministere','institution','collectivite','parti','organisme')),
    nom         TEXT NOT NULL,
    sigle       TEXT,
    siren       TEXT,                 -- clé de jointure collectivités (jamais l'INSEE)
    departement TEXT
);

CREATE TABLE elus (                   -- personnes physiques
    id              TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    prenom          TEXT,
    sexe            TEXT,
    date_naissance  TEXT,
    profession      TEXT,
    uid_an          TEXT,             -- 'PAxxxx' (jointure open data AN / Datan)
    matricule_senat TEXT,
    hatvp_flag      INTEGER NOT NULL DEFAULT 0,
    mandats         TEXT CHECK (mandats IS NULL OR json_valid(mandats))  -- JSON
);
```

- `date_donnees` ≠ `date_ingestion` : la première est la fraîcheur affichée, la seconde alimente le moniteur de santé (alerte A11 si dérive vs `frequence`).
- Les pipelines créent leurs **tables métier** (préfixe conseillé par domaine : `marches_*`, `jorf_*`, `lobbying_*`…) et peuvent affiner `entites`/`elus` par migrations additives (ALTER ADD COLUMN), jamais destructives.
- Jointures d'identité : pas d'identifiant national d'élu partagé — HATVP ↔ RNE par nom+prénom+département, AN par `uri_hatvp` (SOURCES.md §0.6).

---

## 5. Convention de fraîcheur (obligatoire dans l'UI)

Chaque module affiche, pour chacune de ses sources, un badge :

> **Données au JJ/MM/AAAA · <nom court de la source> · <fréquence>**

- Alimenté exclusivement par `meta_sources` (helper `getMetaSources()` de `app/src/lib/db.ts`, format via `formatDateFr()`).
- `JJ/MM/AAAA` = `date_donnees` (la donnée la plus récente réellement en base), jamais la date du jour, jamais la date de modif du dataset amont.
- Mentions obligatoires héritées de SOURCES.md : « PLF » (S20), « en cours de consolidation » (S1, latence légale 2 mois), « provisoire » (OFGL 2025), crédit Datan/consolidation DECP, attribution ODbL le cas échéant.
- La page `/donnees` expose le catalogue complet de `meta_sources` (le « moniteur de santé des sources »).
- Base absente (`getDb()` → `null`) : chaque page rend un état « données en cours d'ingestion » — jamais de crash, jamais de placeholder chiffré.

---

## 6. Conventions de nommage des pipelines

Un module par pipeline : `pipelines/ingest_<source>.py`, exécutable par `python -m pipelines.ingest_<source>` et câblé dans le `Makefile` (`make ingest-<source>`, variable `PIPELINES`). Correspondance avec SOURCES.md §5 :

| Cible make | Module | Pipeline (sources) |
|---|---|---|
| `ingest-budget_mensuel` | `ingest_budget_mensuel.py` | P1 — SMB mensuelles (S13) |
| `ingest-budget_structure` | `ingest_budget_structure.py` | P2 — PLF/jaunes annuels (S20, S21, S23) |
| `ingest-decp` | `ingest_decp.py` | P3 — DECP consolidées (S1) |
| `ingest-boamp` | `ingest_boamp.py` | P4 — AO en cours (S2) |
| `ingest-approch` | `ingest_approch.py` | P5 — projets d'achats (S9) |
| `ingest-jorf` | `ingest_jorf.py` | P6 — Journal officiel (S3) |
| `ingest-integrite` | `ingest_integrite.py` | P7 — HATVP liste + RNE (S14, S17) |
| `ingest-lobbying` | `ingest_lobbying.py` | P8 — HATVP AGORA (S4) |
| `ingest-parlement` | `ingest_parlement.py` | P9 — AN + Sénat + Datan (S5, S6, S7) |
| `ingest-financement` | `ingest_financement.py` | P10 — CNCCFP (S25, S29) |
| `ingest-collectivites` | `ingest_collectivites.py` | P11 — OFGL (S16) |
| `ingest-referentiels` | `ingest_referentiels.py` | P12 — géo, populations, entreprises (S27, S10) |
| `ingest-trainvie` | `ingest_trainvie.py` | P13 — constantes sourcées (S31) |

Contrat d'un pipeline :
1. importe `common` (session, `telecharger`, log) et `db` (`connexion`, `init_db`, `upsert_meta`) ;
2. appelle `init_db()` en premier (idempotent) ;
3. télécharge dans `data/raw/<source>/`, transforme (DuckDB si volumineux), écrit ses tables métier en transaction ;
4. termine par `upsert_meta(...)` avec le **compte de lignes réel** et la **date de la donnée la plus récente constatée dans les données** (tri sur le champ date, pas les métadonnées) ;
5. échoue bruyamment (exception, exit ≠ 0) plutôt que d'écrire des données partielles : pas de `meta_sources` mis à jour = ingestion non comptée ;
6. tout paramètre variable (législature 17, seuils 40/60 k€ au 01/04/2026, millésimes) est une constante nommée en tête de module, jamais enfouie.

Côté app : pages de module dans `app/src/app/<module>/page.tsx` (routes : `/depenses`, `/marches`, `/elus`, `/lobbying`, `/financement`, `/frais`, `/collectivites`, `/documents`, `/donnees`) ; requêtes SQL dans `app/src/lib/` (un fichier par domaine), jamais dans les composants client.

---

## 7. Stratégie de tests

- **`make test`** = `pytest pipelines/tests -q` dans la venv. Doit rester vert en local **sans réseau** : les tests unitaires ne téléchargent jamais.
- **Socle** (`test_socle.py`, en place) : `init_db` sur base temporaire (`tmp_path`), idempotence, contraintes CHECK (`entites.type`, `elus.mandats` JSON), upsert/écrasement de `upsert_meta`.
- **Par pipeline** (`pipelines/tests/test_<source>.py`) : tester la **transformation** sur un petit extrait réel du fichier source figé dans `pipelines/tests/fixtures/` (quelques lignes du vrai CSV/JSON, pièges inclus : cp1252 + skiprows=6 pour CNCCFP, `%` du Sénat, `"CDL"` = null, U+00A0 dans les montants). Le téléchargement n'est pas testé unitairement, il est éprouvé par l'exécution réelle.
- **Fumée d'intégration** (optionnelle, marquée `@pytest.mark.reseau`, exclue par défaut) : HEAD sur les URLs vivantes — c'est le rôle du moniteur A11 en production, pas de la CI.
- **App** : `npm run build` (types + lint Next) fait office de porte ; les pages doivent builder avec ET sans `data/france.db` présent (la garde `getDb() → null` est un cas de test permanent).

---

## 8. Ajouter une source (check-list)

1. **Documenter d'abord** : la source entre dans `docs/SOURCES.md` (URL testée avec code HTTP constaté, licence, fraîcheur réelle, pièges) — règle du projet : rien ne s'ingère qui ne soit documenté.
2. Créer `pipelines/ingest_<source>.py` selon le contrat du §6 (id `Sxx` repris de SOURCES.md).
3. L'ajouter à la variable `PIPELINES` du `Makefile` → `make ingest-<source>` et inclusion dans `make ingest`.
4. Écrire `pipelines/tests/test_<source>.py` + fixture réelle minimale ; `make test` vert.
5. Exécuter réellement le pipeline ; vérifier la ligne `meta_sources` (compte de lignes, `date_donnees` cohérente avec la source).
6. Côté app : requêtes dans `app/src/lib/`, page/composants avec **badge de fraîcheur** (§5), jetons DATAVIZ.md uniquement, mentions de licence/attribution si exigées (ODbL, Datan…).
7. Si la source alimente une alerte (A1-A11), documenter la règle de calcul et sa base légale sur la page `/donnees`.

---

## 9. Ports et commandes

| Commande | Effet |
|---|---|
| `make venv` | crée `.venv` (python3.14) + `pip install -r requirements.txt` |
| `make ingest` / `make ingest-<source>` | joue tous les pipelines / un seul |
| `make test` | pytest du socle et des pipelines |
| `make app-install` | `npm install` dans `app/` |
| `make dev` | `next dev` sur **http://localhost:3620** |
| `make build` | `next build` (porte de qualité de l'app) |

Le port **3620** est fixé dans `app/package.json` (`dev` et `start`) pour éviter toute collision avec d'autres apps locales sur 3000.
