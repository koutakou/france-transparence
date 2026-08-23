"""P20 — Recettes et dépenses des APU (agrégats ESA, S44, Eurostat).

Source : JSON-stat `gov_10a_main`, quatre extraits figés
geo=FR × sector=S13 × na_item=TE|TR × unit=MIO_EUR
et les mêmes filtres en unit=PC_GDP.
DOI : https://doi.org/10.2908/GOV_10A_MAIN
Licence : décision 2011/833/UE (réutilisation des données statistiques
Eurostat) — pas CC BY 4.0. La France est un État membre : l'exception
« pays tiers, réutilisation commerciale » ne s'applique pas.

CE PIPELINE N'EST PAS LA SOURCE S13, NI S41, NI S42
---------------------------------------------------
Le secteur ESA **S13** = administrations publiques (État, Odac, APUL, ASSO).
La source France Transparence **S13** = situations mensuelles budgétaires
DGFiP (flux de l'État, budget général, cumul depuis le 1er janvier).
La source **S41** = encours (stock, na_item=GD, trimestriel, Maastricht).
La source **S42** = besoin/capacité de financement (flux, na_item=B9,
Maastricht). `source_id` ici = **S44**, jamais `'S13'` ni `'S41'` ni `'S42'`.

N'ingère que `na_item=TE` (total des dépenses) et `na_item=TR` (total des
recettes). Pas de `B9` (S42 le publie, on ne le recalcule pas), pas de
`GD`, pas de `D41PAY`, pas de COFOG (`gov_10a_exp`), pas de taxag, pas de
sous-secteur S.1311, pas de montant par habitant.

TE et TR sont positifs (flux bruts). La conversion Md€ = MIO_EUR ÷ 1000
se fait À LA LECTURE, jamais ÷ 1e9 (unité S13).

`date_donnees` = 31 décembre du TIME max commun à TE et TR
(2025 → 2025-12-31), jamais le champ JSON-stat `updated` (date de
diffusion GFS).

Exécution : python -m pipelines.ingest_agregats_apu
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente (DELETE puis
INSERT dans une transaction), puis upsert_meta('S44', …). Échec → exit ≠ 0,
base intacte.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("agregats_apu")

SOURCE_ID = "S44"
NOM_SOURCE = (
    "Recettes et dépenses des APU "
    "(Eurostat gov_10a_main, TE et TR)"
)
URL_DOI = "https://doi.org/10.2908/GOV_10A_MAIN"
LICENCE = "Décision 2011/833/UE (réutilisation des données statistiques Eurostat)"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24

NA_ITEMS = ("TE", "TR")
UNITES = ("MIO_EUR", "PC_GDP")

FICHIERS_RAW = {
    ("TE", "MIO_EUR"): "eurostat/gov_10a_main_te_mio.json",
    ("TE", "PC_GDP"): "eurostat/gov_10a_main_te_pc.json",
    ("TR", "MIO_EUR"): "eurostat/gov_10a_main_tr_mio.json",
    ("TR", "PC_GDP"): "eurostat/gov_10a_main_tr_pc.json",
}

ANNEE_RE = re.compile(r"^\d{4}$")

# Bornes d'unité sur le TIME max, pas la fixture. Un total APU FR tient
# entre quelques centaines de Md€ et quelques milliers.
BORNE_MIN_MIO = 2e5  # exclusive — 200 Md€
BORNE_MAX_MIO = 4e6  # exclusive — 4 000 Md€
BORNE_MIN_PC = 30.0  # exclusive
BORNE_MAX_PC = 80.0  # exclusive
N_VALUES_MIN = 25  # par na_item

NOTES = (
    "flux annuel, na_item=TE (dépenses) et TR (recettes) ; "
    "ESA S13 = APU, distinct de la source S13 (SMB DGFiP, budget de l'État), "
    "de S41 (stock GD trimestriel, Maastricht) et de S42 (B9, Maastricht) ; "
    "pas un indicateur Maastricht ; "
    "Md€ = MIO_EUR÷1000 (jamais ÷1e9) ; "
    "PC_GDP lu à part ; B9 non recalculé (TR−TE) ; "
    "pas de COFOG, pas de taxag, pas de D41PAY, pas de S.1311, pas de par habitant ; "
    "date_donnees = 31/12 du TIME max commun, jamais JSON-stat updated ; "
    "DOI 10.2908/GOV_10A_MAIN"
)

_DDL = """
CREATE TABLE IF NOT EXISTS agregats_apu_esa (
    geo            TEXT NOT NULL CHECK (geo = 'FR'),
    sector         TEXT NOT NULL CHECK (sector = 'S13'), -- ESA APU, pas la source S13
    na_item        TEXT NOT NULL CHECK (na_item IN ('TE', 'TR')), -- jamais B9 ni GD
    annee          INTEGER NOT NULL,
    valeur_mio_eur REAL NOT NULL CHECK (valeur_mio_eur > 0),
    valeur_pc_gdp  REAL NOT NULL CHECK (valeur_pc_gdp > 0),
    statut         TEXT,
    PRIMARY KEY (geo, sector, na_item, annee)
);
"""


def url_api(na_item: str, unit: str) -> str:
    if na_item not in NA_ITEMS or unit not in UNITES:
        raise ValueError(f"extrait hors contrat : {na_item}/{unit}")
    return (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
        f"gov_10a_main?format=JSON&geo=FR&unit={unit}&sector=S13"
        f"&na_item={na_item}&lang=EN"
    )


def mio_en_md(mio: float) -> float:
    """MIO_EUR → Md€. Un million d'euros = 0,001 milliard. Jamais ÷ 1e9."""
    return mio / 1000.0


def date_fin_annee(annee: int) -> str:
    """31 décembre de l'année TIME : 2025 → 2025-12-31."""
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


def extraire(payload: dict, na_item: str, unit: str) -> list[dict]:
    """JSON-stat 2.0 → observations (FR / ESA S13 / na_item / unit).

    `value` est un dict d'index linéaires (clés str). Les années sans
    observation sont sautées, pas inventées. Refuse net toute autre
    dimension que FR / S13 / TE|TR / freq=A / unit demandée.
    """
    if na_item not in NA_ITEMS:
        raise ValueError(f"na_item hors contrat : {na_item!r}")
    dimension = payload.get("dimension")
    if not isinstance(dimension, dict):
        raise ValueError("JSON-stat : dimension absente")
    _verifier_dimension_unique(dimension, "geo", "FR")
    _verifier_dimension_unique(dimension, "sector", "S13")
    _verifier_dimension_unique(dimension, "na_item", na_item)
    _verifier_dimension_unique(dimension, "unit", unit)
    if "freq" in dimension:
        _verifier_dimension_unique(dimension, "freq", "A")

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

    dims_attendues = {
        "geo": "FR",
        "sector": "S13",
        "na_item": na_item,
        "freq": "A",
        "unit": unit,
    }

    pos_fixe: list[int | None] = []
    for nom in ids:
        if nom == "time":
            pos_fixe.append(None)
            continue
        if nom in dims_attendues:
            pos_fixe.append(_index_categorie(dimension, nom)[dims_attendues[nom]])
            continue
        idx = _index_categorie(dimension, nom)
        if len(idx) != 1:
            raise ValueError(f"dimension {nom} n'est pas unique : {sorted(idx)}")
        pos_fixe.append(next(iter(idx.values())))

    champ_valeur = "valeur_mio_eur" if unit == "MIO_EUR" else "valeur_pc_gdp"
    observations = []
    for code, tpos in time_index.items():
        if not ANNEE_RE.fullmatch(code):
            raise ValueError(f"année hors motif YYYY : {code!r}")
        positions = [tpos if p is None else p for p in pos_fixe]
        cle = str(_indice_lineaire(positions, sizes))
        if cle not in values or values[cle] is None:
            continue
        try:
            val = float(values[cle])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"valeur non numérique en {code}") from exc
        if val <= 0:
            raise ValueError(
                f"{na_item}/{unit} en {code} = {val} : un total APU n'est pas ≤ 0"
            )
        st = status.get(cle)
        if st == "":
            st = None
        observations.append({
            "geo": "FR",
            "sector": "S13",
            "na_item": na_item,
            "annee": int(code),
            champ_valeur: val,
            "statut": st,
        })

    if not observations:
        raise ValueError(f"aucune observation {na_item}/FR/S13/{unit}")
    observations.sort(key=lambda o: o["annee"])
    return observations


def assembler(obs_mio: list[dict], obs_pc: list[dict], na_item: str) -> list[dict]:
    """Jointure stricte sur l'année : le TIME max MIO_EUR doit avoir son PC_GDP."""
    if na_item not in NA_ITEMS:
        raise ValueError(f"na_item hors contrat : {na_item!r}")
    pc_par_annee = {o["annee"]: o for o in obs_pc}
    jointes = []
    for o in obs_mio:
        if o["na_item"] != na_item:
            raise ValueError(f"na_item MIO {o['na_item']!r} ≠ {na_item!r}")
        pc = pc_par_annee.get(o["annee"])
        if pc is None:
            continue
        if pc["na_item"] != na_item:
            raise ValueError(f"na_item PC {pc['na_item']!r} ≠ {na_item!r}")
        statut = o["statut"] if o["statut"] is not None else pc["statut"]
        jointes.append({
            "geo": "FR",
            "sector": "S13",
            "na_item": na_item,
            "annee": o["annee"],
            "valeur_mio_eur": o["valeur_mio_eur"],
            "valeur_pc_gdp": pc["valeur_pc_gdp"],
            "statut": statut,
        })
    if not jointes:
        raise ValueError(f"aucune année commune MIO_EUR × PC_GDP pour {na_item}")
    time_max_mio = max(o["annee"] for o in obs_mio)
    annees_jointes = {o["annee"] for o in jointes}
    if time_max_mio not in annees_jointes:
        raise ValueError(
            f"TIME max MIO_EUR {time_max_mio} sans observation PC_GDP ({na_item})"
        )
    jointes.sort(key=lambda o: o["annee"])
    return jointes


def fusionner(par_item: dict[str, list[dict]]) -> list[dict]:
    """Concatène TE et TR. Le TIME max doit être le même des deux côtés."""
    if set(par_item) != set(NA_ITEMS):
        raise ValueError(f"items = {sorted(par_item)} ; attendu TE et TR")
    time_max = {item: max(o["annee"] for o in obs) for item, obs in par_item.items()}
    if time_max["TE"] != time_max["TR"]:
        raise ValueError(
            f"TIME max TE={time_max['TE']} ≠ TR={time_max['TR']}"
        )
    fusionnees: list[dict] = []
    for item in NA_ITEMS:
        fusionnees.extend(par_item[item])
    fusionnees.sort(key=lambda o: (o["na_item"], o["annee"]))
    return fusionnees


def controler_ampleur(observations: list[dict]) -> None:
    """Garde-fous d'unité sur une série réelle, pas sur une fixture minimale."""
    par_item: dict[str, list[dict]] = {item: [] for item in NA_ITEMS}
    for o in observations:
        if o["na_item"] not in par_item:
            raise ValueError(f"na_item hors contrat : {o['na_item']!r}")
        par_item[o["na_item"]].append(o)
    for item in NA_ITEMS:
        serie = par_item[item]
        if len(serie) < N_VALUES_MIN:
            raise ValueError(
                f"{item}: {len(serie)} observations, {N_VALUES_MIN} attendues au minimum"
            )
        dernier = max(serie, key=lambda o: o["annee"])
        v = dernier["valeur_mio_eur"]
        if not (BORNE_MIN_MIO < v < BORNE_MAX_MIO):
            raise ValueError(
                "ordre de grandeur suspect (erreur d'unité ?) : "
                f"{item} {dernier['annee']} = {v} MIO_EUR "
                f"hors ]{BORNE_MIN_MIO:g}, {BORNE_MAX_MIO:g}["
            )
        pc = dernier["valeur_pc_gdp"]
        if not (BORNE_MIN_PC < pc < BORNE_MAX_PC):
            raise ValueError(
                "ordre de grandeur suspect (PC_GDP) : "
                f"{item} {dernier['annee']} = {pc} % PIB "
                f"hors ]{BORNE_MIN_PC:g}, {BORNE_MAX_PC:g}["
            )
        if dernier["statut"] not in (None, "p"):
            raise ValueError(
                f"statut du TIME max {item} {dernier['annee']!r} = "
                f"{dernier['statut']!r} (attendu None ou 'p')"
            )


def ecrire_db(conn, observations: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S44. Retourne date_donnees."""
    items = {o["na_item"] for o in observations}
    if items != set(NA_ITEMS):
        raise ValueError(f"écriture incomplète : {sorted(items)}")
    date_donnees = date_fin_annee(max(o["annee"] for o in observations))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM agregats_apu_esa")
        conn.executemany(
            """INSERT INTO agregats_apu_esa
               (geo, sector, na_item, annee, valeur_mio_eur, valeur_pc_gdp, statut)
               VALUES (:geo, :sector, :na_item, :annee,
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
        par_item: dict[str, list[dict]] = {}
        for na_item in NA_ITEMS:
            payloads: dict[str, dict] = {}
            for unit in UNITES:
                chemin = telecharger(
                    url_api(na_item, unit),
                    FICHIERS_RAW[(na_item, unit)],
                    max_age_heures=CACHE_HEURES,
                )
                payloads[unit] = json.loads(Path(chemin).read_text(encoding="utf-8"))
            obs_mio = extraire(payloads["MIO_EUR"], na_item, "MIO_EUR")
            obs_pc = extraire(payloads["PC_GDP"], na_item, "PC_GDP")
            par_item[na_item] = assembler(obs_mio, obs_pc, na_item)
        observations = fusionner(par_item)
        controler_ampleur(observations)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, observations)
        conn.close()
        log.info(
            "agregats_apu_esa: %d observations, données au %s (TIME max %s)",
            len(observations),
            date_donnees,
            max(o["annee"] for o in observations),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S44 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
