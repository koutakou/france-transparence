"""P26 — Dépenses des APU par fonction (S49, Eurostat gov_10a_exp, CFAP).

Source : JSON-stat `gov_10a_exp`, deux extraits figés
geo=FR × sector=S13 × na_item=TE × cofog99 ∈ {TOTAL, GF01…GF10}
× unit=MIO_EUR, et les mêmes filtres en unit=PC_GDP.
DOI : https://doi.org/10.2908/GOV_10A_EXP
Licence : décision 2011/833/UE (réutilisation des données statistiques
Eurostat) — pas CC BY 4.0. La France est un État membre : l'exception
« pays tiers, réutilisation commerciale » ne s'applique pas.

CE PIPELINE N'EST PAS LA SOURCE S13, NI S44, NI S45
---------------------------------------------------
Le secteur ESA **S13** = administrations publiques (État, Odac, APUL, ASSO).
La source France Transparence **S13** = situations mensuelles budgétaires
DGFiP (flux de l'État, budget général, cumul depuis le 1er janvier).
La source **S44** = totaux TE/TR de `gov_10a_main` (table distincte).
La source **S45** = prestations DREES, tous régimes. `source_id` ici =
**S49**, jamais `'S13'` ni `'S44'` ni `'S45'`.

N'ingère que `na_item=TE` et les onze codes CFAP (TOTAL + dix divisions
GF01–GF10). Pas de groupes (GF0101…), pas de `P2`/`D1`/…, pas de
sous-secteur S.1311, pas de taxag, pas de montant par habitant.

TE est positif (flux brut). La conversion Md€ = MIO_EUR ÷ 1000 se fait
À LA LECTURE, jamais ÷ 1e9 (unité S13). PC_GDP est lu à part et n'est
PAS additif.

`date_donnees` = 31 décembre du TIME max de TOTAL
(2024 → 2024-12-31), jamais le champ JSON-stat `updated` (date de
diffusion GFS) ni OBS_PERIOD_OVERALL_LATEST (2025 listé, 0 valeur FR).

Le TIME max de S49 n'est PAS celui de S44 : au 25/08/2026, S44 porte
2025 et S49 s'arrête à 2024. Les deux totaux 2024 ne coïncident pas
(table distincte). On n'additionne pas, on ne « ventile » pas S44.

Exécution : python -m pipelines.ingest_cofog_apu
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente (DELETE puis
INSERT dans une transaction), puis upsert_meta('S49', …). Échec → exit ≠ 0,
base intacte.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("cofog_apu")

SOURCE_ID = "S49"
NOM_SOURCE = (
    "Dépenses des APU par fonction "
    "(Eurostat gov_10a_exp, CFAP / COFOG-99, TE)"
)
URL_DOI = "https://doi.org/10.2908/GOV_10A_EXP"
LICENCE = "Décision 2011/833/UE (réutilisation des données statistiques Eurostat)"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24

NA_ITEM = "TE"
UNITES = ("MIO_EUR", "PC_GDP")

# Dix divisions CFAP + le total. Les groupes (GF0101…) ne sont pas ingérés :
# ils recouvrent les divisions.
DIVISIONS = tuple(f"GF{i:02d}" for i in range(1, 11))
CODES = ("TOTAL",) + DIVISIONS
CODES_SET = frozenset(CODES)

# Libellés FR d'Eurostat (lang=FR), figés : un écart à l'ingestion échoue
# plutôt que d'afficher un nom inventé. TOTAL reste « Total » côté API ;
# le libellé citoyen du total est posé à la lecture, pas ici.
LIBELLES_FR = {
    "TOTAL": "Total",
    "GF01": "Services généraux des administrations publiques",
    "GF02": "Défense",
    "GF03": "Ordre et sécurité publics",
    "GF04": "Affaires économiques",
    "GF05": "Protection de l'environnement",
    "GF06": "Logements et équipements collectifs",
    "GF07": "Santé",
    "GF08": "Loisirs, culture et culte",
    "GF09": "Enseignement",
    "GF10": "Protection sociale",
}

FICHIERS_RAW = {
    "MIO_EUR": "eurostat/gov_10a_exp_te_mio.json",
    "PC_GDP": "eurostat/gov_10a_exp_te_pc.json",
}

ANNEE_RE = re.compile(r"^\d{4}$")

# Bornes d'unité sur le TIME max de TOTAL, pas la fixture.
BORNE_MIN_MIO = 2e5  # exclusive — 200 Md€
BORNE_MAX_MIO = 4e6  # exclusive — 4 000 Md€
BORNE_MIN_PC = 30.0  # exclusive
BORNE_MAX_PC = 80.0  # exclusive
N_ANNEES_MIN = 25
# Arrondi JSON-stat des onze postes : max observé 0,4 M€ sur 1995–2024.
TOLERANCE_ADDITIVITE_MIO = 1.0

NOTES = (
    "flux annuel, na_item=TE, CFAP (COFOG-99) TOTAL + GF01–GF10 ; "
    "ESA S13 = APU, distinct de la source S13 (SMB DGFiP, budget de l'État), "
    "de S44 (TE gov_10a_main, table distincte) et de S45 (prestations DREES) ; "
    "pas un indicateur Maastricht ; "
    "Md€ = MIO_EUR÷1000 (jamais ÷1e9) ; "
    "PC_GDP lu à part, non additif ; "
    "groupes GF0101… non ingérés ; pas de taxag, pas de S.1311, pas de par habitant ; "
    "date_donnees = 31/12 du TIME max de TOTAL, jamais JSON-stat updated "
    "ni OBS_PERIOD_OVERALL_LATEST ; "
    "DOI 10.2908/GOV_10A_EXP"
)

_DDL = """
CREATE TABLE IF NOT EXISTS cofog_apu_esa (
    geo            TEXT NOT NULL CHECK (geo = 'FR'),
    sector         TEXT NOT NULL CHECK (sector = 'S13'), -- ESA APU, pas la source S13
    cofog99        TEXT NOT NULL CHECK (cofog99 IN (
                       'TOTAL','GF01','GF02','GF03','GF04','GF05',
                       'GF06','GF07','GF08','GF09','GF10'
                   )),
    libelle        TEXT NOT NULL,
    annee          INTEGER NOT NULL,
    valeur_mio_eur REAL NOT NULL CHECK (valeur_mio_eur > 0),
    valeur_pc_gdp  REAL NOT NULL CHECK (valeur_pc_gdp > 0),
    statut         TEXT,
    PRIMARY KEY (geo, sector, cofog99, annee)
);
"""


def url_api(unit: str) -> str:
    if unit not in UNITES:
        raise ValueError(f"unité hors contrat : {unit}")
    filtres = "".join(f"&cofog99={code}" for code in CODES)
    return (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        f"gov_10a_exp?format=JSON&geo=FR&unit={unit}&sector=S13"
        f"&na_item={NA_ITEM}{filtres}&lang=FR"
    )


def mio_en_md(mio: float) -> float:
    """MIO_EUR → Md€. Un million d'euros = 0,001 milliard. Jamais ÷ 1e9."""
    return mio / 1000.0


def date_fin_annee(annee: int) -> str:
    """31 décembre de l'année TIME : 2024 → 2024-12-31."""
    if not isinstance(annee, int) or annee < 1900 or annee > 2100:
        raise ValueError(f"année hors plage : {annee!r}")
    return f"{annee}-12-31"


def _index_categorie(dimension: dict, nom: str) -> dict:
    try:
        idx = dimension[nom]["category"]["index"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"dimension JSON-stat {nom!r} absente") from exc
    if not isinstance(idx, dict) or not idx:
        raise ValueError(f"dimension JSON-stat {nom!r} sans codes")
    return idx


def _verifier_dimension_unique(dimension: dict, nom: str, attendu: str) -> None:
    codes = set(_index_categorie(dimension, nom))
    if codes != {attendu}:
        raise ValueError(
            f"dimension {nom} = {sorted(codes)} ; attendu exactement {attendu!r}"
        )


def _indice_lineaire(positions: list[int], tailles: list[int]) -> int:
    """JSON-stat : dernière dimension varie le plus vite."""
    idx = 0
    for p, t in zip(positions, tailles):
        idx = idx * t + p
    return idx


def extraire(payload: dict, unit: str) -> list[dict]:
    """JSON-stat 2.0 → observations (FR / ESA S13 / TE / 11 codes CFAP / unit).

    `value` est un dict d'index linéaires (clés str). Les années sans
    observation sont sautées, pas inventées. Refuse net toute autre
    dimension que FR / S13 / TE / freq=A / unit demandée, et tout code
    CFAP hors TOTAL+GF01–GF10.
    """
    if unit not in UNITES:
        raise ValueError(f"unité hors contrat : {unit}")
    dimension = payload.get("dimension")
    if not isinstance(dimension, dict):
        raise ValueError("JSON-stat : dimension absente")
    _verifier_dimension_unique(dimension, "geo", "FR")
    _verifier_dimension_unique(dimension, "sector", "S13")
    _verifier_dimension_unique(dimension, "na_item", NA_ITEM)
    _verifier_dimension_unique(dimension, "unit", unit)
    if "freq" in dimension:
        _verifier_dimension_unique(dimension, "freq", "A")

    cofog_index = _index_categorie(dimension, "cofog99")
    codes_vus = set(cofog_index)
    if not codes_vus <= CODES_SET:
        raise ValueError(
            f"cofog99 hors contrat : {sorted(codes_vus - CODES_SET)}"
        )
    labels_api = dimension["cofog99"].get("category", {}).get("label") or {}
    for code in codes_vus:
        attendu = LIBELLES_FR[code]
        vu = labels_api.get(code)
        if vu is not None and vu != attendu:
            raise ValueError(
                f"libellé FR {code} = {vu!r} ; attendu {attendu!r}"
            )

    ids = payload.get("id")
    sizes = payload.get("size")
    if not isinstance(ids, list) or not isinstance(sizes, list) or len(ids) != len(sizes):
        raise ValueError("JSON-stat : id/size incohérents")

    time_index = _index_categorie(dimension, "time")
    values = payload.get("value")
    if not isinstance(values, dict):
        raise ValueError("JSON-stat : value n'est pas un objet d'index linéaires")
    status = payload.get("status") or {}
    if not isinstance(status, dict):
        raise ValueError("JSON-stat : status mal formé")

    dims_uniques = {
        "geo": "FR",
        "sector": "S13",
        "na_item": NA_ITEM,
        "freq": "A",
        "unit": unit,
    }

    pos_modele: list[int | None | str] = []
    for nom in ids:
        if nom == "time":
            pos_modele.append("time")
            continue
        if nom == "cofog99":
            pos_modele.append("cofog")
            continue
        if nom in dims_uniques:
            pos_modele.append(_index_categorie(dimension, nom)[dims_uniques[nom]])
            continue
        idx = _index_categorie(dimension, nom)
        if len(idx) != 1:
            raise ValueError(f"dimension {nom} n'est pas unique : {sorted(idx)}")
        pos_modele.append(next(iter(idx.values())))

    champ_valeur = "valeur_mio_eur" if unit == "MIO_EUR" else "valeur_pc_gdp"
    observations = []
    for code, cpos in cofog_index.items():
        for annee_txt, tpos in time_index.items():
            if not ANNEE_RE.fullmatch(annee_txt):
                raise ValueError(f"année hors motif YYYY : {annee_txt!r}")
            positions = []
            for p in pos_modele:
                if p == "time":
                    positions.append(tpos)
                elif p == "cofog":
                    positions.append(cpos)
                else:
                    positions.append(p)
            cle = str(_indice_lineaire(positions, sizes))
            if cle not in values or values[cle] is None:
                continue
            try:
                val = float(values[cle])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"valeur non numérique en {code}/{annee_txt}") from exc
            if val <= 0:
                raise ValueError(
                    f"{code}/{unit} en {annee_txt} = {val} : une dépense APU n'est pas ≤ 0"
                )
            st = status.get(cle)
            if st == "":
                st = None
            observations.append({
                "geo": "FR",
                "sector": "S13",
                "cofog99": code,
                "libelle": LIBELLES_FR[code],
                "annee": int(annee_txt),
                champ_valeur: val,
                "statut": st,
            })

    if not observations:
        raise ValueError(f"aucune observation TE/FR/S13/{unit}")
    observations.sort(key=lambda o: (o["cofog99"], o["annee"]))
    return observations


def assembler(obs_mio: list[dict], obs_pc: list[dict]) -> list[dict]:
    """Jointure stricte sur (cofog99, année). Le TIME max de TOTAL doit avoir son PC_GDP."""
    pc_par = {(o["cofog99"], o["annee"]): o for o in obs_pc}
    jointes = []
    for o in obs_mio:
        if o["cofog99"] not in CODES_SET:
            raise ValueError(f"cofog99 MIO hors contrat : {o['cofog99']!r}")
        pc = pc_par.get((o["cofog99"], o["annee"]))
        if pc is None:
            continue
        statut = o["statut"] if o["statut"] is not None else pc["statut"]
        jointes.append({
            "geo": "FR",
            "sector": "S13",
            "cofog99": o["cofog99"],
            "libelle": o["libelle"],
            "annee": o["annee"],
            "valeur_mio_eur": o["valeur_mio_eur"],
            "valeur_pc_gdp": pc["valeur_pc_gdp"],
            "statut": statut,
        })
    if not jointes:
        raise ValueError("aucune année commune MIO_EUR × PC_GDP")
    totaux_mio = [o for o in obs_mio if o["cofog99"] == "TOTAL"]
    if not totaux_mio:
        raise ValueError("TOTAL absent de l'extrait MIO_EUR")
    time_max_mio = max(o["annee"] for o in totaux_mio)
    annees_total = {
        o["annee"] for o in jointes if o["cofog99"] == "TOTAL"
    }
    if time_max_mio not in annees_total:
        raise ValueError(
            f"TIME max MIO_EUR {time_max_mio} sans observation PC_GDP (TOTAL)"
        )
    jointes.sort(key=lambda o: (o["cofog99"], o["annee"]))
    return jointes


def controler_couverture(observations: list[dict]) -> None:
    """Chaque année qui a un TOTAL a les dix divisions."""
    par_annee: dict[int, set[str]] = {}
    for o in observations:
        par_annee.setdefault(o["annee"], set()).add(o["cofog99"])
    totaux = [a for a, codes in par_annee.items() if "TOTAL" in codes]
    if not totaux:
        raise ValueError("aucun TOTAL")
    for annee in totaux:
        manquants = CODES_SET - par_annee[annee]
        if manquants:
            raise ValueError(
                f"année {annee} incomplète : {sorted(manquants)}"
            )


def controler_ampleur(observations: list[dict]) -> None:
    """Garde-fous d'unité sur TOTAL, pas sur une fixture minimale."""
    totaux = [o for o in observations if o["cofog99"] == "TOTAL"]
    if len(totaux) < N_ANNEES_MIN:
        raise ValueError(
            f"TOTAL: {len(totaux)} années, {N_ANNEES_MIN} attendues au minimum"
        )
    dernier = max(totaux, key=lambda o: o["annee"])
    v = dernier["valeur_mio_eur"]
    if not (BORNE_MIN_MIO < v < BORNE_MAX_MIO):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"TOTAL {dernier['annee']} = {v} MIO_EUR "
            f"hors ]{BORNE_MIN_MIO:g}, {BORNE_MAX_MIO:g}["
        )
    pc = dernier["valeur_pc_gdp"]
    if not (BORNE_MIN_PC < pc < BORNE_MAX_PC):
        raise ValueError(
            "ordre de grandeur suspect (PC_GDP) : "
            f"TOTAL {dernier['annee']} = {pc} % PIB "
            f"hors ]{BORNE_MIN_PC:g}, {BORNE_MAX_PC:g}["
        )
    if dernier["statut"] not in (None, "p"):
        raise ValueError(
            f"statut du TIME max TOTAL {dernier['annee']!r} = "
            f"{dernier['statut']!r} (attendu None ou 'p')"
        )


def controler_additivite(observations: list[dict]) -> None:
    """Les dix divisions recomposent TOTAL, à l'arrondi près. PC_GDP non sommé."""
    par_annee: dict[int, dict[str, float]] = {}
    for o in observations:
        par_annee.setdefault(o["annee"], {})[o["cofog99"]] = o["valeur_mio_eur"]
    totaux = [a for a, d in par_annee.items() if "TOTAL" in d]
    if not totaux:
        raise ValueError("aucun TOTAL pour l'additivité")
    annee = max(totaux)
    postes = par_annee[annee]
    manquants = CODES_SET - set(postes)
    if manquants:
        raise ValueError(f"TIME max {annee} incomplet : {sorted(manquants)}")
    somme = sum(postes[c] for c in DIVISIONS)
    total = postes["TOTAL"]
    if abs(somme - total) > TOLERANCE_ADDITIVITE_MIO:
        raise ValueError(
            f"GF01–GF10 ({somme}) ≠ TOTAL ({total}) en {annee} "
            f"(tolérance {TOLERANCE_ADDITIVITE_MIO} MIO_EUR)"
        )


def ecrire_db(conn, observations: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S49. Retourne date_donnees."""
    codes = {o["cofog99"] for o in observations}
    if not CODES_SET <= codes:
        raise ValueError(f"écriture incomplète : {sorted(CODES_SET - codes)}")
    totaux = [o["annee"] for o in observations if o["cofog99"] == "TOTAL"]
    date_donnees = date_fin_annee(max(totaux))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM cofog_apu_esa")
        conn.executemany(
            """INSERT INTO cofog_apu_esa
               (geo, sector, cofog99, libelle, annee,
                valeur_mio_eur, valeur_pc_gdp, statut)
               VALUES (:geo, :sector, :cofog99, :libelle, :annee,
                       :valeur_mio_eur, :valeur_pc_gdp, :statut)""",
            observations,
        )
    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_DOI,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(observations),
        notes=NOTES,
    )
    return date_donnees


def main() -> int:
    try:
        payloads: dict[str, dict] = {}
        for unit in UNITES:
            chemin = telecharger(
                url_api(unit),
                FICHIERS_RAW[unit],
                max_age_heures=CACHE_HEURES,
            )
            payloads[unit] = json.loads(Path(chemin).read_text(encoding="utf-8"))
        obs_mio = extraire(payloads["MIO_EUR"], "MIO_EUR")
        obs_pc = extraire(payloads["PC_GDP"], "PC_GDP")
        observations = assembler(obs_mio, obs_pc)
        controler_couverture(observations)
        controler_ampleur(observations)
        controler_additivite(observations)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, observations)
        conn.close()
        time_max = max(
            o["annee"] for o in observations if o["cofog99"] == "TOTAL"
        )
        log.info(
            "cofog_apu_esa: %d observations, données au %s (TIME max TOTAL %s)",
            len(observations),
            date_donnees,
            time_max,
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S49 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
