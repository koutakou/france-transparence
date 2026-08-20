"""P11 — Finances locales : OFGL (data.ofgl.fr), comptes des collectivités et DGF. [S16]

Source pivot : Observatoire des Finances et de la Gestion publique Locales,
API Opendatasoft Explore v2.1, sans clé, Licence Ouverte 2.0 (SOURCES.md S16,
docs/recherche/06-finances-locales.md). Stratégie imposée par la volumétrie
(22 M lignes communes, 27 M lignes dotations) : JAMAIS d'aspiration des bases
complètes — exports CSV filtrés (`/exports/csv` streame avec where+select,
~9 Mo max ici) + agrégats serveur `group_by` (le `/records` est plafonné à
offset+limit ≤ 10 000). Pièges appliqués : `exer`/`exercice` sont des dates →
`year(exer)=2025` ; toujours `type_de_budget="Budget principal"` ; dotations
en format long `variable`/`valeur` → variables retenues « Montant Dotation
DGF » et « Population INSEE » (la « Population DGF », majorée, sert au calcul
de répartition de l'État, pas aux €/habitant citoyens).

Tables produites (SQLite, possédées par ce pipeline, delete+insert idempotent) :

- collectivites_departements — carte de France, communes agrégées par
  département, exercice 2025, budgets principaux :
  code_dep, nom, dep_fonctionnement (€), dep_investissement (€),
  euros_par_hab (= (fonctionnement + investissement) / population),
  population (somme ptot des communes), nb_communes, exercice.
- collectivites_regions — les conseils régionaux/CTU eux-mêmes (17 en 2025,
  dont CTU Corse/Martinique/Guyane, est_ctu=1), série 2018-2025, un
  enregistrement par grande catégorie (agrégat OFGL) :
  code_region, nom, siren, est_ctu, exercice, agregat, montant,
  euros_par_hab, population.
- collectivites_conseils_departementaux — idem pour les conseils
  départementaux et assimilés (97 en 2025 : « 67A » = Collectivité européenne
  d'Alsace, « 691 » = Métropole de Lyon, « 75 » = Ville de Paris ; Corse,
  Martinique, Guyane sont devenues des CTU → base régions) :
  code_dep, nom, siren, exercice, agregat, montant, euros_par_hab, population.
- collectivites_communes_top200 — top 200 communes par population (et RIEN
  d'autre : le nom porte le périmètre, la France compte ~34 900 communes),
  exercice 2025 : code_insee, nom, dep_code, dep_nom, siren, population,
  dep_fonctionnement, fonct_euros_par_hab, dep_investissement,
  inv_euros_par_hab, exercice.
- collectivites_communes_series — les MÊMES 200 communes, série 2018-2025
  en format long aligné sur les régions/départements, 2 agrégats
  (fonctionnement, investissement), budgets principaux seuls. Exports CSV
  filtrés par lots de codes INSEE (jamais le jeu entier) :
  code_insee, nom, siren, tranche_population (strate OFGL '0'..'10',
  population 2025), epci_nom, exercice, agregat, montant, euros_par_hab,
  population.
- collectivites_communes_strates — médianes d'€/habitant par strate
  démographique (tranche_population) × exercice × agrégat, calculées PAR LE
  SERVEUR OFGL (group_by + median() sur les ~34 900 budgets principaux,
  ~176 lignes rapatriées) : la seule comparaison honnête pour une commune
  est la médiane de sa strate, jamais un classement toutes tailles
  confondues : tranche_population, exercice, agregat,
  mediane_euros_par_hab, nb_communes.
- dotations_dgf — DGF des communes (dotations-communes OFGL, 2018-2026) :
  niveau ('national' | 'departement' | 'commune'), code ('FR', code dép. ou
  code INSEE), nom, exercice, dgf_montant (€), population (Population INSEE),
  dgf_par_hab, rang ('top'/'flop' pour les 20 extrêmes en DGF/hab, NULL
  sinon ; la DGF à 0 € existe — Paris est écrêtée), nb_communes (niveaux
  national et département). Niveau national = somme des communes par exercice
  2018→2026 ; niveau département = exercice 2026, codes Corse normalisés
  20A/20B → 2A/2B pour joindre la carte, inclut des COM (975, 986, 987, 988) ;
  niveau commune = les ~480 communes ≥ 20 000 hab., exercice 2026.
- entites (socle, type='collectivite') — régions, départements/assimilés,
  top 200 communes, avec SIREN OFGL ; id = COLL-REG-xx / COLL-DEP-xx /
  COLL-COM-xxxxx.

Module UI : « Finances locales » (carte départementale, fiches région/
département avec séries par grande catégorie, grandes communes avec séries
2018-2025 comparées à la médiane de leur strate, dotations DGF) + carte de
l'Accueil. Fraîcheur affichable : « Comptes 2025 provisoires
(chargés juillet 2026 ; ~97 communes manquantes jusqu'en décembre 2026) » ·
« Dotations de l'État : exercice 2026 ».

Exécution : `python -m pipelines.ingest_collectivites` (FT_DB_PATH pour une
base jetable). Idempotent ; échec → exit 1 sans données partielles commitées.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlencode

import duckdb
import requests

from pipelines import db
from pipelines.common import obtenir_logger, session_http, telecharger

log = obtenir_logger("ingest_collectivites")

API = "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets"

# Millésimes cibles (comptes N chargés par l'OFGL en juillet N+1 ;
# dotations réparties en début d'exercice → 2026 déjà disponible).
EXERCICE_COMPTES = 2025
SERIE_DEBUT = 2018
DGF_ANNEES = list(range(2018, 2027))  # 2018 → 2026 inclus
ANNEE_DGF_DETAIL = 2026

TOP_COMMUNES = 200
SEUIL_POP_TOP_FLOP = 20_000  # top/flop DGF/hab restreints aux communes ≥ 20 000 hab.
NB_TOP_FLOP = 20

AGREGAT_FONCT = "Dépenses de fonctionnement"
AGREGAT_INVEST = "Dépenses d'investissement"

# Séries communales : les 2 agrégats restitués sur /collectivites (le front
# les compare à la médiane de strate, en €/hab — pas d'autre agrégat tant
# qu'aucun module ne le restitue).
AGREGATS_COMMUNES = [AGREGAT_FONCT, AGREGAT_INVEST]
# Taille des lots de codes INSEE par export filtré (doctrine « jamais
# d'aspiration des bases complètes » : la clause `com_code in (...)` reste
# courte et l'URL loin des limites usuelles).
TAILLE_LOT_COMMUNES = 50

# Grandes catégories ingérées pour les régions et départements (agrégats
# OFGL, listés par group_by=agregat le 19/08/2026 — présents dans les deux
# bases ; « Epargne brute » peut être légitimement négative).
AGREGATS_SERIES = [
    "Dépenses de fonctionnement",
    "Dépenses d'investissement",
    "Dépenses d'équipement",
    "Dépenses d'intervention",
    "Frais de personnel",
    "Achats et charges externes",
    "Charges financières",
    "Subventions aux personnes de droit privé",
    "Subventions d'équipement versées",
    "Annuité de la dette",
    "Encours de dette",
    "Epargne brute",
    "Recettes de fonctionnement",
    "Recettes d'investissement",
    "Dotation globale de fonctionnement",
    "Allocations RSA",
    "Allocations APA",
]

VAR_DGF = "Montant Dotation DGF"
VAR_POP = "Population INSEE"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS collectivites_departements (
    code_dep           TEXT NOT NULL,
    nom                TEXT NOT NULL,
    dep_fonctionnement REAL,
    dep_investissement REAL,
    euros_par_hab      REAL,      -- (fonctionnement + investissement) / population
    population         INTEGER,   -- somme des ptot communaux (population totale INSEE)
    nb_communes        INTEGER,
    exercice           INTEGER NOT NULL,
    PRIMARY KEY (code_dep, exercice)
);

CREATE TABLE IF NOT EXISTS collectivites_regions (
    code_region   TEXT NOT NULL,
    nom           TEXT NOT NULL,
    siren         TEXT,
    est_ctu       INTEGER NOT NULL DEFAULT 0,
    exercice      INTEGER NOT NULL,
    agregat       TEXT NOT NULL,
    montant       REAL,
    euros_par_hab REAL,
    population    INTEGER,
    PRIMARY KEY (code_region, exercice, agregat)
);

CREATE TABLE IF NOT EXISTS collectivites_conseils_departementaux (
    code_dep      TEXT NOT NULL,
    nom           TEXT NOT NULL,
    siren         TEXT,
    exercice      INTEGER NOT NULL,
    agregat       TEXT NOT NULL,
    montant       REAL,
    euros_par_hab REAL,
    population    INTEGER,
    PRIMARY KEY (code_dep, exercice, agregat)
);

CREATE TABLE IF NOT EXISTS collectivites_communes_top200 (
    code_insee          TEXT NOT NULL,
    nom                 TEXT NOT NULL,
    dep_code            TEXT,
    dep_nom             TEXT,
    siren               TEXT,
    population          INTEGER,
    dep_fonctionnement  REAL,
    fonct_euros_par_hab REAL,
    dep_investissement  REAL,
    inv_euros_par_hab   REAL,
    exercice            INTEGER NOT NULL,
    PRIMARY KEY (code_insee, exercice)
);

CREATE TABLE IF NOT EXISTS collectivites_communes_series (
    code_insee         TEXT NOT NULL,
    nom                TEXT NOT NULL,
    siren              TEXT,
    tranche_population TEXT,      -- strate OFGL codée '0'..'10' (population au 01/01/2025)
    epci_nom           TEXT,      -- groupement à fiscalité propre 2025 (NULL si isolée)
    exercice           INTEGER NOT NULL,
    agregat            TEXT NOT NULL,
    montant            REAL,
    euros_par_hab      REAL,
    population         INTEGER,
    PRIMARY KEY (code_insee, exercice, agregat)
);

CREATE TABLE IF NOT EXISTS collectivites_communes_strates (
    tranche_population    TEXT NOT NULL,   -- strate OFGL codée '0'..'10'
    exercice              INTEGER NOT NULL,
    agregat               TEXT NOT NULL,
    mediane_euros_par_hab REAL,
    nb_communes           INTEGER,         -- effectif de la strate (budgets principaux)
    PRIMARY KEY (tranche_population, exercice, agregat)
);

CREATE TABLE IF NOT EXISTS dotations_dgf (
    niveau      TEXT NOT NULL CHECK (niveau IN ('national', 'departement', 'commune')),
    code        TEXT NOT NULL,
    nom         TEXT NOT NULL,
    exercice    INTEGER NOT NULL,
    dgf_montant REAL NOT NULL,
    population  INTEGER,
    dgf_par_hab REAL,
    rang        TEXT CHECK (rang IN ('top', 'flop') OR rang IS NULL),
    nb_communes INTEGER,
    PRIMARY KEY (niveau, code, exercice)
);
CREATE INDEX IF NOT EXISTS idx_dgf_niveau_exercice ON dotations_dgf(niveau, exercice);
"""

# Colonnes à typer explicitement à la lecture DuckDB (codes à zéros de tête,
# SIREN à garder en texte) ; le reste est inféré (montants DOUBLE, ptot BIGINT).
_TYPES_COMMUNES = (
    "{'exer':'VARCHAR','com_code':'VARCHAR','dep_code':'VARCHAR','reg_code':'VARCHAR','siren':'VARCHAR'}"
)
_TYPES_SERIES_DEP = "{'exer':'VARCHAR','dep_code':'VARCHAR','siren':'VARCHAR'}"
_TYPES_SERIES_REG = "{'exer':'VARCHAR','reg_code':'VARCHAR','siren':'VARCHAR'}"
_TYPES_DGF = "{'exercice':'VARCHAR','code_insee':'VARCHAR','code_departement':'VARCHAR'}"
_TYPES_SERIES_COM = (
    "{'exer':'VARCHAR','com_code':'VARCHAR','siren':'VARCHAR','tranche_population':'VARCHAR'}"
)
_TYPES_STRATES = "{'tranche_population':'VARCHAR','exercice':'VARCHAR'}"


# ---------------------------------------------------------------------------
# Rapatriement (exports filtrés + group_by serveur)
# ---------------------------------------------------------------------------


def _url_export(dataset: str, where: str, select: str, group_by: str | None = None) -> str:
    params = {"where": where, "select": select}
    if group_by:
        params["group_by"] = group_by
    return f"{API}/{dataset}/exports/csv?" + urlencode(params)


def _liste_in(valeurs: list[str]) -> str:
    """Clause ODSQL `in ("a","b",...)` (littéraux entre guillemets doubles)."""
    return "(" + ",".join(f'"{v}"' for v in valeurs) + ")"


def telecharger_exports(session: requests.Session, max_age_heures: float = 12.0) -> dict[str, Path]:
    """Rapatrie les 5 exports filtrés OFGL dans data/raw/ofgl/ (~15 Mo au
    total — l'export « strates » est agrégé PAR LE SERVEUR : ~176 lignes).

    Les séries communales, elles, dépendent de la liste des 200 communes
    (dérivée de l'export comptes) : `telecharger_series_communes`."""
    chemins: dict[str, Path] = {}

    where = (
        f'year(exer)={EXERCICE_COMPTES} and type_de_budget="Budget principal" '
        f"and agregat in {_liste_in([AGREGAT_FONCT, AGREGAT_INVEST])}"
    )
    select = "exer,com_code,com_name,dep_code,dep_name,reg_code,reg_name,siren,agregat,montant,euros_par_habitant,ptot"
    chemins["communes"] = telecharger(
        _url_export("ofgl-base-communes", where, select),
        f"ofgl/communes-comptes-{EXERCICE_COMPTES}.csv",
        max_age_heures=max_age_heures,
        session=session,
    )

    where = (
        f'year(exer)>={SERIE_DEBUT} and type_de_budget="Budget principal" '
        f"and agregat in {_liste_in(AGREGATS_SERIES)}"
    )
    chemins["departements"] = telecharger(
        _url_export(
            "ofgl-base-departements",
            where,
            "exer,dep_code,dep_name,siren,agregat,montant,euros_par_habitant,ptot",
        ),
        f"ofgl/departements-series-{SERIE_DEBUT}-{EXERCICE_COMPTES}.csv",
        max_age_heures=max_age_heures,
        session=session,
    )
    chemins["regions"] = telecharger(
        _url_export(
            "ofgl-base-regions",
            where,
            "exer,reg_code,reg_name,reg_is_ctu,siren,agregat,montant,euros_par_habitant,ptot",
        ),
        f"ofgl/regions-series-{SERIE_DEBUT}-{EXERCICE_COMPTES}.csv",
        max_age_heures=max_age_heures,
        session=session,
    )

    where = (
        f'year(exer)>={SERIE_DEBUT} and type_de_budget="Budget principal" '
        f"and agregat in {_liste_in(AGREGATS_COMMUNES)}"
    )
    chemins["strates"] = telecharger(
        _url_export(
            "ofgl-base-communes",
            where,
            "median(euros_par_habitant) as mediane,count(*) as nb_communes",
            group_by="tranche_population,year(exer) as exercice,agregat",
        ),
        f"ofgl/communes-strates-medianes-{SERIE_DEBUT}-{EXERCICE_COMPTES}.csv",
        max_age_heures=max_age_heures,
        session=session,
    )

    where = (
        f"year(exercice)={ANNEE_DGF_DETAIL} and variable in {_liste_in([VAR_DGF, VAR_POP])}"
    )
    chemins["dgf"] = telecharger(
        _url_export(
            "dotations-communes",
            where,
            "exercice,code_insee,commune,code_departement,nom_departement,variable,valeur",
        ),
        f"ofgl/dotations-dgf-communes-{ANNEE_DGF_DETAIL}.csv",
        max_age_heures=max_age_heures,
        session=session,
    )
    return chemins


def telecharger_series_communes(
    session: requests.Session,
    codes_insee: list[str],
    max_age_heures: float = 12.0,
) -> list[Path]:
    """Séries 2018-2025 des communes listées (le top 200), par lots de
    `TAILLE_LOT_COMMUNES` codes INSEE — exports filtrés `com_code in (...)`,
    JAMAIS le jeu ofgl-base-communes entier (21,9 M de lignes)."""
    select = (
        "exer,com_code,com_name,siren,tranche_population,epci_name,"
        "agregat,montant,euros_par_habitant,ptot"
    )
    chemins: list[Path] = []
    for i in range(0, len(codes_insee), TAILLE_LOT_COMMUNES):
        lot = codes_insee[i : i + TAILLE_LOT_COMMUNES]
        where = (
            f'year(exer)>={SERIE_DEBUT} and type_de_budget="Budget principal" '
            f"and agregat in {_liste_in(AGREGATS_COMMUNES)} "
            f"and com_code in {_liste_in(lot)}"
        )
        chemins.append(
            telecharger(
                _url_export("ofgl-base-communes", where, select),
                f"ofgl/communes-series-{SERIE_DEBUT}-{EXERCICE_COMPTES}"
                f"-lot{i // TAILLE_LOT_COMMUNES:02d}.csv",
                max_age_heures=max_age_heures,
                session=session,
            )
        )
    return chemins


def _records(session: requests.Session, dataset: str, params: dict) -> list[dict]:
    """GET /records (group_by serveur), résultats bruts. Lève sur HTTP ≠ 2xx."""
    r = session.get(f"{API}/{dataset}/records", params=params, timeout=120)
    r.raise_for_status()
    return r.json()["results"]


def dgf_nationale_par_annee(session: requests.Session) -> list[tuple]:
    """Série nationale DGF des communes 2018-2026 : deux group_by serveur
    (somme des montants, puis somme des populations INSEE), joints par année.

    Retour : [(annee, dgf_totale, population, dgf_par_hab, nb_communes), ...]
    """
    montants = _records(
        session,
        "dotations-communes",
        {
            "where": f'variable="{VAR_DGF}"',
            "group_by": "year(exercice) as annee",
            "select": "sum(valeur) as total, count(*) as nb",
            "limit": 20,
        },
    )
    pops = _records(
        session,
        "dotations-communes",
        {
            "where": f'variable="{VAR_POP}"',
            "group_by": "year(exercice) as annee",
            "select": "sum(valeur) as pop",
            "limit": 20,
        },
    )
    pop_par_annee = {int(r["annee"]): r["pop"] for r in pops}
    lignes = []
    for r in sorted(montants, key=lambda x: int(x["annee"])):
        annee = int(r["annee"])
        total = float(r["total"])
        pop = pop_par_annee.get(annee)
        par_hab = (total / pop) if pop else None
        lignes.append((annee, total, int(pop) if pop else None, par_hab, int(r["nb"])))
    annees = {ligne[0] for ligne in lignes}
    if not set(DGF_ANNEES) <= annees:
        raise RuntimeError(f"série DGF nationale incomplète : {sorted(annees)} (attendu {DGF_ANNEES})")
    return lignes


def verifier_fraicheur(session: requests.Session) -> dict[str, str]:
    """Re-vérifie en ligne la date de modification des 4 jeux OFGL
    (convention SOURCES.md §0.2 : ne jamais se fier à la recherche d'hier)."""
    dates = {}
    for ds in ("ofgl-base-communes", "ofgl-base-departements", "ofgl-base-regions", "dotations-communes"):
        r = session.get(f"{API}/{ds}", timeout=60)
        r.raise_for_status()
        dates[ds] = (r.json().get("metas", {}).get("default", {}).get("modified") or "?")[:10]
    log.info("fraîcheur OFGL constatée : %s", dates)
    return dates


# ---------------------------------------------------------------------------
# Transformations pures (DuckDB sur les exports CSV) — testées sur fixtures
# ---------------------------------------------------------------------------


def _duck(
    chemin: str | Path | list[str | Path], types: str
) -> duckdb.DuckDBPyConnection:
    chemins = chemin if isinstance(chemin, list) else [chemin]
    liste = ", ".join(f"'{Path(c).as_posix()}'" for c in chemins)
    conn = duckdb.connect()
    conn.execute(
        f"CREATE VIEW src AS SELECT * FROM read_csv([{liste}], "
        f"delim=';', header=true, types={types})"
    )
    return conn


_PIVOT_COMMUNES = f"""
SELECT com_code,
       any_value(com_name)                                        AS nom,
       any_value(dep_code)                                        AS dep_code,
       any_value(dep_name)                                        AS dep_nom,
       any_value(siren)                                           AS siren,
       max(ptot)                                                  AS ptot,
       max(CASE WHEN agregat = '{AGREGAT_FONCT}' THEN montant END)             AS fonct,
       max(CASE WHEN agregat = '{AGREGAT_FONCT}' THEN euros_par_habitant END)  AS fonct_hab,
       max(CASE WHEN agregat = '{AGREGAT_INVEST.replace("'", "''")}' THEN montant END)            AS inv,
       max(CASE WHEN agregat = '{AGREGAT_INVEST.replace("'", "''")}' THEN euros_par_habitant END) AS inv_hab,
       CAST(substr(any_value(exer), 1, 4) AS INTEGER)             AS exercice
FROM src
GROUP BY com_code
"""


def agreger_departements(chemin_csv: str | Path) -> list[tuple]:
    """Agrège les communes par département (export comptes 2025).

    Retour : [(code_dep, nom, fonctionnement, investissement, euros_par_hab,
    population, nb_communes, exercice)] — euros_par_hab = (fonct+inv)/pop,
    NULL si population nulle (communes « mortes pour la France » sans habitant).
    """
    with _duck(chemin_csv, _TYPES_COMMUNES) as c:
        return c.execute(
            f"""
            WITH piv AS ({_PIVOT_COMMUNES})
            SELECT dep_code,
                   any_value(dep_nom),
                   round(sum(fonct), 2),
                   round(sum(inv), 2),
                   CASE WHEN coalesce(sum(ptot), 0) > 0
                        THEN round((coalesce(sum(fonct), 0) + coalesce(sum(inv), 0)) / sum(ptot), 2)
                   END,
                   CAST(sum(ptot) AS BIGINT),
                   count(*),
                   any_value(exercice)
            FROM piv
            GROUP BY dep_code
            ORDER BY dep_code
            """
        ).fetchall()


def top_communes(chemin_csv: str | Path, top_n: int = TOP_COMMUNES) -> list[tuple]:
    """Top `top_n` communes par population (export comptes 2025), pivotées.

    Retour : [(code_insee, nom, dep_code, dep_nom, siren, population,
    fonctionnement, fonct_euros_par_hab, investissement, inv_euros_par_hab,
    exercice)] — les €/habitant sont ceux calculés par l'OFGL.
    """
    with _duck(chemin_csv, _TYPES_COMMUNES) as c:
        return c.execute(
            f"""
            WITH piv AS ({_PIVOT_COMMUNES})
            SELECT com_code, nom, dep_code, dep_nom, siren,
                   CAST(ptot AS BIGINT),
                   round(fonct, 2), round(fonct_hab, 2),
                   round(inv, 2), round(inv_hab, 2),
                   exercice
            FROM piv
            WHERE ptot IS NOT NULL AND ptot > 0
            ORDER BY ptot DESC, com_code
            LIMIT {int(top_n)}
            """
        ).fetchall()


def series_conseils(chemin_csv: str | Path, niveau: str) -> list[tuple]:
    """Séries 2018-2025 par grande catégorie pour les conseils régionaux
    (`niveau='region'`, avec drapeau CTU) ou départementaux (`niveau='departement'`).

    Retour région : [(code, nom, siren, est_ctu, exercice, agregat, montant,
    euros_par_hab, population)] ; département : idem sans est_ctu.
    """
    if niveau == "region":
        cols = "reg_code, any_value(reg_name), any_value(siren), max(CASE WHEN reg_is_ctu = 'Oui' THEN 1 ELSE 0 END)"
        types, cle = _TYPES_SERIES_REG, "reg_code"
    elif niveau == "departement":
        cols = "dep_code, any_value(dep_name), any_value(siren)"
        types, cle = _TYPES_SERIES_DEP, "dep_code"
    else:
        raise ValueError(f"niveau inconnu : {niveau!r}")
    with _duck(chemin_csv, types) as c:
        return c.execute(
            f"""
            SELECT {cols},
                   CAST(substr(any_value(exer), 1, 4) AS INTEGER) AS exercice,
                   agregat,
                   round(sum(montant), 2),
                   round(CASE WHEN coalesce(max(ptot), 0) > 0 THEN sum(montant) / max(ptot) END, 2),
                   CAST(max(ptot) AS BIGINT)
            FROM src
            GROUP BY {cle}, substr(exer, 1, 4), agregat
            ORDER BY 1, exercice, agregat
            """
        ).fetchall()


def series_communes(
    chemins_csv: list[str | Path], codes_retenus: list[str]
) -> list[tuple]:
    """Séries 2018-2025 des communes du top 200 (exports par lots), format
    long aligné sur `series_conseils`.

    Retour : [(code_insee, nom, siren, tranche_population, epci_nom,
    exercice, agregat, montant, euros_par_hab, population)] — l'€/habitant
    est celui calculé par l'OFGL (une ligne source par commune × exercice ×
    agrégat en budget principal). Un exercice absent de la source reste
    ABSENT (aucune ligne) : le front affiche « donnée non disponible »,
    jamais 0.
    """
    retenus = set(codes_retenus)
    with _duck(list(chemins_csv), _TYPES_SERIES_COM) as c:
        lignes = c.execute(
            """
            SELECT com_code,
                   any_value(com_name),
                   any_value(siren),
                   any_value(tranche_population),
                   any_value(epci_name),
                   CAST(substr(any_value(exer), 1, 4) AS INTEGER) AS exercice,
                   agregat,
                   round(sum(montant), 2),
                   round(max(euros_par_habitant), 2),
                   CAST(max(ptot) AS BIGINT)
            FROM src
            GROUP BY com_code, substr(exer, 1, 4), agregat
            ORDER BY com_code, exercice, agregat
            """
        ).fetchall()
    return [l for l in lignes if l[0] in retenus]


def medianes_strates(chemin_csv: str | Path) -> list[tuple]:
    """Médianes d'€/habitant par strate × exercice × agrégat (export agrégé
    par le serveur OFGL : median() + count() sur les budgets principaux).

    Retour : [(tranche_population, exercice, agregat,
    mediane_euros_par_hab, nb_communes)].
    """
    with _duck(chemin_csv, _TYPES_STRATES) as c:
        return c.execute(
            """
            SELECT tranche_population,
                   CAST(exercice AS INTEGER),
                   agregat,
                   round(mediane, 2),
                   CAST(nb_communes AS BIGINT)
            FROM src
            ORDER BY CAST(tranche_population AS INTEGER), exercice, agregat
            """
        ).fetchall()


def pivot_dgf_communes(chemin_csv: str | Path) -> list[tuple]:
    """Pivote l'export dotations 2026 : une ligne par commune.

    Retour : [(code_insee, commune, code_departement, nom_departement,
    dgf, population, dgf_par_hab, exercice)] — noms de communes tels que
    publiés par l'OFGL (majuscules, suffixe « (dep) »).
    """
    with _duck(chemin_csv, _TYPES_DGF) as c:
        return c.execute(
            f"""
            SELECT code_insee,
                   any_value(commune),
                   any_value(code_departement),
                   any_value(nom_departement),
                   max(CASE WHEN variable = '{VAR_DGF}' THEN valeur END)  AS dgf,
                   CAST(max(CASE WHEN variable = '{VAR_POP}' THEN valeur END) AS BIGINT) AS pop,
                   round(CASE WHEN max(CASE WHEN variable = '{VAR_POP}' THEN valeur END) > 0
                              THEN max(CASE WHEN variable = '{VAR_DGF}' THEN valeur END)
                                   / max(CASE WHEN variable = '{VAR_POP}' THEN valeur END)
                         END, 2)                                          AS dgf_par_hab,
                   CAST(substr(any_value(exercice), 1, 4) AS INTEGER)     AS exercice
            FROM src
            GROUP BY code_insee
            ORDER BY code_insee
            """
        ).fetchall()


# Le jeu dotations-communes code la Corse « 20A »/« 20B » là où les comptes
# OFGL (et l'INSEE) disent « 2A »/« 2B » : normalisé pour la jointure carte.
_NORMALISATION_DEP = {"20A": "2A", "20B": "2B"}


def agreger_dgf_departements(communes_dgf: list[tuple]) -> list[tuple]:
    """Agrège le pivot DGF par département : [(code_dep, nom, dgf, pop,
    dgf_par_hab, nb_communes, exercice)]. Codes Corse normalisés en 2A/2B."""
    par_dep: dict[str, list] = {}
    for _insee, _nom, dep, dep_nom, dgf, pop, _ph, exercice in communes_dgf:
        if dgf is None:
            continue
        dep = _NORMALISATION_DEP.get(dep, dep)
        acc = par_dep.setdefault(dep, [dep_nom, 0.0, 0, 0, exercice])
        acc[1] += dgf
        acc[2] += pop or 0
        acc[3] += 1
    lignes = []
    for dep, (dep_nom, dgf, pop, nb, exercice) in sorted(par_dep.items()):
        lignes.append((dep, dep_nom, round(dgf, 2), pop, round(dgf / pop, 2) if pop else None, nb, exercice))
    return lignes


def communes_dgf_retenues(
    communes_dgf: list[tuple],
    seuil_pop: int = SEUIL_POP_TOP_FLOP,
    n: int = NB_TOP_FLOP,
) -> list[tuple]:
    """Communes ≥ `seuil_pop` habitants (≈ 480 « grandes communes »), avec
    rang 'top'/'flop' pour les `n` extrêmes en DGF/hab, NULL entre les deux.

    Retour : [(code_insee, commune, exercice, dgf, pop, dgf_par_hab, rang)].
    Une DGF nulle est une donnée réelle (écrêtement — Paris est à 0 €).
    """
    eligibles = [
        c for c in communes_dgf
        if c[4] is not None and c[5] is not None and c[5] >= seuil_pop
    ]
    eligibles.sort(key=lambda c: c[6], reverse=True)
    lignes = []
    for i, c in enumerate(eligibles):
        rang = "top" if i < n else ("flop" if i >= len(eligibles) - n and i >= n else None)
        lignes.append((c[0], c[1], c[7], c[4], c[5], c[6], rang))
    return lignes


# ---------------------------------------------------------------------------
# Chargement SQLite + contrôles de vraisemblance
# ---------------------------------------------------------------------------


def charger(
    conn,
    deps: list[tuple],
    communes: list[tuple],
    regions: list[tuple],
    conseils_dep: list[tuple],
    dgf_national: list[tuple],
    dgf_deps: list[tuple],
    dgf_grandes_communes: list[tuple],
    series_com: list[tuple] = (),
    strates: list[tuple] = (),
) -> dict[str, int]:
    """Delete+insert dans les tables possédées par le pipeline (idempotent),
    upsert des entités. Ne commite pas (le commit suit les contrôles)."""
    # Migration : la table s'est appelée `collectivites_communes` jusqu'en
    # août 2026 — le nom promettait les ~34 900 communes de France alors
    # qu'elle en portait 200. Une base construite avant le renommage garde
    # l'ancienne table : on la retire pour qu'elle ne trompe personne.
    conn.execute("DROP TABLE IF EXISTS collectivites_communes")
    conn.executescript(_SCHEMA)

    conn.execute("DELETE FROM collectivites_departements")
    conn.executemany(
        "INSERT INTO collectivites_departements VALUES (?,?,?,?,?,?,?,?)", deps
    )
    conn.execute("DELETE FROM collectivites_communes_top200")
    conn.executemany(
        "INSERT INTO collectivites_communes_top200 VALUES (?,?,?,?,?,?,?,?,?,?,?)", communes
    )
    conn.execute("DELETE FROM collectivites_communes_series")
    conn.executemany(
        "INSERT INTO collectivites_communes_series VALUES (?,?,?,?,?,?,?,?,?,?)",
        series_com,
    )
    conn.execute("DELETE FROM collectivites_communes_strates")
    conn.executemany(
        "INSERT INTO collectivites_communes_strates VALUES (?,?,?,?,?)", strates
    )
    conn.execute("DELETE FROM collectivites_regions")
    conn.executemany(
        "INSERT INTO collectivites_regions VALUES (?,?,?,?,?,?,?,?,?)", regions
    )
    conn.execute("DELETE FROM collectivites_conseils_departementaux")
    conn.executemany(
        "INSERT INTO collectivites_conseils_departementaux VALUES (?,?,?,?,?,?,?,?)",
        conseils_dep,
    )

    conn.execute("DELETE FROM dotations_dgf")
    conn.executemany(
        "INSERT INTO dotations_dgf VALUES ('national','FR','France (communes)',?,?,?,?,NULL,?)",
        dgf_national,
    )
    conn.executemany(
        "INSERT INTO dotations_dgf (niveau, code, nom, exercice, dgf_montant, population,"
        " dgf_par_hab, rang, nb_communes)"
        " VALUES ('departement',?,?,?,?,?,?,NULL,?)",
        [(d[0], d[1], d[6], d[2], d[3], d[4], d[5]) for d in dgf_deps],
    )
    conn.executemany(
        "INSERT INTO dotations_dgf (niveau, code, nom, exercice, dgf_montant, population,"
        " dgf_par_hab, rang, nb_communes)"
        " VALUES ('commune',?,?,?,?,?,?,?,NULL)",
        [(c[0], c[1], c[2], c[3], c[4], c[5], c[6]) for c in dgf_grandes_communes],
    )

    upsert = """
        INSERT INTO entites (id, type, nom, siren, departement)
        VALUES (?, 'collectivite', ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nom = excluded.nom, siren = excluded.siren, departement = excluded.departement
    """
    if regions:
        annee_max = max(r[4] for r in regions)
        conn.executemany(
            upsert,
            {(f"COLL-REG-{r[0]}", r[1], r[2], None) for r in regions if r[4] == annee_max},
        )
    if conseils_dep:
        annee_max = max(d[3] for d in conseils_dep)
        conn.executemany(
            upsert,
            {(f"COLL-DEP-{d[0]}", d[1], d[2], d[0]) for d in conseils_dep if d[3] == annee_max},
        )
    conn.executemany(
        upsert, [(f"COLL-COM-{c[0]}", c[1], c[4], c[2]) for c in communes]
    )

    return {
        "collectivites_departements": len(deps),
        "collectivites_communes_top200": len(communes),
        "collectivites_communes_series": len(series_com),
        "collectivites_communes_strates": len(strates),
        "collectivites_regions": len(regions),
        "collectivites_conseils_departementaux": len(conseils_dep),
        "dotations_dgf": len(dgf_national) + len(dgf_deps) + len(dgf_grandes_communes),
    }


def verifier(conn) -> None:
    """Contrôles de vraisemblance sur la base chargée. Lève RuntimeError si KO
    (le commit n'a pas encore eu lieu : la base reste intacte)."""
    def un(sql: str):
        return conn.execute(sql).fetchone()[0]

    problemes = []

    n = un(f"SELECT count(*) FROM collectivites_departements WHERE exercice = {EXERCICE_COMPTES}")
    if not 100 <= n <= 102:
        problemes.append(f"carte départementale : {n} départements (101 attendus)")
    n = un(
        "SELECT count(*) FROM collectivites_departements"
        " WHERE euros_par_hab IS NULL OR euros_par_hab <= 0 OR euros_par_hab > 10000"
    )
    if n:
        problemes.append(f"carte départementale : {n} €/hab hors de ]0 ; 10 000]")

    n = un("SELECT count(*) FROM collectivites_communes_top200")
    if n != TOP_COMMUNES:
        problemes.append(f"top communes : {n} lignes ({TOP_COMMUNES} attendues)")
    n = un(
        "SELECT count(*) FROM collectivites_communes_top200"
        " WHERE fonct_euros_par_hab <= 0 OR fonct_euros_par_hab > 10000"
        "    OR inv_euros_par_hab < 0 OR inv_euros_par_hab > 10000"
    )
    if n:
        problemes.append(f"top communes : {n} €/hab aberrants")
    marseille = conn.execute(
        "SELECT dep_fonctionnement, fonct_euros_par_hab FROM collectivites_communes_top200"
        " WHERE code_insee = '13055'"
    ).fetchone()
    if marseille is None:
        problemes.append("Marseille absente du top communes")
    elif not (1.0e9 < marseille[0] < 2.0e9 and 1000 < marseille[1] < 2500):
        problemes.append(f"Marseille hors plage attendue : {tuple(marseille)}")

    nb_exercices = EXERCICE_COMPTES - SERIE_DEBUT + 1
    n = un("SELECT count(DISTINCT code_insee) FROM collectivites_communes_series")
    if n != TOP_COMMUNES:
        problemes.append(f"séries communales : {n} communes ({TOP_COMMUNES} attendues)")
    n = un(
        "SELECT count(*) FROM collectivites_communes_series"
        f" WHERE code_insee = '13055' AND agregat = '{AGREGAT_FONCT}'"
    )
    if n != nb_exercices:
        problemes.append(
            f"séries communales : Marseille a {n} exercices de fonctionnement"
            f" ({nb_exercices} attendus)"
        )
    n = un(
        "SELECT count(*) FROM collectivites_communes_series"
        " WHERE euros_par_hab IS NULL OR euros_par_hab < 0 OR euros_par_hab > 10000"
    )
    if n:
        problemes.append(f"séries communales : {n} €/hab hors de [0 ; 10 000]")

    n = un("SELECT count(*) FROM collectivites_communes_strates")
    if not 100 <= n <= 300:  # 11 strates × exercices × agrégats (~176)
        problemes.append(f"médianes de strate : {n} lignes (~176 attendues)")
    n = un(
        "SELECT count(*) FROM collectivites_communes_strates"
        " WHERE mediane_euros_par_hab IS NULL OR mediane_euros_par_hab <= 0"
        "    OR mediane_euros_par_hab > 10000 OR nb_communes <= 0"
    )
    if n:
        problemes.append(f"médianes de strate : {n} lignes invraisemblables")

    n = un(
        f"SELECT count(DISTINCT code_region) FROM collectivites_regions WHERE exercice = {EXERCICE_COMPTES}"
    )
    if not 15 <= n <= 20:
        problemes.append(f"régions {EXERCICE_COMPTES} : {n} (17 attendues)")
    n = un(
        "SELECT count(DISTINCT code_dep) FROM collectivites_conseils_departementaux"
        f" WHERE exercice = {EXERCICE_COMPTES}"
    )
    if not 90 <= n <= 105:
        problemes.append(f"conseils départementaux {EXERCICE_COMPTES} : {n} (97 attendus)")

    n = un("SELECT count(*) FROM dotations_dgf WHERE niveau = 'national'")
    if n != len(DGF_ANNEES):
        problemes.append(f"DGF nationale : {n} exercices ({len(DGF_ANNEES)} attendus)")
    lyon = conn.execute(
        "SELECT dgf_montant FROM dotations_dgf"
        f" WHERE niveau = 'commune' AND code = '69123' AND exercice = {ANNEE_DGF_DETAIL}"
    ).fetchone()
    if lyon is None:
        problemes.append(f"DGF Lyon {ANNEE_DGF_DETAIL} absente (attendue : communes ≥ {SEUIL_POP_TOP_FLOP} hab.)")
    elif lyon[0] <= 0:
        problemes.append(f"DGF Lyon {ANNEE_DGF_DETAIL} non positive : {lyon[0]}")
    n = un("SELECT count(*) FROM dotations_dgf WHERE dgf_montant < 0 OR dgf_par_hab < 0")
    if n:
        problemes.append(f"dotations_dgf : {n} montants ou €/hab négatifs")

    if problemes:
        raise RuntimeError("contrôles de vraisemblance KO : " + " ; ".join(problemes))


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def executer() -> None:
    session = session_http()
    fraicheur = verifier_fraicheur(session)
    chemins = telecharger_exports(session)

    log.info("transformation DuckDB des exports…")
    deps = agreger_departements(chemins["communes"])
    communes = top_communes(chemins["communes"])
    regions = series_conseils(chemins["regions"], "region")
    conseils = series_conseils(chemins["departements"], "departement")
    dgf_communes = pivot_dgf_communes(chemins["dgf"])
    dgf_deps = agreger_dgf_departements(dgf_communes)
    dgf_grandes = communes_dgf_retenues(dgf_communes)
    dgf_nat = dgf_nationale_par_annee(session)

    # Séries communales : mêmes 200 communes que le top (la liste vient de
    # l'export comptes, jamais d'une liste en dur), exports par lots.
    codes_top = [c[0] for c in communes]
    chemins_series = telecharger_series_communes(session, codes_top)
    series_com = series_communes(chemins_series, codes_top)
    strates = medianes_strates(chemins["strates"])

    conn = db.init_db()
    try:
        comptes = charger(
            conn, deps, communes, regions, conseils, dgf_nat, dgf_deps, dgf_grandes,
            series_com, strates,
        )
        verifier(conn)
        conn.commit()
        db.upsert_meta(
            conn,
            source_id="S16",
            nom="OFGL — comptes des collectivités et dotations DGF (data.ofgl.fr)",
            url="https://data.ofgl.fr/explore/dataset/ofgl-base-communes/",
            licence="Licence Ouverte 2.0",
            frequence="annuelle (comptes N chargés en juillet N+1, provisoires jusqu'en décembre ; dotations N au printemps N)",
            date_donnees=f"{EXERCICE_COMPTES}-12-31",
            lignes=sum(comptes.values()),
            notes=(
                f"Comptes {EXERCICE_COMPTES} provisoires (~97 communes manquantes jusqu'à déc. 2026) ; "
                f"dotations DGF jusqu'à l'exercice {ANNEE_DGF_DETAIL}. "
                f"Séries communales {SERIE_DEBUT}-{EXERCICE_COMPTES} (top {TOP_COMMUNES}, "
                f"budgets principaux) et médianes d'€/hab par strate démographique "
                f"(médiane calculée par l'API OFGL sur l'ensemble des communes). "
                f"MAJ OFGL revérifiées ce jour : communes {fraicheur['ofgl-base-communes']}, "
                f"départements {fraicheur['ofgl-base-departements']}, "
                f"régions {fraicheur['ofgl-base-regions']}, "
                f"dotations {fraicheur['dotations-communes']}. "
                f"Top/flop DGF/hab : communes ≥ {SEUIL_POP_TOP_FLOP} hab. (une DGF à 0 € est réelle : écrêtement)."
            ),
        )
    finally:
        conn.close()

    for table, n in comptes.items():
        log.info("table %s : %d lignes", table, n)
    log.info("P11 finances locales : OK")


def main() -> int:
    try:
        executer()
    except Exception:
        log.exception("échec du pipeline finances locales")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
