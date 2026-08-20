"""P14 — Participation électorale : résultats agrégés du ministère de l'Intérieur. [S26]

Source : jeu « Données des élections agrégées » (data.gouv.fr, dataset
`6481e741d4cf002ec0efec9d`), ressource Parquet « Résultats généraux »
(`general_results.parquet`, 70,9 Mo, 25 colonnes, 3 162 440 lignes, 56 scrutins
de 1999 à 2026, mise à jour du 07/07/2026). Licence **lov2** (Licence Ouverte
2.0), vérifiée par l'API data.gouv le 20/08/2026.

Ce que ce pipeline ingère — et RIEN d'autre : la PARTICIPATION.
inscrits, votants, blancs, nuls, exprimés, agrégés à la commune et au
département, sur 7 scrutins. Pas de nuance politique, pas de bureau de vote,
pas de nom de candidat. Le raisonnement complet est dans docs/ELECTIONS.md ;
en résumé :

- **Nuances politiques : écartées, ni en base ni à l'écran.** La nuance est
  une qualification attribuée par les préfectures, pas une déclaration du
  candidat. Elle est vide à 25,2 % sur les municipales 2026 et à 100 % sur la
  présidentielle 2022 ; sa grille a changé entre 2020 et 2026 (6 codes
  disparus, 6 apparus), ce qui interdit toute série ; elle est contestée
  devant le Conseil d'État. La publier exigerait tant de réserves qu'elle
  informerait moins qu'elle n'induirait en erreur. Décision RÉVERSIBLE :
  rouvrir docs/ELECTIONS.md § « Ce qui est écarté » avant d'y revenir.
- **Noms de candidats : jamais.** La ressource `candidats_results.parquet`
  contient 646 104 noms de personnes physiques ; elle n'est ni téléchargée,
  ni lue, ni référencée ailleurs que dans cette phrase.
- **Bureau de vote : écarté.** Le grain natif (3,16 M de lignes) pèse
  +88 Mo en base pour une granularité que le site n'expose nulle part.

Scrutins retenus (7, cf. SCRUTINS) : municipales 2026 T1/T2, législatives
2024 T1/T2, européennes 2024, présidentielle 2022 T1/T2.

Tables produites (SQLite, possédées par ce pipeline, delete+insert idempotent) :

- elections_participation_departement — 740 lignes (7 scrutins × 102 à 107
  départements et collectivités). Colonnes : id_election, code_departement,
  libelle_departement, inscrits, votants, blancs, nuls, exprimes.
- elections_participation_ville — 1 524 lignes, restreintes aux communes DÉJÀ
  connues du site (`ref_villes` ∪ `collectivites_communes`, 234 au 20/08/2026 ;
  231 figurent aux municipales 2026 T1). Colonnes : id_election, code_commune,
  libelle_commune, code_departement, inscrits, votants, blancs, nuls, exprimes.

Aucun taux n'est stocké : les ratios sont calculés à l'affichage à partir des
effectifs bruts, pour qu'une donnée absente reste absente (un taux stocké se
lirait comme un zéro).

────────────────────────────────────────────────────────────────────────────
LES TROIS PIÈGES MESURÉS (chacun a son garde-fou ci-dessous)
────────────────────────────────────────────────────────────────────────────

1. **`code_departement` change de codification selon le scrutin.** La
   Guadeloupe est `ZA` jusqu'en 2024 et `971` en 2026 ; idem pour 11
   territoires (`ZB`→972, `ZC`→973, `ZD`→974, `ZS`→975, `ZM`→976, `ZX`→977 ET
   978, `ZW`→986, `ZP`→987, `ZN`→988). Une jointure sur `code_departement`
   casse donc SILENCIEUSEMENT — sans erreur, avec des lignes manquantes — pour
   ces territoires, et `ZX` fusionne à lui seul Saint-Barthélemy et
   Saint-Martin. Le département est TOUJOURS dérivé des 2 ou 3 premiers
   caractères de `code_commune` (toujours 5 caractères, cohérent d'un scrutin
   à l'autre : `97101` dans les deux codifications), JAMAIS de
   `code_departement`. Voir `_SQL_DEPARTEMENT` et le contrôle
   « appariement ref_departements » de `verifier()`.

2. **Cohérence arithmétique.** Sur les 428 586 lignes de bureau retenues,
   `votants = blancs + nuls + exprimés` est vrai partout (0 écart), mais
   2 lignes violent `inscrits >= votants >= exprimés`, toutes deux aux
   municipales 2026 T1 : Saint-Cyr-du-Gault (41205) publie `nuls = -84`
   (négatif) et `votants = 0` ; Le Mesnil-sur-Bulles (60400) publie 212
   votants pour 209 inscrits. Ce sont des données réelles du ministère, pas
   un défaut d'ingestion : elles ne sont NI corrigées, NI supprimées, NI
   arrondies. Elles sont comptées, journalisées et consignées dans
   `meta_sources.notes`. Aucune n'appartient au périmètre communal du site,
   et aucune n'entame la cohérence des agrégats départementaux (0 violation).

3. **Communes connues du site absentes du parquet.** Trois des 234 manquent
   aux municipales 2026 T1, et l'absence est structurelle, pas un trou de
   données : Saint-Barthélemy (97701) et Saint-Martin (97801) sont des
   collectivités d'outre-mer de l'article 74 depuis 2007 — elles n'élisent pas
   de conseil municipal mais un conseil territorial, lors d'un scrutin
   distinct ; elles figurent bien aux présidentielle, législatives et
   européennes. Uvea (98613) est absente de TOUS les scrutins : Wallis-et-
   Futuna n'a pas de communes, le territoire est découpé en trois
   circonscriptions coutumières et le ministère publie ses résultats sous une
   entité unique (`98601`). Ni fusion de communes, ni arrondissement.

Autre exclusion assumée : `ZZ` — « Français établis hors de France », 210 à
213 « communes » consulaires. Ce n'est pas un département : l'inclure dans une
table départementale serait une erreur de catégorie. Conséquence à dire au
lecteur (elle l'est, dans le composant) : la somme des départements EXCLUT ces
électeurs, et diffère donc du taux national du ministère (74,86 % contre
73,69 % à la présidentielle 2022 T1).

Exécution : `python -m pipelines.ingest_elections` (FT_DB_PATH pour une base
jetable). Idempotent ; échec → exit 1, transaction annulée, base intacte.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import duckdb
import requests

from pipelines import db
from pipelines.common import obtenir_logger, session_http, telecharger

log = obtenir_logger("ingest_elections")

SOURCE_ID = "S26"
NOM_SOURCE = "Résultats électoraux agrégés (ministère de l'Intérieur, data.gouv.fr)"
URL_PAGE = "https://www.data.gouv.fr/datasets/donnees-des-elections-agregees"
URL_API_DATASET = "https://www.data.gouv.fr/api/1/datasets/6481e741d4cf002ec0efec9d/"
URL_PARQUET = (
    "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/elections/general_results.parquet"
)
LICENCE = "Licence Ouverte 2.0 (lov2)"
# `frequency` du dataset = "punctual". Convention meta_sources déjà employée
# par S29 (comptes de campagne) pour une source sans période : « par scrutin ».
FREQUENCE = "par scrutin"

FICHIER_RAW = "elections/general_results.parquet"
# Le jeu ne bouge qu'après un tour de scrutin : 7 jours de cache suffisent et
# évitent de re-télécharger 70,9 Mo à chaque rejeu du pipeline.
CACHE_HEURES = 168.0

# Scrutins ingérés — LISTE FERMÉE, à étendre À LA MAIN après chaque nouveau
# tour (prochaines échéances : présidentielle et législatives 2027). Le choix
# est éditorial : les 7 derniers tours nationaux ou communaux, ceux dont la
# participation éclaire encore le paysage local. Ajouter un scrutin ici suffit
# (le pipeline est rejouable) ; ne rien y ajouter ne casse rien, mais la
# fraîcheur S26 cessera d'avancer — c'est le point de vigilance manuel signalé
# dans /etc/france-transparence/fraicheur.conf.
SCRUTINS: tuple[str, ...] = (
    "2022_pres_t1",
    "2022_pres_t2",
    "2024_euro_t1",
    "2024_legi_t1",
    "2024_legi_t2",
    "2026_muni_t1",
    "2026_muni_t2",
)

# Date du dernier tour ingéré = `date_donnees` de meta_sources (convention
# SOURCES.md §0.2 : la date de la DONNÉE, jamais celle de modification du
# dataset amont, ici le 07/07/2026). Table fermée, chaque date étant fixée par
# un décret de convocation des électeurs :
#   - présidentielle 2022 : décret n° 2022-107 du 02/02/2022 ;
#   - européennes 2024 : décret n° 2024-217 du 12/03/2024 ;
#   - législatives 2024 (dissolution) : décret n° 2024-527 du 09/06/2024 ;
#   - municipales 2026 : décret n° 2025-848 du 27/08/2025.
# Un scrutin ajouté à SCRUTINS sans date ici ne bloque pas l'ingestion : la
# date de données retombe sur le dernier tour daté connu (dégradation propre).
DATES_SCRUTINS: dict[str, str] = {
    "2022_pres_t1": "2022-04-10",
    "2022_pres_t2": "2022-04-24",
    "2024_euro_t1": "2024-06-09",
    "2024_legi_t1": "2024-06-30",
    "2024_legi_t2": "2024-07-07",
    "2026_muni_t1": "2026-03-15",
    "2026_muni_t2": "2026-03-22",
}

# Collectivités présentes dans les résultats mais absentes de `ref_departements`
# (qui ne liste que les 101 départements). Libellés INSEE : la source les
# fusionne sous « Saint-Martin/Saint-Barthélemy » pour DEUX codes distincts
# (977 et 978), un libellé unique y serait donc faux pour l'un des deux.
LIBELLES_COLLECTIVITES: dict[str, str] = {
    "975": "Saint-Pierre-et-Miquelon",
    "977": "Saint-Barthélemy",
    "978": "Saint-Martin",
    "986": "Wallis-et-Futuna",
    "987": "Polynésie française",
    "988": "Nouvelle-Calédonie",
}

# Code « département » des Français établis hors de France : exclu de la table
# départementale (cf. docstring). Ce n'est pas un département.
CODE_HORS_DE_FRANCE = "ZZ"

# Garde-fous « build cassé » : en deçà, on refuse d'écraser des tables saines.
MIN_LIGNES_PARQUET = 3_000_000
MIN_DEPARTEMENTS = 100          # 96 métropole + DROM, par scrutin
MIN_LIGNES_DEPARTEMENT = 700
MIN_LIGNES_VILLE = 1_400
# Part maximale de lignes incohérentes tolérée avant de refuser l'ingestion.
# Mesuré le 20/08/2026 : 2 communes sur 240 000 agrégats, soit 0,0008 %.
MAX_PART_INCOHERENTES = 0.01

# ---------------------------------------------------------------------------
# PIÈGE 1 — le département se dérive de code_commune, jamais de code_departement
#
# code_commune est TOUJOURS sur 5 caractères et sa codification ne varie pas
# d'un scrutin à l'autre : 97101 (Les Abymes) sous `ZA` en 2022 comme sous
# `971` en 2026. Les 2 premiers caractères donnent le département de métropole
# (« 2A »/« 2B » compris, qui sont bien la codification INSEE de la Corse) ;
# les codes commençant par 97 ou 98 sont d'outre-mer et tiennent sur 3.
# ---------------------------------------------------------------------------
_SQL_DEPARTEMENT = (
    "CASE WHEN substr(code_commune, 1, 2) IN ('97', '98') "
    "THEN substr(code_commune, 1, 3) ELSE substr(code_commune, 1, 2) END"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS elections_participation_departement (
    id_election         TEXT NOT NULL,     -- ex. '2026_muni_t1' (identifiant natif MI)
    code_departement    TEXT NOT NULL,     -- DÉRIVÉ de code_commune (cf. piège 1)
    libelle_departement TEXT NOT NULL,
    inscrits            INTEGER NOT NULL,
    votants             INTEGER NOT NULL,
    blancs              INTEGER NOT NULL,
    nuls                INTEGER NOT NULL,
    exprimes            INTEGER NOT NULL,
    PRIMARY KEY (id_election, code_departement)
);

CREATE TABLE IF NOT EXISTS elections_participation_ville (
    id_election      TEXT NOT NULL,
    code_commune     TEXT NOT NULL,        -- code INSEE 5 caractères
    libelle_commune  TEXT NOT NULL,
    code_departement TEXT NOT NULL,        -- DÉRIVÉ de code_commune (cf. piège 1)
    inscrits         INTEGER NOT NULL,
    votants          INTEGER NOT NULL,
    blancs           INTEGER NOT NULL,
    nuls             INTEGER NOT NULL,
    exprimes         INTEGER NOT NULL,
    PRIMARY KEY (id_election, code_commune)
);
CREATE INDEX IF NOT EXISTS idx_elections_ville_commune
    ON elections_participation_ville(code_commune);
"""


# ---------------------------------------------------------------------------
# Périmètre lu en base (aucune liste en dur : le site décide de son périmètre)
# ---------------------------------------------------------------------------


def perimetre_communes(conn: sqlite3.Connection) -> list[str]:
    """Communes DÉJÀ connues du site : `ref_villes` ∪ `collectivites_communes`.

    234 codes INSEE au 20/08/2026 (184 villes de référence, 200 grandes
    communes OFGL, 150 en commun). Le pipeline n'élargit jamais ce périmètre :
    une commune n'apparaît dans les résultats électoraux que si une autre page
    du site la connaît déjà.
    """
    lignes = conn.execute(
        """
        SELECT code_insee FROM ref_villes
        UNION
        SELECT code_insee FROM collectivites_communes
        """
    ).fetchall()
    return sorted(l[0] for l in lignes)


def libelles_departements(conn: sqlite3.Connection) -> dict[str, str]:
    """Libellés faisant autorité : `ref_departements` (101) + collectivités
    d'outre-mer hors référentiel (6, cf. LIBELLES_COLLECTIVITES)."""
    libelles = dict(LIBELLES_COLLECTIVITES)
    for code, nom in conn.execute("SELECT code, nom FROM ref_departements"):
        libelles[code] = nom
    return libelles


# ---------------------------------------------------------------------------
# Fraîcheur amont (convention SOURCES.md §0.2 : re-vérifier en ligne)
# ---------------------------------------------------------------------------


def verifier_fraicheur(session: requests.Session) -> dict[str, str]:
    """Relit licence et date de modification du jeu sur l'API data.gouv.

    Retourne {'licence', 'modifie', 'octets'} — informatif : ces valeurs
    partent dans `meta_sources.notes`, elles ne servent JAMAIS de
    `date_donnees` (ce serait la date du dataset, pas celle de la donnée).
    """
    r = session.get(URL_API_DATASET, timeout=60)
    r.raise_for_status()
    jeu = r.json()
    parquet = next(
        (
            res
            for res in jeu.get("resources", [])
            if res.get("format") == "parquet" and "general_results" in (res.get("url") or "")
        ),
        {},
    )
    infos = {
        "licence": jeu.get("license") or "?",
        "modifie": (parquet.get("last_modified") or jeu.get("last_update") or "?")[:10],
        "octets": str(parquet.get("filesize") or "?"),
    }
    log.info("fraîcheur S26 constatée : %s", infos)
    if infos["licence"] not in ("lov2", "?"):
        raise RuntimeError(
            f"licence amont inattendue : {infos['licence']!r} (lov2 attendue) — "
            "vérifier docs/ELECTIONS.md avant de republier"
        )
    return infos


# ---------------------------------------------------------------------------
# Transformation (pure : parquet + périmètre → listes de tuples)
# ---------------------------------------------------------------------------


def transformer(
    chemin_parquet: str | Path,
    communes_connues: list[str],
    libelles_dep: dict[str, str],
    scrutins: tuple[str, ...] = SCRUTINS,
) -> tuple[list[tuple], list[tuple], dict]:
    """Agrège le parquet en (lignes département, lignes ville, stats).

    Pure et rejouable : ni réseau ni SQLite, testable sur une fixture parquet.
    L'agrégation part du grain natif (bureau de vote) et n'en garde AUCUNE
    ligne : seules les sommes commune et département sont retournées.

    `stats` contient lignes_parquet, lignes_retenues, scrutins_trouves,
    scrutins_manquants, departements, communes_absentes, incoherentes_dep,
    incoherentes_ville, ecarts_votants, dernier_scrutin.
    """
    chemin = Path(chemin_parquet).as_posix()
    duck = duckdb.connect()
    duck.execute("SET threads TO 4")

    lignes_parquet = duck.execute(
        "SELECT count(*) FROM read_parquet(?)", [chemin]
    ).fetchone()[0]

    duck.execute("CREATE TEMP TABLE t_scrutins (id_election VARCHAR)")
    duck.executemany("INSERT INTO t_scrutins VALUES (?)", [(s,) for s in scrutins])
    duck.execute("CREATE TEMP TABLE t_perimetre (code_commune VARCHAR)")
    duck.executemany("INSERT INTO t_perimetre VALUES (?)", [(c,) for c in communes_connues])

    # Grain natif filtré sur les scrutins retenus, département DÉRIVÉ (piège 1).
    duck.execute(
        f"""
        CREATE TEMP VIEW bureaux AS
        SELECT id_election,
               {_SQL_DEPARTEMENT} AS code_departement,
               code_commune, libelle_commune,
               inscrits, votants, blancs, nuls, exprimes
        FROM read_parquet('{chemin}')
        WHERE id_election IN (SELECT id_election FROM t_scrutins)
        """
    )
    lignes_retenues = duck.execute("SELECT count(*) FROM bureaux").fetchone()[0]
    scrutins_trouves = [
        r[0] for r in duck.execute("SELECT DISTINCT id_election FROM bureaux ORDER BY 1").fetchall()
    ]

    # PIÈGE 2 (a) — identité arithmétique votants = blancs + nuls + exprimés,
    # au grain natif. Mesurée exacte partout le 20/08/2026 ; comptée quand même,
    # parce qu'un jour elle ne le sera plus.
    ecarts_votants = duck.execute(
        "SELECT count(*) FROM bureaux WHERE votants <> blancs + nuls + exprimes"
    ).fetchone()[0]
    # …et l'encadrement inscrits >= votants >= exprimés, AU GRAIN NATIF. Les
    # deux lignes fautives des municipales 2026 sont à ce niveau : elles ne
    # remontent dans aucune des deux tables produites (leurs communes sont hors
    # périmètre du site et leurs départements restent cohérents), mais les
    # ignorer serait taire un défaut réel de la source.
    incoherentes_bureau = duck.execute(
        "SELECT count(*) FROM bureaux"
        " WHERE NOT (inscrits >= votants AND votants >= exprimes)"
    ).fetchone()[0]
    if incoherentes_bureau:
        for ligne in duck.execute(
            "SELECT id_election, code_commune, libelle_commune, inscrits, votants,"
            " blancs, nuls, exprimes FROM bureaux"
            " WHERE NOT (inscrits >= votants AND votants >= exprimes)"
            " ORDER BY 1, 2 LIMIT 20"
        ).fetchall():
            log.warning("bureau incohérent à la source (conservé tel quel) : %s", ligne)

    # Agrégat DÉPARTEMENT — 'ZZ' (Français établis hors de France) exclu :
    # ce n'est pas un département (cf. docstring).
    lignes_dep = duck.execute(
        f"""
        SELECT id_election, code_departement,
               CAST(sum(inscrits) AS BIGINT), CAST(sum(votants) AS BIGINT),
               CAST(sum(blancs)   AS BIGINT), CAST(sum(nuls)    AS BIGINT),
               CAST(sum(exprimes) AS BIGINT)
        FROM bureaux
        WHERE code_departement <> '{CODE_HORS_DE_FRANCE}'
        GROUP BY id_election, code_departement
        ORDER BY id_election, code_departement
        """
    ).fetchall()

    # Le libellé départemental vient du référentiel du site, pas de la source :
    # celle-ci fusionne 977 et 978 sous « Saint-Martin/Saint-Barthélemy ».
    # Un code hors référentiel garde son code pour libellé (dégradation propre,
    # jamais un nom inventé) et le contrôle `verifier()` le fera remonter.
    dep_final = [
        (idel, code, libelles_dep.get(code, code), i, v, b, n, e)
        for idel, code, i, v, b, n, e in lignes_dep
    ]

    # Agrégat VILLE — restreint au périmètre connu du site.
    ville_final = duck.execute(
        """
        SELECT id_election, code_commune,
               any_value(libelle_commune), any_value(code_departement),
               CAST(sum(inscrits) AS BIGINT), CAST(sum(votants) AS BIGINT),
               CAST(sum(blancs)   AS BIGINT), CAST(sum(nuls)    AS BIGINT),
               CAST(sum(exprimes) AS BIGINT)
        FROM bureaux
        WHERE code_commune IN (SELECT code_commune FROM t_perimetre)
        GROUP BY id_election, code_commune
        ORDER BY id_election, code_commune
        """
    ).fetchall()

    # PIÈGE 2 (b) — inscrits >= votants >= exprimés, sur les AGRÉGATS produits.
    # Les lignes fautives sont conservées telles quelles (donnée réelle du
    # ministère) mais comptées, journalisées et consignées dans les notes.
    incoherentes_dep = [l for l in dep_final if not (l[3] >= l[4] >= l[7])]
    incoherentes_ville = [l for l in ville_final if not (l[4] >= l[5] >= l[8])]
    for ligne in incoherentes_dep:
        log.warning("département incohérent (donnée source conservée) : %s", ligne)
    for ligne in incoherentes_ville:
        log.warning("commune incohérente (donnée source conservée) : %s", ligne)

    # PIÈGE 3 — communes connues du site absentes des résultats.
    #
    # Deux mesures, parce qu'une absence n'a pas le même sens selon le tour :
    # au SECOND tour, des dizaines de communes manquent normalement (conseil
    # élu dès le premier tour) — l'absence n'y prouve rien. C'est le dernier
    # PREMIER tour communal qui fait foi : chaque commune y vote.
    dernier = scrutins_trouves[-1] if scrutins_trouves else None
    premiers_tours = [s for s in scrutins_trouves if s.endswith("_t1")]
    dernier_t1 = premiers_tours[-1] if premiers_tours else dernier
    connues = set(communes_connues)
    presentes_t1 = {l[1] for l in ville_final if l[0] == dernier_t1}
    communes_absentes = sorted(connues - presentes_t1)
    # Absence de TOUS les scrutins ingérés : il n'existe alors aucun niveau
    # communal pour ce code (Wallis-et-Futuna), ce n'est pas un trou de donnée.
    communes_jamais_vues = sorted(connues - {l[1] for l in ville_final})
    if communes_absentes:
        log.info(
            "communes connues absentes de %s : %s — dont %s absente(s) de tous "
            "les scrutins ingérés (absences structurelles documentées : "
            "docs/ELECTIONS.md § piège 3)",
            dernier_t1, ", ".join(communes_absentes),
            ", ".join(communes_jamais_vues) or "aucune",
        )

    stats = {
        "lignes_parquet": lignes_parquet,
        "lignes_retenues": lignes_retenues,
        "scrutins_trouves": scrutins_trouves,
        "scrutins_manquants": [s for s in scrutins if s not in scrutins_trouves],
        "departements": sorted({l[1] for l in dep_final}),
        "communes_connues": len(communes_connues),
        "communes_absentes": communes_absentes,
        "communes_jamais_vues": communes_jamais_vues,
        "dernier_premier_tour": dernier_t1,
        "incoherentes_dep": len(incoherentes_dep),
        "incoherentes_ville": len(incoherentes_ville),
        "ecarts_votants": ecarts_votants,
        "incoherentes_bureau": incoherentes_bureau,
        "dernier_scrutin": dernier,
    }
    duck.close()
    return dep_final, ville_final, stats


# ---------------------------------------------------------------------------
# Chargement SQLite (transaction unique : DELETE + INSERT, rollback si échec)
# ---------------------------------------------------------------------------


def charger(
    conn: sqlite3.Connection, lignes_dep: list[tuple], lignes_ville: list[tuple]
) -> dict[str, int]:
    """Réécrit les 2 tables elections_* (delete+insert, idempotent).

    Ne commite pas : l'appelant commet après `verifier()`, ou annule.
    """
    conn.executescript(_SCHEMA)
    conn.execute("DELETE FROM elections_participation_departement")
    conn.executemany(
        "INSERT INTO elections_participation_departement VALUES (?,?,?,?,?,?,?,?)",
        lignes_dep,
    )
    conn.execute("DELETE FROM elections_participation_ville")
    conn.executemany(
        "INSERT INTO elections_participation_ville VALUES (?,?,?,?,?,?,?,?,?)",
        lignes_ville,
    )
    return {
        "elections_participation_departement": len(lignes_dep),
        "elections_participation_ville": len(lignes_ville),
    }


def verifier(
    conn: sqlite3.Connection,
    stats: dict,
    min_lignes_dep: int = MIN_LIGNES_DEPARTEMENT,
    min_lignes_ville: int = MIN_LIGNES_VILLE,
    min_departements: int = MIN_DEPARTEMENTS,
) -> None:
    """Contrôles de vraisemblance sur la base chargée, AVANT commit.

    Lève RuntimeError si KO — la transaction est alors annulée par l'appelant
    et la base reste dans son état précédent.

    Les trois minimums de volume sont paramétrables pour que les épreuves
    puissent jouer les MÊMES contrôles sur une fixture de 181 lignes ; en
    production, ce sont les constantes du module qui s'appliquent.
    """
    def un(sql: str):
        return conn.execute(sql).fetchone()[0]

    problemes: list[str] = []

    if stats["scrutins_manquants"]:
        problemes.append(f"scrutins absents du parquet : {stats['scrutins_manquants']}")

    n = un("SELECT count(*) FROM elections_participation_departement")
    if n < min_lignes_dep:
        problemes.append(f"table département : {n} lignes (< {min_lignes_dep})")
    n = un("SELECT count(*) FROM elections_participation_ville")
    if n < min_lignes_ville:
        problemes.append(f"table ville : {n} lignes (< {min_lignes_ville})")

    # PIÈGE 1, la preuve : les 101 codes de `ref_departements` doivent TOUS
    # s'apparier à la table départementale. C'est exactement ce qu'une jointure
    # sur `code_departement` casserait pour la Guadeloupe, la Martinique, la
    # Guyane, La Réunion et Mayotte (codées ZA/ZB/ZC/ZD/ZM jusqu'en 2024).
    orphelins = conn.execute(
        """
        SELECT r.code FROM ref_departements r
        WHERE NOT EXISTS (
            SELECT 1 FROM elections_participation_departement e
            WHERE e.code_departement = r.code
        )
        ORDER BY r.code
        """
    ).fetchall()
    if orphelins:
        problemes.append(
            "départements de ref_departements sans résultat : "
            + ", ".join(o[0] for o in orphelins)
        )

    # Aucun libellé ne doit être retombé sur son code (référentiel incomplet).
    sans_libelle = conn.execute(
        "SELECT DISTINCT code_departement FROM elections_participation_departement"
        " WHERE libelle_departement = code_departement ORDER BY 1"
    ).fetchall()
    if sans_libelle:
        problemes.append(
            "libellé départemental manquant (code affiché tel quel) pour "
            + ", ".join(s[0] for s in sans_libelle)
        )

    n = un(
        "SELECT count(*) FROM ("
        " SELECT id_election FROM elections_participation_departement"
        f" GROUP BY id_election HAVING count(*) < {min_departements})"
    )
    if n:
        problemes.append(f"{n} scrutin(s) avec moins de {min_departements} départements")

    # PIÈGE 2 : garde-fou de volume. Deux communes fautives sur 240 000
    # agrégats sont une anomalie de saisie amont ; 5 % en seraient une de
    # pipeline, et il ne faut pas écraser des tables saines avec ça.
    total = max(
        stats.get("incoherentes_dep", 0) + stats.get("incoherentes_ville", 0), 0
    )
    lignes = un("SELECT count(*) FROM elections_participation_departement") + un(
        "SELECT count(*) FROM elections_participation_ville"
    )
    if lignes and total / lignes > MAX_PART_INCOHERENTES:
        problemes.append(
            f"{total} agrégats incohérents sur {lignes} "
            f"(> {MAX_PART_INCOHERENTES:.0%}) — ingestion refusée"
        )

    # Effectifs manifestement impossibles (une valeur négative n'est pas une
    # absence : elle est signalée, pas remplacée par zéro).
    n = un(
        "SELECT count(*) FROM elections_participation_departement"
        " WHERE inscrits <= 0 OR votants < 0 OR exprimes < 0"
    )
    if n:
        problemes.append(f"table département : {n} effectifs impossibles")

    if problemes:
        raise RuntimeError("contrôles de vraisemblance KO : " + " ; ".join(problemes))


def date_donnees(stats: dict) -> str:
    """Date du dernier tour RÉELLEMENT ingéré (jamais la date du dataset).

    Dégradation propre : si le dernier scrutin trouvé n'a pas de date déclarée
    dans DATES_SCRUTINS, on retient la plus récente des dates connues parmi
    les scrutins effectivement ingérés.
    """
    connues = sorted(
        DATES_SCRUTINS[s] for s in stats["scrutins_trouves"] if s in DATES_SCRUTINS
    )
    if not connues:
        raise RuntimeError(
            "aucun scrutin ingéré n'a de date déclarée (DATES_SCRUTINS) — "
            "meta_sources.date_donnees ne peut pas être renseignée honnêtement"
        )
    return connues[-1]


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def executer() -> dict:
    session = session_http()
    fraicheur = verifier_fraicheur(session)
    parquet = telecharger(
        URL_PARQUET, FICHIER_RAW, max_age_heures=CACHE_HEURES, session=session
    )

    conn = db.init_db()
    try:
        communes = perimetre_communes(conn)
        libelles = libelles_departements(conn)
        log.info(
            "périmètre : %d communes connues, %d libellés départementaux",
            len(communes), len(libelles),
        )

        lignes_dep, lignes_ville, stats = transformer(parquet, communes, libelles)
        date_ref = date_donnees(stats)
        if stats["lignes_parquet"] < MIN_LIGNES_PARQUET:
            raise RuntimeError(
                f"parquet suspect : {stats['lignes_parquet']} lignes "
                f"(< {MIN_LIGNES_PARQUET}) — base non modifiée"
            )

        comptes = charger(conn, lignes_dep, lignes_ville)
        verifier(conn, stats)

        db.upsert_meta(  # commet la transaction (DELETE/INSERT compris)
            conn,
            source_id=SOURCE_ID,
            nom=NOM_SOURCE,
            url=URL_PAGE,
            licence=LICENCE,
            frequence=FREQUENCE,
            date_donnees=date_ref,
            lignes=sum(comptes.values()),
            notes=(
                f"Participation seulement : inscrits, votants, blancs, nuls, exprimés, "
                f"agrégés commune et département sur {len(stats['scrutins_trouves'])} scrutins "
                f"({', '.join(stats['scrutins_trouves'])}). "
                f"AUCUNE nuance politique et AUCUN nom de candidat ingérés "
                f"(justification : docs/ELECTIONS.md). "
                f"Département dérivé de code_commune, jamais de code_departement "
                f"(codification outre-mer variable : ZA en 2024, 971 en 2026). "
                f"Français établis hors de France (ZZ) exclus : ne relèvent d'aucun "
                f"département — la somme des départements diffère donc du taux national. "
                f"Cohérence : {stats['incoherentes_bureau']} ligne(s) de bureau sur "
                f"{stats['lignes_retenues']} violent inscrits >= votants >= exprimés "
                f"(données réelles du ministère, conservées telles quelles, jamais "
                f"corrigées), dont {stats['incoherentes_dep']} agrégat(s) "
                f"départemental(aux) et {stats['incoherentes_ville']} agrégat(s) "
                f"communal(aux) publiés ici ; {stats['ecarts_votants']} écart(s) sur "
                f"votants = blancs + nuls + exprimés. "
                f"{len(stats['communes_absentes'])} commune(s) connue(s) du site absente(s) "
                f"de {stats['dernier_premier_tour']} "
                f"({', '.join(stats['communes_absentes']) or 'aucune'}) : "
                f"Saint-Barthélemy et Saint-Martin élisent un conseil territorial "
                f"(collectivités de l'article 74), pas un conseil municipal ; "
                f"Uvea (absente de tous les scrutins) relève de Wallis-et-Futuna, "
                f"territoire sans communes. "
                f"Jeu amont : licence {fraicheur['licence']}, modifié le "
                f"{fraicheur['modifie']}, {fraicheur['octets']} octets."
            ),
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    for table, n in comptes.items():
        log.info("table %s : %d lignes", table, n)
    log.info(
        "P14 participation électorale : OK — %d départements, %d communes connues, "
        "date_donnees=%s",
        len(stats["departements"]), stats["communes_connues"], date_ref,
    )
    return stats


def main() -> int:
    try:
        executer()
    except Exception:
        log.exception("échec du pipeline participation électorale — base intacte")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
