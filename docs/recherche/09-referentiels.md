# 09 — Référentiels transverses

> Recherche menée le **19 août 2026**. Toutes les sources ci-dessous ont été **réellement appelées** (curl / API) ce jour ; les extraits sont des réponses réelles. Rôle de ces référentiels : relier entre elles les données des autres axes (marchés publics, subventions, élus…) — résolution d'entités par SIRET/SIREN, cartographie, ratios €/habitant, fiches institutions et élus.

---

## 1. SIRENE / résolution d'entités

### 1.1 API Recherche d'entreprises (recherche-entreprises.api.gouv.fr) — ★ solution retenue

- **URL testée** : `https://recherche-entreprises.api.gouv.fr/search?q=<texte|SIREN|SIRET>` → **HTTP 200, sans aucune authentification**.
- **Tests réels effectués** (19/08/2026) :
  - `?q=ministère de l'intérieur` → `{"siren":"110014016","nom_complet":"MINISTERE DE L'INTERIEUR","nature_juridique":"7113","siege":{"siret":"11001401600015","adresse":"HOTEL DE BEAUVAU PLACE BEAUVAU 75008 PARIS 08","coordonnees":"48.871315208,2.3164658273",...},"date_mise_a_jour":"2026-08-19T08:07:39"}` — donnée **mise à jour le jour même**.
  - `?q=21750001600019` (SIRET complet) → `{"nom":"VILLE DE PARIS","siren":"217500016","nature_juridique":"7229"}` + le SIRET exact retrouvé dans `matching_etablissements` (libellé commune « PARIS 04 »). **La recherche par SIRET 14 chiffres fonctionne directement.**
  - `?q=552037806` → `{"nom":"VINCI","nature_juridique":"5599","categorie":"GE"}`.
  - `?est_administration=true&departement=69&per_page=1` → HTTP 200, premier résultat FRANCE TRAVAIL — **le filtre `est_administration` fonctionne sans `q`**.
- **Champs utiles à la résolution** : `nom_complet`, `nature_juridique` (catégorie juridique INSEE niveau 3 : `71xx` = État/ministères, `72xx` = collectivités territoriales, `73xx` = établissements publics administratifs, `5xxx` = sociétés commerciales, `9xxx` = associations…), `categorie_entreprise` (PME/ETI/GE), `activite_principale` (NAF), adresse + `coordonnees` GPS du siège, `etat_administratif`, `matching_etablissements` (résolution au niveau établissement).
- **Bonus inattendu** : pour une collectivité, `complements.collectivite_territoriale` contient code INSEE, niveau, **et la liste complète des élus** (nom, prénom, fonction — ex. Ville de Paris : maire « GRÉGOIRE Emmanuel » + 163 conseillers, données RNE). Utilisable pour les fiches institutions.
- **Filtres disponibles** (OpenAPI vérifiée) : `nature_juridique`, `est_administration`, `est_collectivite_territoriale`, `est_association`, `departement`, `region`, `code_commune`, `code_postal`, `tranche_effectif_salarie`, `nom_personne`… Endpoints : `/search` et `/near_point`.
- **Limites** (OpenAPI officielle) : « **au maximum 7 requêtes par seconde par adresse IP** », 30 req/s par ASN ; au-delà → 429. Pas de pagination au-delà de 10 000 résultats (usage recherche, pas extraction massive).
- **Fraîcheur** : quotidienne (Sirene INSEE + RNE) — constatée : `date_mise_a_jour: 2026-08-19`.
- **Licence** : données Sirene/RNE en open data (Licence Ouverte 2.0 côté data.gouv).
- **Piège** : c'est une API de *recherche*, pas d'extraction : pour enrichir des dizaines de milliers de SIRET, passer par les fichiers stock (1.3) et garder l'API pour le temps réel / les trous.
- **Verdict : EXPLOITABLE DIRECT** — usage : résolution d'entités (acheteurs publics, titulaires de marchés) en nom + catégorie + localisation, fiches institutions.

### 1.2 API Sirene INSEE (api.insee.fr)

- **URL testée** : `https://api.insee.fr/api-sirene/3.11/siret/13000495500010` → **HTTP 401** `{"message":"Unauthorized"}`.
- **Accès** : compte sur le portail INSEE + **clé API obligatoire** ; quota public **30 requêtes/minute**.
- **Apport vs 1.1** : accès aux unités « à diffusion partielle », interrogation multicritères exhaustive, données brutes complètes.
- **Verdict : EXPLOITABLE AVEC EFFORT (inutile ici)** — recherche-entreprises + fichiers stock couvrent 100 % du besoin sans clé.

### 1.3 Fichiers stock Sirene (data.gouv.fr)

- **Dataset** : « Base Sirene des entreprises et de leurs établissements (SIREN, SIRET) », éditeur INSEE, **licence lov2 (Licence Ouverte 2.0)**, mise à jour **mensuelle** (dernier millésime constaté : **1er août 2026**).
- **Ressources testées** (HEAD réel) :
  - `StockUniteLegale` CSV zip : **970 595 120 octets** — `https://static.data.gouv.fr/resources/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/20260801-072607/stock-stockunitelegale-csv.zip` → HTTP 200, `last-modified: Sat, 01 Aug 2026 07:26:53 GMT`.
  - **Format Parquet disponible** : StockUniteLegale 705 Mo, StockEtablissement 2,20 Go — parfait pour DuckDB en pipeline de build.
- **Piège** : l'ancien chemin `files.data.gouv.fr/insee-sirene/…` renvoie **404** — passer par l'API data.gouv du dataset pour obtenir les URLs `static.data.gouv.fr` courantes (elles changent à chaque millésime).
- **Verdict : EXPLOITABLE DIRECT** — usage : table locale de résolution SIRET→(nom, catégorie juridique, commune) construite une fois par mois avec DuckDB sur le Parquet.

---

## 2. Géo (communes, départements, régions, contours, centroïdes)

### 2.1 geo.api.gouv.fr — ★ solution retenue pour codes, population, centroïdes

- **Tests réels** (tous HTTP 200, sans auth) :
  - `/communes?nom=Lyon&fields=nom,code,population,centre,codeDepartement&boost=population&limit=1` → `{"nom":"Lyon","code":"69123","population":519127,"centre":{"type":"Point","coordinates":[4.8351,45.758]},"codeDepartement":"69"}`.
  - `/communes/75056?fields=nom,population,centre` → `{"nom":"Paris","population":2103778,"centre":{"coordinates":[2.347,48.8589]}}`. **Vérification croisée** : 2 103 778 = PMUN de Paris dans le fichier INSEE « populations de référence 2023 » (§ 6) → **l'API sert la population légale en vigueur au 01/01/2026**.
  - `/departements?fields=nom,code,codeRegion` → 101 départements ; `/departements/69?fields=nom,chefLieu` → `{"nom":"Rhône","chefLieu":"69123"}` — **le chef-lieu (préfecture) est exposé** ; son centroïde s'obtient via `/communes/{chefLieu}?fields=centre`. Attention : **pas de champ `population` au niveau département** (champ ignoré) → utiliser le fichier INSEE (§ 6).
  - `/regions` → 18 régions (codes INSEE).
  - `/communes/69123?format=geojson&geometry=contour` → contour GeoJSON de Lyon, **13 506 octets**.
  - **Volumétrie France entière** : `/communes?fields=nom,code,centre,population,codeDepartement` → **4,7 Mo en 0,5 s** (≈ 35 000 communes avec centroïde + population en un appel).
- **Formats/géométries** : json/geojson ; `centre` (défaut), `contour`, `mairie`, `bbox`.
- **Licence** : Licence Ouverte (données INSEE/COG + Admin Express IGN, service Etalab/DINUM). Limite de débit non documentée — rester raisonnable, cacher les réponses.
- **Verdict : EXPLOITABLE DIRECT** — usage : référentiel codes INSEE↔noms, centroïdes des points de la carte, population communale.

### 2.2 Contours GeoJSON prêts à l'emploi (fond de carte SVG)

- **france-geojson (gregoiredavid)** — testé sur `raw.githubusercontent.com` :
  - `departements-version-simplifiee.geojson` : HTTP 200, **569 299 octets** — extrait réel : `{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[4.780213…,46.176677…]…`. Propriétés `code`/`nom` par département → jointure directe avec codes INSEE.
  - `regions-version-simplifiee.geojson` : **225 495 octets** ; `metropole-version-simplifiee.geojson` (silhouette France) : **79 095 octets** ; `departements-avec-outre-mer.geojson` : 3,7 Mo ; `communes-version-simplifiee.geojson` : 19,3 Mo (build-time seulement).
  - **Licence** : Licence Ouverte (source IGN Admin Express COG + INSEE). **Piège** : millésime **2018** — sans conséquence pour départements/régions (inchangés depuis 2016), mais des communes fusionnées depuis manqueront au niveau communal.
- **Etalab contours administratifs (millésimés)** — testé : `https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/departements-100m.geojson` → **302** vers OVH S3 puis **HTTP 200, 2 753 929 octets**. Millésimes annuels (2024, 2025…), résolutions 5m/50m/100m/1000m, Licence Ouverte (dérivé Admin Express IGN). **Suivre la redirection (`curl -L`)**.
- **Verdict : EXPLOITABLE DIRECT** — solution carte retenue : **france-geojson `departements-version-simplifiee.geojson` (556 Ko) en frontend**, projeté en SVG (d3-geo, `geoConicConformalFrance` ou fitSize) ; **Etalab 2025** si besoin d'un millésime récent au niveau communal.

### 2.3 Centroïdes préfectures / grandes villes

- Deux voies testées et concordantes :
  1. `geo.api.gouv.fr` : `/departements/{code}` → `chefLieu` → `/communes/{code}?fields=centre` (testé : Rhône → 69123 → [4.8351, 45.758]).
  2. Annuaire de l'administration (§ 5) : les fiches préfectures portent **latitude/longitude exactes du bâtiment** — testé : Préfecture de Vaucluse → `lat/lon: 43.948117 4.82173`.
- **Verdict : EXPLOITABLE DIRECT** — la carte SVG peut positionner des points par coordonnées réelles sans aucun géocodage.

---

## 3. Résultats électoraux (Ministère de l'Intérieur / data.gouv.fr)

### 3.1 « Données des élections agrégées » — ★ solution retenue

- **Dataset** : `https://www.data.gouv.fr/datasets/6481e741d4cf002ec0efec9d/` — org **data.gouv.fr** (consolidation des publications MI), **licence lov2**, dernière maj constatée **2026-07-07**.
- **Ressources** (constatées via API) :
  - « Résultats généraux » : CSV 405,7 Mo / **Parquet 70,9 Mo** (`ff16d511-10c0-405e-9b35-511723948fce`) ;
  - « Résultats par candidat » : CSV 2,38 Go / **Parquet 161,3 Mo** (`4d3b35f6-0b22-4415-a24c-419a676312e2`) ;
  - « Dictionnaire des nuances politiques » — dont celui de la **circulaire INTP2602966C de février 2026** (municipales 2026).
- **Tests réels via l'API tabulaire** (`tabular-api.data.gouv.fr/api/resources/{rid}/data/`), comptes constatés :
  - `id_election=2024_euro_t1` → ligne réelle : `{"code_departement":"01","code_commune":"01001","libelle_commune":"L'Abergement-Clémenciat","code_bv":"0001","inscrits":662,"votants":373,"exprimes":369,"ratio_abstentions_inscrits":43.66,…}` ;
  - `2024_legi_t1` → **70 102** bureaux de vote ; `2026_muni_t1` → **70 003** BV ; `2026_muni_t2` → **17 398** BV — **les municipales de mars 2026 (T1 15/03, T2 22/03) sont bien publiées**.
  - Résultats par candidat, `2026_muni_t1` → **196 661 lignes**, colonnes : `nuance, sexe, nom, prenom, liste, libelle_abrege_liste, libelle_etendu_liste, nom_tete_liste, voix, ratio_voix_exprimes, code_bv…`
- **Granularité** : bureau de vote, agrégeable commune/département ; **pièges** : (a) `code_circonscription` **vide** sur les lignes législatives 2024 testées → pour un regroupement par circonscription, joindre le référentiel REU « bureaux de vote et circonscriptions » ou utiliser les fichiers officiels par circonscription (§ 3.2) ; (b) `nuance` vide pour les petites communes aux municipales (pas de nuançage sous le seuil MI) ; (c) préférer le **Parquet** (DuckDB) au CSV.
- **Verdict : EXPLOITABLE DIRECT** — un seul dataset, tous les scrutins, format homogène.

### 3.2 Datasets MI par scrutin (source primaire)

- **Municipales 2026** — testé via API data.gouv :
  - T1 : `elections-municipales-2026-resultats-du-premier-tour` (MI, lov2, maj 2026-03-20) — fichiers réels : « Municipales 2026 - Candidats Elus - Tour 1 » (34,75 Mo), « Résultats - BV par communes » (37,68 Mo), + Polynésie et conseils d'arrondissement Paris/Lyon/Marseille.
  - T2 : `elections-municipales-2026-resultats-du-second-tour` (MI, lov2, maj 2026-03-23).
- **Législatives 2024** : listes des candidats T1/T2 sur data.gouv (`elections-legislatives-des-30-juin-et-7-juillet-2024-liste-des-candidats-du-1er-tour` / `…-2nd-tour`) ; résultats par BV consolidés dans § 3.1 (`2024_legi_t1`/`t2`).
- **Européennes 2024** : couvertes par § 3.1 (`2024_euro_t1`, testé).
- **Verdict : EXPLOITABLE DIRECT** (fichiers « Candidats Elus » utiles pour la liste des maires élus 2026).

---

## 4. Votes des eurodéputés français

### 4.1 HowTheyVote.eu — ★ solution retenue

- **API testée** : `https://howtheyvote.eu/api/votes?page=1&page_size=1` → HTTP 200, **2 421 votes** au total ; dernier vote constaté : 2026-07-09 « Feasibility of a 28th tax regime… » (`A10-0167/2026`), avec concepts EuroVoc et sujets OEIL.
- **Détail d'un vote** : `/api/votes/194869` → `member_votes` = **719 positions**, dont **81 France** — extrait réel : `Grégory ALLIONE | RENEW | FOR`, `Mathilde ANDROUËT | PFE | AGAINST`, `Manon AUBRY | GUE_NGL | AGAINST`. Champs : position (FOR/AGAINST/ABSTENTION/DID_NOT_VOTE), groupe politique, pays. Recherche plein texte `?q=` OK (testé).
- **Dumps hebdomadaires** (GitHub `HowTheyVote/data`, testé via API GitHub) : release **2026-08-15** (4 jours avant cette recherche) — `export.zip` 68,6 Mo + CSV.gz par table (`members`, `votes`, `member_votes`, `eurovoc_concept_votes`…).
- **Couverture** : depuis la 9e législature (juillet 2019). **Licence : ODbL** (base) + DbCL (contenus) — **attribution obligatoire** « HowTheyVote.eu » ; API qualifiée d'expérimentale par l'éditeur.
- **Verdict : EXPLOITABLE DIRECT** — usage : fiches eurodéputés FR (taux de participation, votes clés par thème EuroVoc).

### 4.2 Open data du Parlement européen (data.europarl.europa.eu)

- **Testé** : `/api/v2/meps?country-of-representation=FR&parliamentary-term=10&limit=2` → HTTP 200, JSON-LD : `{"identifier":"22858","label":"Fabienne KELLER"…}` — référentiel officiel des 81 eurodéputés FR (10e législature).
- **Votes nominatifs** : `/api/v2/meetings/MTG-PL-2026-07-09/decisions` → HTTP 200 mais **1,12 Mo pour `limit=1`**, JSON-LD très verbeux, reconstruction des positions individuelles laborieuse.
- **Verdict : EXPLOITABLE AVEC EFFORT** — à réserver au référentiel officiel des députés (photo, mandats) ; les votes passent par HowTheyVote.

---

## 5. Annuaire de l'administration (api-lannuaire.service-public.fr)

- **API testée** (Opendatasoft Explore v2.1, **sans auth**) : `https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration/records?where=pivot LIKE "prefecture"&limit=1` → HTTP 200, **107 préfectures** ; fiche réelle : `Préfecture - Vaucluse`, `siren: 178400016`, `code_insee_commune: 84007`, adresse structurée avec **latitude/longitude** (43.948117, 4.82173), horaires d'ouverture, sites web, réseaux sociaux ; copyright « Direction de l'information légale et administrative (Premier ministre) ».
- **Volumétrie** : **94 117 fiches** (métadonnées du dataset). Le champ `pivot` filtre par type (`prefecture`, `mairie`, `conseil_departemental`…) — **piège** : pas de pivot `ministere` (0 résultat testé) ; les administrations centrales se cherchent par `nom` ou via d'autres pivots.
- **Aussi référencée** sur data.gouv comme dataservice « API Annuaire de l'administration et des services publics » (Premier ministre), base URL récente `api-lannuaire.service-public.gouv.fr` (l'ancienne en `.fr` répond toujours). Licence non renseignée dans les métadonnées API ; données DILA diffusées en open data (réutilisation type Licence Ouverte, mention DILA recommandée).
- **Verdict : EXPLOITABLE DIRECT** — usage : fiches institutions (contact, site, géolocalisation, SIREN → jointure SIRENE), points préfectures pour la carte.

---

## 6. Population INSEE (ratios €/habitant)

- **Source retenue** : INSEE « **Populations de référence 2023** » (nouveau nom des populations légales), authentifiées par **décret n° 2025-1362 du 26 décembre 2025**, **en vigueur au 1er janvier 2026** — le référentiel officiel valable en août 2026.
- **Fichier d'ensemble testé et téléchargé** : `https://www.insee.fr/fr/statistiques/fichier/8680726/ensemble.zip` → HTTP 200, **1 032 385 octets**. Contenu réel : `donnees_communes.csv` (**34 900 communes** : `REG;DEP;CODCOM;COM;Commune;PMUN;PCAP;PTOT`), `donnees_departements.csv` (**101** : `…;NBCOM;PMUN;PTOT` — ex. `Ain;391;679344;694945`), `donnees_regions.csv`, cantons, arrondissements.
- **Extrait réel** : `84;Auvergne-Rhône-Alpes;01;2;08;001;01001;L'Abergement-Clémenciat;860;16;876` ; Paris (arrondissement) : `PMUN 2103778; PTOT 2119412`.
- **Cohérence** : PMUN = valeur servie par geo.api.gouv.fr (vérifié sur Paris) → pour les communes, l'API géo suffit ; pour **départements et régions**, prendre ce CSV (l'API géo n'expose pas la population à ces niveaux).
- **Règle** : utiliser **PMUN** (population municipale) pour les ratios €/habitant. Licence : mentions INSEE, réutilisation libre (Licence Ouverte 2.0).
- **Verdict : EXPLOITABLE DIRECT** — 1 Mo, un téléchargement par an.

---

## 7. Tableau récapitulatif

| Source | URL testée | Accès | Format | Fraîcheur constatée | Licence | Verdict | Usage cible |
|---|---|---|---|---|---|---|---|
| API Recherche d'entreprises | recherche-entreprises.api.gouv.fr/search | **Sans auth**, 7 req/s/IP | JSON | maj quotidienne (19/08/2026 vu) | LO 2.0 | **EXPLOITABLE DIRECT** | Résolution SIRET→nom/catégorie/localisation, fiches |
| API Sirene INSEE | api.insee.fr/api-sirene/3.11 | **Clé API** (401 testé), 30 req/min | JSON | quotidienne | LO 2.0 | AVEC EFFORT (inutile) | — |
| Stock Sirene (Parquet/CSV) | static.data.gouv.fr (dataset base-sirene…) | Libre | **Parquet** 705 Mo / 2,2 Go, CSV zip | mensuelle (01/08/2026) | lov2 | **EXPLOITABLE DIRECT** | Table locale de résolution massive |
| geo.api.gouv.fr | /communes /departements /regions | Sans auth | JSON/GeoJSON | pop. réf. 2023 (en vigueur 2026) | LO | **EXPLOITABLE DIRECT** | Codes, centroïdes, pop. communale, contours unitaires |
| france-geojson | raw.githubusercontent.com/gregoiredavid/… | Libre | GeoJSON 79 Ko–19 Mo | contours 2018 (stables dép./rég.) | LO (IGN) | **EXPLOITABLE DIRECT** | Fond de carte SVG (556 Ko départements) |
| Contours Etalab millésimés | etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/… | Libre (302→OVH S3) | GeoJSON (100m : 2,75 Mo) | millésime 2025 | LO | EXPLOITABLE DIRECT | Fond de carte récent / communes |
| Données des élections agrégées | data.gouv.fr/datasets/6481e741…, tabular-api | Libre + API tabulaire | **Parquet 71/161 Mo**, CSV | maj 07/2026, municipales 2026 incluses | lov2 | **EXPLOITABLE DIRECT** | Résultats euro 2024, légis. 2024, municipales 2026 au BV |
| Municipales 2026 (MI, brut) | …/elections-municipales-2026-resultats-du-premier/second-tour | Libre | CSV (35–38 Mo) | T1 20/03, T2 23/03/2026 | lov2 | EXPLOITABLE DIRECT | Élus 2026, contrôle de la source agrégée |
| HowTheyVote.eu | howtheyvote.eu/api/votes + dumps GitHub | Sans auth | JSON / CSV.gz (export 68,6 Mo) | release 15/08/2026, hebdo | **ODbL** (attribution) | **EXPLOITABLE DIRECT** | Votes des 81 eurodéputés FR |
| Europarl open data | data.europarl.europa.eu/api/v2 | Sans auth | JSON-LD verbeux | 10e législature | réutilisation avec mention | AVEC EFFORT | Référentiel officiel des députés |
| Annuaire administration | api-lannuaire.service-public.fr /explore/v2.1 | Sans auth | JSON (ODS) | 94 117 fiches | DILA (open data) | **EXPLOITABLE DIRECT** | Fiches institutions, lat/lon préfectures |
| Populations de référence 2023 | insee.fr/fr/statistiques/fichier/8680726/ensemble.zip | Libre | ZIP de CSV (1 Mo) | décret 26/12/2025, vigueur 01/01/2026 | INSEE/LO | **EXPLOITABLE DIRECT** | Ratios €/habitant (PMUN) commune/dép./région |

---

## 8. Solutions retenues (architecture)

**Résolution SIRET (acheteurs, titulaires)** — deux étages :
1. *Pipeline de build* : DuckDB sur **StockUniteLegale Parquet** (mensuel) → table `siren → (nom, nature_juridique, catégorie, commune)` ; classification public/privé par préfixe de `nature_juridique` (`4`/`7` = public, `71` État, `72` collectivités, `73` EPA ; `5`/`1` = privé ; `92xx` associations).
2. *Temps réel / trous* : **API recherche-entreprises** (`?q=SIRET`, 7 req/s, sans clé), qui rend aussi coordonnées GPS, établissement exact et élus des collectivités.

**Carte de France SVG** : fond **france-geojson `departements-version-simplifiee.geojson`** (556 Ko, jointure par `code` INSEE), projection conique conforme France (d3-geo) ; **points** = centroïdes réels `centre` de geo.api.gouv.fr (35 000 communes + population en un appel de 4,7 Mo ; chefs-lieux via `chefLieu`) ou lat/lon des préfectures de l'annuaire DILA. Aucun géocodage nécessaire.

**Ratios €/habitant** : `donnees_departements.csv` / `donnees_communes.csv` (PMUN, populations de référence 2023) joints par code INSEE ; correspondance SIRET→commune via SIRENE, commune→département via geo API.

**Élections** : Parquet « Données des élections agrégées » (résultats généraux 71 Mo + par candidat 161 Mo) filtré par `id_election` ∈ {2024_euro_t1, 2024_legi_t1/t2, 2026_muni_t1/t2} ; nuances via le dictionnaire de la circulaire de février 2026. Piège circonscriptions (§ 3.1) à traiter si un niveau circo est requis.

**Votes eurodéputés** : dumps CSV HowTheyVote (hebdo) filtrés `country=FRA`, attribution ODbL affichée sur le dashboard.

**Impossibilités / renoncements** : API Sirene INSEE sans clé (401) ; extraction massive via recherche-entreprises (plafond de pagination) ; population départementale via geo API (champ absent) ; pivot `ministere` inexistant dans l'annuaire ; votes du PE d'avant juillet 2019 non couverts par HowTheyVote.
