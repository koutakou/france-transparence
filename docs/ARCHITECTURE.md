# ARCHITECTURE.md — France Transparence

**Document de référence technique · Établi le 19/08/2026. Révisé le 25/08/2026.**

État courant : **30 pipelines**, **43 sources**, **11 onglets** + `/comprendre` hors nav, kit `app/src/components/ui/` écrit (G2/G8). Le flux de données et le schéma SQL noyau ci-dessous n'ont pas changé de contrat.

Complète `docs/SOURCES.md` (le *quoi* : le périmètre de sources ingérées) et `docs/DATAVIZ.md` (le *comment visuel*). Ici : le *comment technique*.

---

## 1. Stack et justifications

| Choix | Pourquoi |
|---|---|
| **Python 3.14 + requests + DuckDB** (`pipelines/`) | L'ingestion est un problème de fichiers hétérogènes (Parquet 243 Mo, CSV cp1252/ISO-8859-1, JSON zippés, XML) : Python les couvre tous. DuckDB lit Parquet/CSV volumineux en mémoire bornée et exporte vers SQLite sans étape intermédiaire — indispensable pour les DECP (3,2 M lignes) sans jamais charger un DataFrame géant. |
| **SQLite unique** (`data/france.db`) | Une seule base servie, zéro serveur à opérer, sauvegarde = un fichier. Le fichier pèse quelques centaines de Mo : très en dessous des limites SQLite. Écrite par les pipelines (WAL), lue en lecture seule par l'app — le fichier EST le contrat entre Python et Next. |
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
│   ├── SOURCES.md            # référentiel des sources (périmètre ingéré)
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
        ├── components/
        │   ├── MainNav.tsx   # client — 11 onglets (pas /comprendre, pas /alertes)
        │   └── ui/           # kit partagé (G2/G8) : graphiques, FreshnessBadge, NoticeLecture…
        └── app/
            ├── globals.css   # jetons DATAVIZ.md §0 en variables CSS + @theme
            ├── layout.tsx    # chrome + SearchBox ; pied vers /comprendre
            ├── page.tsx      # accueil
            ├── recettes/     # onglet Recettes (après Dépenses)
            ├── comprendre/   # appareil pédagogique, hors nav
            └── …             # un dossier par module
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
      │  (dédup uid, attributs pris sur donneesActuelles=true mais date du
      │   marché = min(dateNotification) sur toutes ses lignes,
      │   encodages cp1252/ISO-8859-1),
      │  Python pur pour JSON/XML petits et moyens
      ▼
data/france.db                   (SQLite, WAL ; tables métier par pipeline)
      │  + upsert_meta(source_id, …, date_donnees, date_ingestion, lignes)
      │    dans meta_sources À CHAQUE ingestion réussie
      ▼
app/src/lib/db.ts                (better-sqlite3, readonly, query_only=ON)
      │  Server Components : requêtes au BUILD (export statique) ;
      │  l'interactif côté navigateur lit des JSON pré-générés
      │  (/data/recherche-index.json, /api/*.json) — pas une API live
      ▼
Composants React (jetons DATAVIZ.md, badge de fraîcheur obligatoire)
```

Règles du flux :
- **data/raw est jetable** : tout pipeline doit pouvoir reconstruire ses tables depuis un répertoire vide (re-téléchargement).
- **Remplacement complet par défaut** (le fichier source EST l'état — DECP, HATVP, RNE) ; l'incrémental est l'exception documentée (JORF : deltas quotidiens cumulés).
- **Jamais de donnée fabriquée** : un champ absent reste NULL ; une source en panne laisse l'ancienne donnée en place avec sa `date_ingestion` inchangée (le moniteur de fraîcheur A11 la signalera).
- **Aucune historisation en base** : la base porte l'état courant de chaque source, jamais ses états antérieurs. Une mesure de délai n'est donc calculable que si la source porte elle-même les deux axes du temps — la période décrite et la date d'observation. C'est le cas des DECP (`dateNotification` / `datePublicationDonnees`), et c'est ce qui rend le délai de publication des marchés mesurable au passage du pipeline, sans mécanisme de suivi côté base.
- Les URLs `static.data.gouv.fr` horodatées sont re-résolues via l'API data.gouv à chaque ingestion (SOURCES.md §0.3).

---

## 4. Schéma des tables noyau (`pipelines/db.py`, `init_db()` idempotent)

```sql
CREATE TABLE meta_sources (           -- fraîcheur : donnée de premier rang
    source_id      TEXT PRIMARY KEY,  -- 'S1'…'S51', ids composés (S5-AMO10, S27-*, …)
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
| `ingest-decp` | `ingest_decp.py` | P3 — DECP consolidées (S1). Outre les tables qui servent la carte, le flux des derniers marchés et l'auto-critique des montants, il écrit les trois tables de **qualité de publication** — `decp_publication_qualite`, `decp_publication_annees`, `decp_publication_acheteurs` — calculées au grain du marché (agrégation par `uid` avant tout comptage) directement depuis le parquet, et lues par la page `/marches`. Ses deux classements 12 mois (`decp_top_acheteurs`, `decp_top_titulaires`) groupent par **SIREN**, l'entreprise, et non par SIRET, l'établissement ; `decp_titulaires_qualite` et `decp_acheteurs_qualite` disent sur la même fenêtre ce que ce regroupement retient et ce qu'il écarte, les identifiants non conformes étant comptés là plutôt que classés — deux tables et non une, l'unité de compte n'étant pas la même (couple marché × titulaire d'un côté, marché de l'autre, un marché n'ayant qu'un acheteur). Le nom affiché de ces entreprises n'est pas écrit par ce pipeline : il est joint à la lecture depuis `sirene_unites_legales` (S18), pour ne pas coupler l'écriture de deux pipelines. Lecture de la source dans la fiche S1 de SOURCES.md (§ lecture bitemporelle) ; schéma, périmètre et pièges dans SCHEMA-DB.md. |
| `ingest-boamp` | `ingest_boamp.py` | P4 — AO en cours (S2) |
| `ingest-approch` | `ingest_approch.py` | P5 — projets d'achats (S9) |
| `ingest-jorf` | `ingest_jorf.py` | P6 — Journal officiel (S3) |
| `ingest-integrite` | `ingest_integrite.py` | P7 — HATVP liste + RNE (S14, S17) |
| `ingest-lobbying` | `ingest_lobbying.py` | P8 — HATVP AGORA (S4) |
| `ingest-parlement` | `ingest_parlement.py` | P9 — AN + Sénat + Datan (S5, S6, S7) |
| `ingest-financement` | `ingest_financement.py` | P10 — CNCCFP + aide publique aux partis (S25, S29, S37) |
| `ingest-collectivites` | `ingest_collectivites.py` | P11 — OFGL (S16) |
| `ingest-referentiels` | `ingest_referentiels.py` | P12 — géo, populations, annuaire et organisation de l'État (S27, S11, S35). Le module `pipelines/sirene.py` (S10, résolution unitaire par API) vit à côté mais n'est appelé par aucun pipeline : `meta_sources` ne porte aucune ligne S10. |
| `ingest-trainvie` | `ingest_trainvie.py` | P13 — constantes sourcées (S31) |
| `ingest-hatvp_declarations` | `ingest_hatvp_declarations.py` | Contenu des déclarations d'intérêts HATVP (S15). Passe **après** `ingest-integrite`, dont il lit les élus appariables. |
| `ingest-elections` | `ingest_elections.py` | Résultats et participation électorale (S26). Passe **après** `ingest-referentiels` et `ingest-collectivites`, dont il lit le périmètre. |
| `ingest-cada` | `ingest_cada.py` | Avis et conseils de la CADA, en agrégats (S38). Aucune dépendance d'ordre : n'écrit que ses propres tables. |
| `ingest-registre_ue` | `ingest_registre_ue.py` | Registre de transparence de l'Union européenne (S40). Aucune dépendance d'ordre, et **aucun lien possible avec S4** : l'export UE ne porte ni SIREN ni numéro de TVA. |
| `ingest-dette_maastricht` | `ingest_dette_maastricht.py` | Encours de dette des APU au sens de Maastricht (S41, Eurostat `gov_10q_ggdebt`). Aucune dépendance d'ordre : n'écrit que `dette_apu_maastricht`. Le secteur ESA S13 n'est pas la source S13. |
| `ingest-deficit_maastricht` | `ingest_deficit_maastricht.py` | Déficit public des APU au sens de Maastricht (S42, Eurostat `gov_10dd_edpt1`, na_item=B9). Aucune dépendance d'ordre : n'écrit que `deficit_apu_maastricht`. Distinct de S41 (stock GD) et de S13 (solde du budget général). Pas de comparaison au seuil de 3 % du PIB. |
| `ingest-dole` | `ingest_dole.py` | P19 — Dossiers législatifs DILA (S43, fonds DOLE). Aucune dépendance d'ordre : n'écrit que `dole_dossiers`. Distinct de S3 (JORFSIMPLE, fenêtre 30 JO) et de S35 (LEGI, Debats, RefOrgaAdminEtat). Placé avant `sirene`. |
| `ingest-agregats_apu` | `ingest_agregats_apu.py` | P20 — Recettes et dépenses des APU, agrégats ESA (S44, Eurostat `gov_10a_main`, na_item TE/TR). Aucune dépendance d'ordre : n'écrit que `agregats_apu_esa`. Distinct de S13 (État YTD), S41 (stock GD) et S42 (B9). Pas de B9 dérivé, pas de COFOG. TE/TR ne sont pas Maastricht. Placé avant `sirene`. |
| `ingest-cge` | `ingest_cge.py` | P21 — Bilan patrimonial de l'État (S22, CGE DGFiP, pièce de synthèse xlsx). Aucune dépendance d'ordre : n'écrit que `cge_bilan_etat`. Distinct de S13 (budget, caisse), S41/S42/S44 (Maastricht / ESA des APU). Totaux lus dans la pièce, jamais sommés depuis les balances compte×programme. Placé avant `sirene`. |
| `ingest-protection_sociale` | `ingest_protection_sociale.py` | P22 — Prestations de protection sociale (S45, DREES comptes de la protection sociale, prestations E11). Aucune dépendance d'ordre : n'écrit que `protection_sociale_prestations`. Distinct de S13 (budget État), S44 (TE APU) et S22 (CGE). Grains exclusifs seulement. Md€ = M€ ÷ 1000, jamais ÷ 1e9. Placé avant `sirene`. |
| `ingest-recettes_plf` | `ingest_recettes_plf.py` | P23 — Recettes du budget général au PLF (S46, État A, data.economie `plf25-recettes-du-budget-general`). Aucune dépendance d'ordre : n'écrit que `recettes_plf_etat_a`. Distinct de S13 (exécution nette, cumul YTD). Recettes BRUTES du projet, pas la LFI. Md€ = euros ÷ 1e9, jamais ÷ 1000. Placé avant `sirene`. |
| `ingest-ircom` | `ingest_ircom.py` | P24 — IRCOM, impôt sur le revenu par collectivité territoriale (S47, DGFiP/DESF). Aucune dépendance d'ordre : n'écrit que `ircom_communes`, `ircom_departements`, `ircom_national`. Distinct de S13 (IR de caisse, cumul YTD). Impôt net SUR RÔLE, année des revenus. Unité native milliers d'euros, stockée en euros (× 1000). Tranches de RFR non ingérées. Placé avant `sirene`. |
| `ingest-rei` | `ingest_rei.py` | P25 — REI, fiscalité directe locale (S48, DGFiP/DESF). Aucune dépendance d'ordre : n'écrit que `rei_communes`, `rei_departements`, `rei_national`. Distinct de S16 (comptes OFGL), S13 (caisse État) et S47 (IRCOM). Impositions primitives du rôle général, année d'imposition. Unité native euros. IFER régional : une valeur par région. Placé avant `sirene`. |
| `ingest-cofog_apu` | `ingest_cofog_apu.py` | P26 — Dépenses des APU par fonction (S49, Eurostat `gov_10a_exp`, CFAP / COFOG-99, na_item=TE, TOTAL+GF01–GF10). Aucune dépendance d'ordre : n'écrit que `cofog_apu_esa`. Distinct de S13 (État YTD), S44 (TE `gov_10a_main`) et S45 (prestations DREES). Pas de groupes, pas de taxag, pas de S.1311. Placé avant `sirene`. |
| `ingest-comptes_apu_insee` | `ingest_comptes_apu_insee.py` | P27 — Comptes des APU (S50, INSEE Insee Résultats 8988845, tableaux 3.201/3.202/3.203/3.205/3.212 et 3.216). Aucune dépendance d'ordre : n'écrit que `comptes_apu_insee`. Distinct de S13 (État YTD), S44 (TE/TR), S42 (B9 non ingéré) et S49 (CFAP). PO ≠ taxag. Sous-secteurs non additifs. Placé avant `sirene`. |
| `ingest-odac_insee` | `ingest_odac_insee.py` | P28 — Dépenses des ODAC (S51, INSEE Insee Résultats 8988845, tableau 3.204, S13112). Aucune dépendance d'ordre : n'écrit que `comptes_odac_insee`. Unité native Md€. B9 non ingéré. Distinct de S50 (autres tableaux) et de S39 (jaune opérateurs, liste, 0 €). S13111 + S13112 ≠ S1311. Placé avant `sirene`. |
| `ingest-sirene` | `ingest_sirene.py` | Stock Sirene — attributs des unités légales citées (S18). **Pipeline dérivé** : il lit les SIREN cités par les autres tables et doit donc passer **après** elles ; sur une base neuve il échoue franchement au lieu d'écrire un référentiel vide. À ne pas confondre avec `pipelines/sirene.py`, qui est la résolution unitaire par API de S10. |

Contrat d'un pipeline :
1. importe `common` (session, `telecharger`, log) et `db` (`connexion`, `init_db`, `upsert_meta`) ;
2. appelle `init_db()` en premier (idempotent) ;
3. télécharge dans `data/raw/<source>/`, transforme (DuckDB si volumineux), écrit ses tables métier en transaction ;
4. termine par `upsert_meta(...)` avec le **compte de lignes réel** et la **date de la donnée la plus récente constatée dans les données** (tri sur le champ date, pas les métadonnées) ;
5. échoue bruyamment (exception, exit ≠ 0) plutôt que d'écrire des données partielles : pas de `meta_sources` mis à jour = ingestion non comptée ;
6. tout paramètre variable (législature 17, seuils 40/60 k€ au 01/04/2026, millésimes) est une constante nommée en tête de module, jamais enfouie.

Côté app : pages de module dans `app/src/app/<module>/page.tsx` (routes de nav : `/depenses`, `/recettes`, `/marches`, `/elus`, `/lobbying`, `/financement`, `/frais`, `/collectivites`, `/documents`, `/donnees` ; `/comprendre` hors nav ; `/alertes` existe, ce n'est pas un onglet) ; requêtes SQL dans `app/src/lib/` (un fichier par domaine), jamais dans les composants client. Le kit `ui/` est partagé : une page module ne le fork pas. Les pages restent des Server Components ; les îles `"use client"` et l'interaction G8 sont décrites dans `docs/NOTES-FRONT.md`.

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
6. **Calibrer le seuil de fraîcheur — en DEUX endroits, sinon la source s'affiche « sans seuil calibré » sur `/donnees`.** Une source sans seuil n'est pas neutre : elle est exclue de la supervision, et sa vignette de la page `/donnees` porte l'état `non_calibre` au lieu d'un état de santé.
   - `/etc/france-transparence/fraicheur.conf` — **ce fichier vit hors du dépôt** : il est sur le serveur, en `0750 root:root`, non versionné, et un dépôt fraîchement cloné ne le contient pas. C'est le référentiel qui fait autorité, lu par la supervision quotidienne `ft-fraicheur`. Une ligne par source : `source_id | unite | seuil_retard_j | seuil_alerte_j | seuil_effondrement_pct | commentaire`, où `unite` vaut `jo` (jours ouvrés, sources qui suivent le calendrier ouvré français) ou `jc` (jours calendaires, tout le reste). Le seuil se calibre sur l'**âge normal observé** de la source, jamais sur le mot de `meta_sources.frequence` : deux sources « quotidiennes » peuvent avoir un âge normal de 2 jours (JORF) ou de 60 jours (scrutins de l'Assemblée pendant la trêve estivale).
   - `app/src/lib/queries/donnees.ts`, table `SEUILS_SOURCES` — **copie versionnée** des mêmes valeurs. La duplication est assumée : le fichier `/etc` n'est pas lisible par l'utilisateur qui construit le site, et il n'existe ni dans un clone neuf ni en CI, qui doivent pourtant produire la même page. Toute modification d'un des deux doit être reportée dans l'autre ; `ft-fraicheur --json` affiche les seuils réellement appliqués côté serveur et sert à vérifier qu'ils n'ont pas divergé.
   - Consigner la calibration retenue et son raisonnement dans la fiche de la source (`docs/SOURCES.md`), pour que le lecteur qui n'a pas accès à la machine sache quels seuils sont en vigueur.
7. **Si le pipeline déclare un cache de plus de 23 h** (`max_age_heures`), l'inscrire dans `/etc/france-transparence/cache-long.conf` — **également hors dépôt**, sur le serveur. Sans cette exception, la purge quotidienne de `data/raw` (23 h) efface le fichier chaque nuit et le `max_age_heures` du pipeline reste sans effet : la source est re-téléchargée intégralement pour rien.
8. Côté app : requêtes dans `app/src/lib/`, page/composants avec **badge de fraîcheur** (§5), jetons DATAVIZ.md uniquement, mentions de licence/attribution si exigées (ODbL, Datan…).
9. Si la source alimente une alerte (A1-A11), documenter la règle de calcul et sa base légale sur la page `/donnees`.

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
