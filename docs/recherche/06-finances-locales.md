# 06 — Finances locales (collectivités territoriales)

**Axe** : comptes des communes/départements/régions/EPCI, balances comptables, comptes individuels, subventions versées, dotations de l'État.
**Date de vérification : 19 août 2026.** Toutes les URL ci-dessous ont été appelées réellement (curl, codes HTTP et extraits reproduits). Sources classées par ordre d'exploitabilité.

---

## 1. OFGL — data.ofgl.fr (Observatoire des Finances et de la Gestion publique Locales)

**Verdict : EXPLOITABLE DIRECT — source pivot de l'axe.**

- **URL testées** :
  - Catalogue : `https://data.ofgl.fr/api/explore/v2.1/catalog/datasets?limit=100` → **HTTP 200**, 92 jeux de données.
  - Records : `https://data.ofgl.fr/api/explore/v2.1/catalog/datasets/ofgl-base-communes/records` → HTTP 200.
  - Export filtré : `https://data.ofgl.fr/api/explore/v2.1/catalog/datasets/ofgl-base-communes/exports/csv?where=...` → HTTP 200.
- **Accès** : API Opendatasoft Explore v2.1, sans clé, sans authentification. Exports CSV/JSON/Parquet/Excel.
- **Format** : JSON (records, group_by) ou CSV/Parquet (exports). ODSQL (`where`, `select`, `group_by`, agrégats serveur).
- **Licence** : Licence Ouverte v2.0 (Etalab) — confirmée dans les métadonnées de `ofgl-base-communes` et sur le miroir data.gouv (lov2).

### Jeux de données clés (état réel au 19/08/2026)

| Dataset | Période | Lignes | Dernière MAJ |
|---|---|---|---|
| `ofgl-base-communes` (comptes des communes) | 2018–**2025** | 21 973 458 | 2026-07-29 |
| `ofgl-base-communes-consolidee` (BP + budgets annexes consolidés) | 2018–2025 | 13 605 432 | 2026-07-28 |
| `ofgl-base-departements` | 2012–**2025** | 318 638 | 2026-08-05 |
| `ofgl-base-departements-fonctionnelle` (ventilation par fonction) | 2012–2025 | 865 735 | 2026-08-05 |
| `ofgl-base-regions` / `-consolidee` | 2012–2025 | 24 532 / 14 547 | 2026-07-17 |
| `ofgl-base-gfp` (EPCI à fiscalité propre) / `-consolidee` | 2018–2025 | 3 149 085 / 508 116 | 2026-07-22 |
| `ofgl-base-ei` (ensembles intercommunaux = EPCI + communes membres) | 2018–2025 | 533 804 | 2026-07-28 |
| `dotations-communes` (montants **et critères**) | 2018–**2026** | 27 108 043 | 2026-08-04 |
| `dotations-departements` / `dotations-gfp` / `dotations-regions` | — | 50 455 / 777 890 / 485 | 2026-08-04 / 2026-08-04 / 2026-05-29 |
| `rei` (fiscalité directe locale) | 2024–2025 | 22 774 886 | 2026-05-29 |
| Également : syndicats, SDIS, CCAS-CIAS, EPL, FPIC, actif réévalué 2025 | | | |

### Granularité
Format long : 1 ligne = collectivité × exercice × budget × **agrégat**. 55 agrégats financiers listés par `group_by=agregat` (extrait réel) : Dépenses/Recettes de fonctionnement, Dépenses d'équipement, Frais de personnel, Achats et charges externes, Épargne brute/nette, Encours de dette, Annuité de la dette, DGF, Impôts locaux, Subventions aux personnes de droit privé, etc. Champs : `exer`, `com_code`/`insee`, `siren`, `type_de_budget`, `agregat`, `montant`, **`euros_par_habitant`**, `ptot`, + contexte (strate, EPCI, rural/montagne/touristique/QPV).

### Fraîcheur (vérifiée dans le journal officiel `historique-maj-jeux-donnees`)
- 2026-07-28 : « Ajout des données **2025** » sur `ofgl-base-communes-consolidee` — « les données 2025 de quelques communes sont encore manquantes » (~97 communes selon `disponibilite-des-comptes-des-communes`, complétées fin décembre avec les balances définitives DGFiP).
- 2026-08-05 : données 2025 ajoutées à `ofgl-base-departements-fonctionnelle`.
- Le millésime N est donc chargé en juillet N+1 (comptes provisoires), consolidé en décembre N+1.

### Requêtes réelles jouées
Dépenses de fonctionnement de Marseille, dernier millésime :
```
GET /records?where=com_code="13055" and year(exer)=2025 and agregat="Dépenses de fonctionnement"
              and type_de_budget="Budget principal"
→ {"exer":"2025","com_name":"Marseille","montant":1339679971.72,
   "euros_par_habitant":1516.39,"ptot":883466}
```
Agrégation serveur pour la carte départementale (1 seule requête, HTTP 200) :
```
GET /records?group_by=dep_code&select=sum(montant)/sum(ptot) as eur_hab&...  → 101 départements
{"dep_code":"01","total":614361946.33,"pop":686804,"eur_hab":894.52}
{"dep_code":"05","total":221320201.17,"pop":145336,"eur_hab":1522.82}
```
Export CSV filtré niveau commune (toutes les communes, 1 agrégat, 2025) : **34 778 lignes, 1,9 Mo, 2,8 s** :
```
com_code;com_name;dep_code;montant;euros_par_habitant;ptot
21022;Argilly;21;330796.95;599.27;552
```
DGF 2026 de Lyon via `dotations-communes` (HTTP 200) : `{"variable":"Montant Dotation DGF","valeur":56959311.0,"unite":"euros"}` — les dotations sont disponibles jusqu'à l'exercice **2026** inclus (exercices 2018→2026 vérifiés par `group_by=exercice`).

### Volumétrie et stratégie
Bases massives (22 M lignes communes) mais **jamais besoin de tout télécharger** : l'endpoint `/exports/csv` accepte `where`+`select` et streame sans plafond ; l'endpoint `/records` est plafonné à 10 000 résultats (offset+limit) — utiliser exports ou group_by au-delà.

### Pièges
- `exer`/`exercice` sont des **dates** → filtrer par `year(exer)=2025` (comparaison à un entier → HTTP 400 `IncompatibleTypesInComparisonFilter`, constaté).
- Plusieurs budgets par collectivité → toujours filtrer `type_de_budget="Budget principal"` ou utiliser la base `-consolidee` (vérifié sur le département 13 : 6 lignes « Dépenses de fonctionnement » 2025, budgets annexes mêlés).
- Dans les bases consolidées, les millésimes anciens (ex. 2017) sont retirés du jeu et déplacés **en pièces jointes** (journal de MAJ du 2026-07-28).
- ~97 communes sans comptes 2025 avant décembre 2026.
- `dotations-*` : format long `variable`/`valeur` (7 variables rien que pour « DGF » à Lyon) → dictionnaire des variables à figer avant usage.

**Module cible** : cœur du module « finances-locales » — carte de France, fiches collectivité (séries 2012/2018→2025), dotations, fiscalité.

---

## 2. Balances comptables des collectivités — DGFiP, data.economie.gouv.fr

**Verdict : EXPLOITABLE DIRECT (en accès ciblé) — le détail comptable derrière OFGL.**

- **URL testées** :
  - Catalogue : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets?where=search(dataset_id,"balances-comptables")` → **HTTP 200**, 35 jeux.
  - Records 2025 : `.../datasets/balances-comptables-des-communes-en-2025/records` → HTTP 200.
  - Export : `.../balances-comptables-des-communes-en-2025/exports/csv` → HTTP 200 (flux, en-têtes vérifiés par `curl -sI`).
- **Accès** : API Opendatasoft v2.1 sans clé. **Rate limit constaté dans les en-têtes : 50 000 appels/jour** (`x-ratelimit-limit: 50000`).
- **Licence** : Licence Ouverte v2.0 (Etalab) — métadonnées du jeu 2025.

### État réel des millésimes (vérifié au catalogue)
- Communes : **un dataset par année 2010→2025**. `balances-comptables-des-communes-en-2025` : **6 963 040 lignes, MAJ 2026-07-13**. Description officielle : fichier « Balance_Commune_**2025_Juil2026** » → balances **provisoires de juillet**, définitives en décembre (cycle DGFiP standard).
- Départements (`balances-comptables-des-departements`, 574 002 lignes), régions (44 199), GFP depuis 2010 (6 410 444), syndicats (5 989 163), EPL (8 374 498) : jeux multi-années uniques, tous MAJ 2026-07-13.
- Présentation croisée nature-fonction 2025 : 5 326 293 lignes (MAJ 2026-07-13).

### Granularité
1 ligne = budget (SIRET) × **compte comptable** (M57/M14…, champ `nomen`) : `exer, ident, ndept, lbudg, insee, siren, nomen, compte, obnetdeb, obnetcre, sd, sc…` — le grain le plus fin disponible publiquement.

### Requête réelle jouée
```
GET /records?where=siren="211300553" and startswith(compte,"6411")   (Marseille, 2025)
→ {"lbudg":"MARSEILLE","compte":"64118","obnetdeb":92904283.01}
  {"lbudg":"MARSEILLE - OPERA ET ODEON","compte":"64111","obnetdeb":2369420.18}
```

### Volumétrie — stratégie d'échantillonnage
Mesure réelle : 10 000 lignes CSV = 1 427 259 octets → **~143 o/ligne, soit ≈ 950 Mo le CSV communes 2025** (7 M lignes). Ne jamais aspirer l'export intégral dans le dashboard :
1. requêtes API ciblées par `siren` (fiche collectivité, à la demande) ;
2. si besoin d'un lot : export `/exports/csv?where=ndept="013"` (par département) ;
3. si besoin national : fichier attaché « Balance_Commune_2025_Juil2026 » (recommandé par la DGFiP elle-même) ou export Parquet, en batch hors-ligne.

### Pièges (tous constatés)
- `ndept` sur **3 caractères** (« 013 », « 059 ») et `insee` **tronqué aux 3 derniers caractères** (« 055 » pour Marseille) → le filtre `insee="13055"` renvoie 0 ligne. **Joindre par `siren`** (clé fiable, commune Marseille = 211300553).
- Budgets annexes mêlés au principal (Opéra/Odéon ci-dessus) → filtrer sur `cbudg`/`codbud1`.
- Données au compte : reconstruire des agrégats exige la nomenclature (M57A/M14…) — c'est exactement le travail déjà fait par l'OFGL ; formules publiées dans `methodologie-ofgl-formules-des-agregats-financiers` (64 080 lignes).
- Le fichier 2025 inclut la **Ville de Paris fusionnée** (commune + département).
- 2025 = balances provisoires jusqu'à la publication définitive de décembre 2026.

**Module cible** : « fiche collectivité — détail comptable » (drill-down à la demande depuis la fiche OFGL) ; contrôle de cohérence des agrégats.

---

## 3. Dotations de l'État (DGF) — OFGL `dotations-*` et portail DGCL

**Verdict : EXPLOITABLE DIRECT via OFGL ; portail DGCL = source primaire de contrôle.**

- **OFGL `dotations-communes`** (détail section 1) : DGF et autres dotations, **montants + critères de répartition**, 2018→**2026**, 27,1 M lignes, API. Requête réelle : DGF 2026 de Lyon = 56 959 311 €. C'est la voie d'ingestion recommandée.
- **Portail primaire DGCL** : `http://www.dotations-dgcl.interieur.gouv.fr/consultation/criteres_repartition.php` → **HTTP 200** (testé). Fichiers **Excel** par millésime et catégorie ; les critères 2026 y sont en ligne depuis le 20/07/2026 (AMF/DGCL). Consultation individuelle par commune également. Pas d'API.
- **data.gouv.fr** : dataset DGCL « Critères de répartition des dotations versées par l'État » **gelé depuis 2020-01-10** (vérifié via l'API data.gouv) — ne pas s'y fier.

**Pièges** : format long `variable`/`valeur` chez OFGL (choisir « Montant Dotation DGF » parmi 7 variables contenant « DGF ») ; chez la DGCL, fichiers Excel à colonnes changeantes selon millésime.

**Module cible** : « dotations de l'État » — carte DGF/hab et évolution par commune, alimentée par OFGL (2018-2026).

---

## 4. Comptes individuels des collectivités — data.economie.gouv.fr (fichiers globaux) et impots.gouv.fr

**Verdict : EXPLOITABLE AVEC EFFORT — utile pour les ratios de strate, sinon redondant avec OFGL et moins frais.**

- **URL testées** :
  - `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/comptes-individuels-des-communes-fichier-global-2023-2024/records?where=inom="MARSEILLE"` → **HTTP 200**.
  - Catalogue : 50 jeux « comptes-individuels-* / agregats-* » (communes, départements/CTU, régions, GFP, par tranches de millésimes).
  - Site de consultation : `https://www.impots.gouv.fr/cll/zf1/accueil/flux.ex?_flowId=accueilcclloc-flow` → **HTTP 200** (fiches HTML interactives, pas de bulk).
  - Le dataset data.gouv « Comptes individuels des collectivités » (MAJ 2021) ne fait que pointer vers ces deux ressources ; sa copie ODS directe est **vide** (0 enregistrement, constaté).
- **Format** : datasets tabulaires ODS. Fichier communes 2023-2024 : **69 877 lignes × 252 champs** (MAJ 2025-12-01). 1 ligne = commune × année : produits/charges/dette/DGF… avec pour chaque grandeur la valeur (`prod`), le €/hab (`fprod`) et la **moyenne de la strate** (`mprod`) — c'est l'apport unique de cette source.
- **Extrait réel** (Marseille, an=2023) : `prod=1364813.37, charge=1209472.04, dette=1305591.55, fprod=1556.94` — **montants en milliers d'euros** (piège n°1).
- **Fraîcheur** : s'arrête à **2024** (2023-2024 publié le 01/12/2025) ; le millésime 2025 n'existe pas encore ici alors qu'OFGL l'a depuis juillet 2026.
- **Licence** : Licence Ouverte 2.0 (politique open data DGFiP, confirmée par impots.gouv.fr).
- **Pièges** : un dataset par tranche de millésimes aux slugs incohérents (`...-20090`), 252 colonnes peu documentées, montants en k€, retard d'un an sur OFGL.

**Module cible** : enrichissement de la fiche collectivité (« où se situe la commune dans sa strate »), pas d'ingestion de masse.

---

## 5. Subventions versées par les collectivités — schéma SCDL, data.gouv.fr et portails locaux

**Verdict : EXPLOITABLE AVEC EFFORT — couverture nationale IMPOSSIBLE en l'état, agrégation manuelle ciblée obligatoire.**

- **URL testées** :
  - Recensement officiel : `https://www.data.gouv.fr/api/1/datasets/?schema=scdl%2Fsubventions&page_size=200` → **HTTP 200, total = 53 datasets** émanant de ~45 organisations. Attention : le slug est `scdl/subventions` (le filtre `schema=scdl-subventions` renvoie 0).
  - Registre des schémas : `https://www.data.gouv.fr/api/1/datasets/schemas/` → schéma « scdl/subventions », version courante 2.1.1, **`consolidation_dataset_id: None` → il n'existe AUCUNE consolidation nationale officielle** (contrairement à d'autres schémas).
  - Fichier réel le plus frais : Côtes-d'Armor (MAJ 2026-08-16), `https://datarmor.cotesdarmor.fr/data-fair/api/v1/datasets/subventions-versees-par-le-conseil-departemental-des-cotes-darmor-aux-associations-depuis-2016-decret/raw` → HTTP 206, CSV 3,7 Mo, **strictement conforme SCDL** :
    `"nomAttribuant","idAttribuant","dateConvention",...,"nomBeneficiaire","idBeneficiaire","objet","montant","nature",...`
    `"Département des Côtes d Armor",22220001600327,2015-04-05,...,"STEREDENN",78162654400014,...,4000.0,...`
  - Paris : `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/subventions-associations-votees-/records` → HTTP 200, **107 693 lignes, MAJ 2026-07-28, exercices jusqu'à 2026** (extrait réel : `{"annee_budgetaire":"2026","nom_beneficiaire":"A.S PARIS 17","numero_siret":"92322612000015","montant_vote":1500}`) — mais **format maison, pas SCDL** (+ `subventions-versees-annexe-compte-administratif` 47 381 lignes).
  - Île-de-France (`data.iledefrance.fr`) : 14 datasets « subvention », majoritairement anciens ou thématiques — pas de flux SCDL global.
- **Qui publie réellement au schéma** (recensement du 19/08/2026) : quelques départements (Côtes-d'Armor 2026, Savoie 2025, Eure-et-Loir 2025, Cher 2026, Pyrénées-Orientales, Ille-et-Vilaine, Morbihan…), Métropole de Lyon + Ville de Lyon (2025), villes moyennes (Antibes 2026, Vaulx-en-Velin 2026, Rillieux-la-Pape 2026, Quimper 2026, Villejuif, Charleville-Mézières…), et des publieurs hors cible (CCI, GIP, ANRS). **Ni Paris, ni les grandes régions n'y figurent** — elles publient sur leurs portails avec leurs propres schémas.
- **Licence** : Licence Ouverte 2.0 en général (à vérifier dataset par dataset).
- **Pièges** : obligation légale (>3 500 hab, >50 agents, >23 k€) massivement inappliquée ; `idBeneficiaire` (SIRET) parfois vide (constaté dès la 2ᵉ ligne du fichier Armor) ; portails hétérogènes (ODS, data-fair, dépôt simple) ; périodes couvertes disparates ; doublons entre attributions votées et versements. Data.Subvention (datasubvention.beta.gouv.fr) agrège pour les **agents publics** mais n'expose pas d'open data global.
- **Stratégie réaliste** : module limité à un panel assumé (Paris + Lyon + départements SCDL frais), avec date de collecte et mention de non-exhaustivité ; re-scan périodique du filtre `schema=scdl/subventions`.

**Module cible** : « subventions aux associations » (panel de grandes collectivités), jamais présenté comme national.

---

## La carte de France : quelle source l'alimente le mieux ?

**Réponse nette : OFGL (`ofgl-base-communes` / `ofgl-base-departements`), sans concurrence.**

1. **Carte départementale** (dépenses/hab, dette/hab, DGF/hab…) : une seule requête `group_by=dep_code` avec agrégats serveur → 101 lignes (testé, extrait en section 1). Idem par région ou EPCI.
2. **Carte communale** : export CSV filtré (1 agrégat × 1 exercice × budget principal) → **34 778 communes, 1,9 Mo, 2,8 s** (testé), champ `euros_par_habitant` déjà calculé. Pré-calculer un fichier par indicateur au build, pas d'appel à la volée.
3. **Fonds de carte** : `https://geo.api.gouv.fr` testé (HTTP 200, contour GeoJSON de Marseille 154 Ko) ; utiliser admin-express/france-geojson en statique pour les 35 000 communes.
4. Les balances DGFiP sont inutilisables pour la carte (grain compte, ~950 Mo/an, codes INSEE tronqués) ; les comptes individuels s'arrêtent à 2024.

Les fiches par collectivité s'appuient sur : OFGL (séries d'agrégats + €/hab + strate), comptes individuels (comparaison à la strate), balances (drill-down comptable), dotations OFGL (DGF 2018-2026), subventions locales quand publiées.

---

## Tableau récapitulatif

| Source | URL testée | Accès | Granularité | Fraîcheur réelle (19/08/2026) | Volumétrie | Licence | Verdict |
|---|---|---|---|---|---|---|---|
| OFGL comptes | data.ofgl.fr (API ODS v2.1) | API sans clé + exports | collectivité × budget × agrégat (55) | **2025** chargé (juil.-août 2026, ~97 communes manquantes → déc.) | 22 M lignes communes ; export filtré 1,9 Mo | LO 2.0 | **EXPLOITABLE DIRECT** |
| OFGL dotations | data.ofgl.fr `dotations-*` | API sans clé | commune × variable (montants + critères) | **2026** inclus (MAJ 04/08/2026) | 27,1 M lignes | LO 2.0 | **EXPLOITABLE DIRECT** |
| Balances DGFiP | data.economie.gouv.fr | API sans clé (50 k appels/j) | budget × compte | **2025 provisoire** (Juil2026, MAJ 13/07/2026), définitif déc. | ~7 M lignes/an ≈ 950 Mo CSV | LO 2.0 | **EXPLOITABLE DIRECT** (accès ciblé) |
| Comptes individuels | data.economie.gouv.fr `fichier-global-*` + impots.gouv.fr/cll | API sans clé / fiches HTML | commune × année, 252 champs (k€, ratios strate) | **2024** max (publié 12/2025) | 70 k lignes/biennium | LO 2.0 | **AVEC EFFORT** |
| Subventions SCDL | data.gouv.fr `?schema=scdl/subventions` + portails locaux | fichiers CSV hétérogènes | attribution (bénéficiaire SIRET, montant, objet) | 53 datasets, dont frais 2026 (Armor 16/08, Paris hors schéma 28/07) | qq Mo par collectivité | LO 2.0 (généralement) | **AVEC EFFORT** (jamais national) |
| DGF data.gouv (DGCL) | data.gouv.fr | fichiers | commune | **gelé 2020** | — | LO 2.0 | **INEXPLOITABLE** (remplacé par OFGL/portail DGCL) |
| Portail DGCL dotations | dotations-dgcl.interieur.gouv.fr | téléchargement Excel, pas d'API | commune × critère | critères **2026** en ligne (20/07/2026) | 1 xlsx/millésime | mention légale à vérifier | **AVEC EFFORT** (contrôle) |

## Impossibilités constatées
- **Aucune consolidation nationale des subventions SCDL** (`consolidation_dataset_id: None`) : toute vue « France entière » des subventions serait mensongère.
- **Pas de comptes 2025 définitifs avant décembre 2026** (balances provisoires de juillet ; ~97 communes absentes chez OFGL).
- **Comptes individuels DGFiP limités à 2024** ; site impots.gouv.fr/cll sans export de masse.
- **Codes INSEE inutilisables tels quels dans les balances** (tronqués) : jointures par SIREN uniquement.
