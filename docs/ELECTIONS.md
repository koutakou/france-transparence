# Participation électorale (source S26)

Pipeline `pipelines/ingest_elections.py` · tables `elections_participation_departement`
et `elections_participation_ville` · requêtes `app/src/lib/queries/elections.ts` ·
affichage `app/src/components/client/ParticipationElectorale.tsx` (bloc de `/collectivites`).

Mesures de ce document : relevées le **20/08/2026** sur le parquet du 07/07/2026
et sur la base de travail, chaque chiffre par une commande rejouable.

---

## 1. Source

| | |
|---|---|
| Jeu | **Données des élections agrégées** — `6481e741d4cf002ec0efec9d` |
| Page | https://www.data.gouv.fr/datasets/donnees-des-elections-agregees |
| Producteur | Ministère de l'Intérieur (publication data.gouv.fr) |
| Licence | **lov2** — Licence Ouverte 2.0, confirmée par l'API data.gouv le 20/08/2026 |
| Ressource ingérée | `general_results.parquet`, **70 866 179 octets**, 25 colonnes, **3 162 440 lignes**, **56 scrutins de 1999 à 2026** |
| URL de la ressource | `https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/elections/general_results.parquet` |
| Dernière modification amont | 07/07/2026 |
| Cadence | `punctual` côté data.gouv → `par scrutin` dans `meta_sources` (même convention que S29) |

Le parquet « Résultats généraux » **ne contient aucun nom de personne** : ses
25 colonnes sont des identifiants géographiques et cinq effectifs (`inscrits`,
`abstentions`, `votants`, `blancs`, `nuls`, `exprimes`) plus leurs ratios.
Granularité native : le **bureau de vote**.

```bash
# licence, taille, date de modification
curl -sS "https://www.data.gouv.fr/api/1/datasets/donnees-des-elections-agregees/" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['license'], d['last_update'])"
# → lov2 2026-07-07T14:01:07+00:00
```

## 2. Périmètre retenu

**Participation seulement.** Deux tables, aucun taux stocké (les ratios sont
calculés à l'affichage : un taux en base se lirait comme un zéro là où la
donnée manque).

| Table | Lignes | Grain |
|---|---:|---|
| `elections_participation_departement` | **740** | 7 scrutins × 102 à 107 départements et collectivités |
| `elections_participation_ville` | **1 524** | 7 scrutins × les communes déjà connues du site |

Colonnes : `id_election`, code et libellé de la collectivité, `inscrits`,
`votants`, `blancs`, `nuls`, `exprimes`.

**Sept scrutins** (liste fermée `SCRUTINS`, à étendre à la main après chaque
tour) : municipales 2026 T1/T2, législatives 2024 T1/T2, européennes 2024,
présidentielle 2022 T1/T2.

**Périmètre communal** : `ref_villes` ∪ `collectivites_communes_top200` = **234
communes** au 20/08/2026. Le pipeline n'élargit jamais ce périmètre : une
commune n'apparaît en résultats électoraux que si une autre page du site la
connaît déjà. C'est ce qui borne la table ville à 1 524 lignes plutôt qu'aux
34 884 communes du parquet.

**Poids réellement ajouté à la base : 241 664 octets** (236 Kio), mesuré
`stat -c %s` avant/après sur une base fraîchement `VACUUM`-ée.

**Poids ajouté à la page** : les 2 264 lignes traversent la frontière
serveur → client en props compactes — `92 442 octets` bruts, `40 416` gzip
(mesuré le 20/08/2026). L'encodage nommé naïf en pesait `252 311` / `62 788` :
les libellés sont donc sortis une seule fois dans un dictionnaire `noms` et les
lignes réduites à des tuples `[code, inscrits, votants, blancs, nuls,
exprimés]`. Seules les 12 premières lignes de chaque tableau sont rendues dans
le HTML, le reste s'affiche d'un clic sans requête.

Mesure de bout en bout sur l'export statique, avec et sans le bloc :

| `app/out/collectivites/index.html` | brut | gzip |
|---|---:|---:|
| sans le bloc participation | 231 420 | 35 021 |
| avec le bloc participation | **350 171** | **79 243** |

Si ce surcoût devient gênant, le levier déjà employé ailleurs sur cette page
(`CarteDepartements`, `SeriesCollectivites`) est un **fragment statique**
`/data/elections.json` chargé au premier changement de scrutin : les props se
réduiraient alors au seul scrutin par défaut. Cela suppose une nouvelle route
`app/src/app/data/elections.json/route.ts`.

⚠ **Piège d'intégration** : `app/src/lib/queries/elections.ts` ouvre la base
via `@/lib/db` (better-sqlite3, `node:fs`). Le composant client n'en importe
que des **types** (`import type`, effacé à la compilation) ; les formules
d'affichage (taux, part des blancs et nuls, décodage des tuples) vivent dans le
composant, qui est pur. Une importation de valeur fait échouer le build sur
« Module not found: Can't resolve 'fs' ».

## 3. Ce qui est écarté, et pourquoi

### 3.1 Les nuances politiques — décision réversible

**Non publiées, ni en base ni à l'écran.** Quatre raisons cumulatives :

1. la nuance est une **qualification préfectorale**, pas une déclaration du
   candidat : elle dit ce que l'administration a rangé, pas ce que l'intéressé
   revendique ;
2. elle est **vide à 25,2 %** sur les municipales 2026 et **à 100 %** sur la
   présidentielle 2022 — publier une répartition sur trois quarts d'un scrutin
   et rien du tout sur l'autre n'informe pas, cela égare ;
3. sa **grille a changé entre 2020 et 2026** (6 codes disparus, 6 apparus,
   circulaire INTP2602966C de février 2026) : aucune série temporelle n'est
   possible sans recodage arbitraire ;
4. elle est **contestée devant le Conseil d'État**.

La publier exigerait tant de réserves qu'elle informerait moins qu'elle
n'induirait en erreur. L'option retenue est « pas affichée du tout ».
**Cette décision tient à ces quatre faits, pas à un principe** : elle vaut tant
qu'ils valent. Elle est liée au point 3.3 : la colonne `nuance` n'existe
que dans `candidats_results`, la ressource qui porte aussi les 646 104 noms de
candidats, et que le pipeline ne télécharge pas.

### 3.2 Le bureau de vote

Le grain natif (3,16 M de lignes, +88 Mo mesurés en base) n'est exposé nulle
part sur le site. Le pipeline lit ces lignes et n'en conserve **aucune** :
elles ne servent qu'à produire les sommes commune et département.

### 3.3 Les noms de candidats

La ressource `candidats_results.parquet` contient **646 104 noms de personnes
physiques**. Elle n'est **ni téléchargée, ni lue, ni référencée** par une URL
dans le code. Aucun nom de candidat n'existe à aucune étape du pipeline, de la
base ou de l'affichage. Un test (`test_aucune_nuance_aucun_candidat_dans_le_schema`)
verrouille l'absence de colonne `nuance`, `candidat`, `nom_`, `prenom`, `voix`
ou `sieges` dans le schéma.

### 3.4 Les Français établis hors de France (`ZZ`)

Le parquet range 210 à 213 « communes » consulaires sous
`code_departement = 'ZZ'`. **Ce n'est pas un département** : les inclure dans
une table départementale serait une erreur de catégorie. Ils sont donc exclus,
et la conséquence est **dite au lecteur** : la somme des départements n'est pas
le taux national. À la présidentielle 2022 T1, elle donne **74,86 %** là où le
ministère publie 73,69 % — l'écart, ce sont ces électeurs-là. L'agrégat
s'appelle « ensemble des départements et collectivités », jamais « France ».

## 4. Les trois pièges mesurés

### Piège 1 — le code département change de codification selon le scrutin

La Guadeloupe est `ZA` jusqu'en 2024 et `971` en 2026. Onze territoires sont
concernés, et `ZX` fusionne à lui seul **deux** collectivités :

| `code_departement` (≤ 2024) | dérivé de `code_commune` | Territoire |
|---|---|---|
| `ZA` `ZB` `ZC` `ZD` | 971 972 973 974 | Guadeloupe, Martinique, Guyane, La Réunion |
| `ZM` `ZS` | 976 975 | Mayotte, Saint-Pierre-et-Miquelon |
| `ZX` | **977 et 978** | Saint-Barthélemy **et** Saint-Martin |
| `ZW` `ZP` `ZN` | 986 987 988 | Wallis-et-Futuna, Polynésie, Nouvelle-Calédonie |

Une jointure sur `code_departement` casse **silencieusement** — sans erreur,
avec des lignes simplement absentes. Mesure du dégât évité, par scrutin :

| Scrutin | `ref_departements` appariés par jointure naïve | par dérivation |
|---|---|---|
| 2022_pres_t1 / t2 | 96/101 (manquent 971, 972, 973, 974, 976) | **101/101** |
| 2024_euro_t1 | 96/101 (idem) | **101/101** |
| 2024_legi_t1 / t2 | 96/101 (idem) | **101/101** |
| 2026_muni_t1 | 101/101 | **101/101** |
| 2026_muni_t2 | 100/101 (Mayenne : pas de second tour, absence réelle) | 100/101 |

**Règle appliquée** : le département est TOUJOURS dérivé des 2 ou 3 premiers
caractères de `code_commune`, jamais de `code_departement`. `code_commune` est
sur 5 caractères partout et sa codification ne varie pas (`97101` dans les deux
cas) ; les codes commençant par `97` ou `98` tiennent sur 3 caractères, les
autres sur 2 (`2A`/`2B` compris). C'est `_SQL_DEPARTEMENT` dans le pipeline.
Le contrôle `verifier()` **refuse l'ingestion** si un seul des 101 codes de
`ref_departements` n'a aucun résultat.

Les libellés viennent de `ref_departements` (101) complétés par
`LIBELLES_COLLECTIVITES` (6 collectivités hors référentiel) — indispensable
puisque la source nomme 977 **et** 978 « Saint-Martin/Saint-Barthélemy », ce
qui serait faux pour l'un des deux.

### Piège 2 — cohérence arithmétique

Sur les **428 586 lignes de bureau** retenues :

- `votants = blancs + nuls + exprimés` : **0 écart** ;
- `inscrits >= votants >= exprimés` : **2 lignes en violation**, toutes deux
  aux municipales 2026 T1 —
  - **41205 Saint-Cyr-du-Gault** : `votants = 0`, `blancs = 5`, **`nuls = -84`**
    (négatif), `exprimés = 79` ;
  - **60400 Le Mesnil-sur-Bulles** : **212 votants pour 209 inscrits**.

Ce sont des données réelles du ministère, pas un défaut d'ingestion. Elles ne
sont **ni corrigées, ni supprimées, ni arrondies, ni remplacées par zéro** :
elles sont comptées, journalisées en `WARNING` et consignées dans
`meta_sources.notes`. Aucune des deux communes n'appartient au périmètre du
site, et **0 agrégat départemental** est incohérent — les deux tables publiées
sont donc saines. Un garde-fou refuse l'ingestion si plus de 1 % des agrégats
violent l'encadrement (2 sur 240 000 = 0,0008 % : anomalie amont ; 5 % :
anomalie de pipeline, on n'écrase pas des tables saines avec ça).

### Piège 3 — communes connues du site absentes des résultats

Trois des 234 communes suivies manquent aux municipales 2026 T1. **Ni fusion,
ni arrondissement** : l'absence est structurelle.

- **97701 Saint-Barthélemy** et **97801 Saint-Martin** : collectivités
  d'outre-mer de l'**article 74 de la Constitution** depuis 2007. Elles
  n'élisent pas de conseil municipal mais un **conseil territorial**, lors d'un
  scrutin distinct qui ne figure pas dans ce jeu. Elles sont bien présentes aux
  présidentielle, législatives et européennes (5 267 et 12 659 inscrits en 2022).
- **98613 Uvea** : absente de **tous** les 56 scrutins du parquet.
  Wallis-et-Futuna n'a pas de communes — le territoire est découpé en trois
  circonscriptions coutumières (Uvea, Sigave, Alo) et le ministère publie ses
  résultats sous une entité unique, `98601 « Wallis-Et-Futuna »`.

L'absence se mesure sur le dernier **premier** tour ingéré, jamais sur un
second : à un second tour, 78 des 234 communes manquent normalement (conseil
élu dès le premier tour) et l'absence n'y prouverait rien.

À l'écran, une commune absente est **dite absente** avec sa raison ; aucune
ligne n'est fabriquée, aucun taux à zéro n'est affiché.

## 5. Garde-fous d'affichage

- Chaque bloc porte son `FreshnessBadge` : `meta_sources.date_donnees` =
  **date du dernier tour réellement ingéré** (2026-03-22), jamais la date de
  modification du dataset (07/07/2026). Les dates de convocation sont une table
  fermée, chacune fixée par décret (2022-107, 2024-217, 2024-527, 2025-848).
- **Les sept scrutins ne se comparent pas entre eux** : une participation
  municipale et une participation présidentielle ne mesurent ni le même corps
  électoral, ni le même enjeu, ni le même mode de scrutin. La mise en garde
  est écrite au-dessus des tableaux, pas reléguée en note.
- Aucun superlatif, aucune projection, aucune intention prêtée. Le mot
  « en direct » est banni : ces résultats sont définitifs et datés.
- Tout ratio absent s'affiche « — », jamais 0.
- **Libellés** : les noms de départements viennent de `ref_departements`
  (résolus par le pipeline), ceux des communes du référentiel du site
  (`ref_villes` ∪ `collectivites_communes_top200`, résolus par la requête), avec repli
  sur le libellé de la source. Le ministère change la casse d'un scrutin à
  l'autre (« Aix-En-Provence » aux municipales 2026 T1, « Aix-en-Provence » au
  T2) et la même commune est nommée ailleurs sur `/collectivites` depuis ce
  référentiel : deux orthographes du même nom sur une page se lisent comme deux
  communes.

> **Point de synchronisation.** `DATES_SCRUTINS` existe en deux exemplaires :
> `pipelines/ingest_elections.py` (pour `date_donnees`) et
> `app/src/lib/queries/elections.ts` (pour l'affichage). Le schéma des tables
> ne porte volontairement aucune colonne de date — la date est un référentiel
> éditorial, pas une donnée du parquet. Toute modification de l'une doit être
> reportée dans l'autre.

## 6. Exploitation

```bash
make ingest-elections          # ou make ingest (elections après collectivites)
```

Le pipeline est **idempotent** (delete + insert dans une transaction unique) et
rejouable : deux passages consécutifs laissent 740 + 1 524 lignes, 0 doublon et
un fichier de base d'octet identique. Le parquet est mis en cache 168 h dans
`data/raw/elections/`. Durée d'ingestion cache chaud : **0,6 s**.

Fraîcheur recommandée (à reporter dans `/etc/france-transparence/fraicheur.conf`
et `app/src/lib/queries/donnees.ts`) :

```
S26 |jc|1100|1300|5|Résultats électoraux agrégés (MI) : PAS de cadence périodique,
                    « par scrutin ». L'écart maximal observé entre deux scrutins
                    nationaux dans le jeu est de 3 ans (2004 → 2007), auquel
                    s'ajoute ~3,5 mois de latence de publication (municipales du
                    22/03/2026 publiées le 07/07/2026) : seuils ~36/43 mois.
                    Rupture resserrée à 5 % : la liste SCRUTINS est fermée, le
                    volume ne bouge QUE si on l'étend à la main. À SURVEILLER
                    MANUELLEMENT autour d'avril et juin 2027 (présidentielle et
                    législatives) — le seuil ne le détectera pas seul.
```

Ingestion recommandée : **mensuelle** (le contenu ne bouge qu'après un tour),
plus un passage manuel dans le mois qui suit chaque scrutin, en ajoutant
d'abord le nouvel identifiant à `SCRUTINS` et sa date à `DATES_SCRUTINS`
(pipeline **et** `elections.ts`).
