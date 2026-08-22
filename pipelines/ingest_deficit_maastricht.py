"""P18 — Déficit public des APU au sens de Maastricht (S42, Eurostat).

Source : JSON-stat `gov_10dd_edpt1`, deux extraits figés
geo=FR × sector=S13 × na_item=B9 × unit=MIO_EUR
et le même filtre en unit=PC_GDP.
DOI : https://doi.org/10.2908/GOV_10DD_EDPT1
Licence : décision 2011/833/UE (réutilisation des données statistiques
Eurostat) — pas CC BY 4.0. La France est un État membre : l'exception
« pays tiers, réutilisation commerciale » ne s'applique pas.

CE PIPELINE N'EST PAS LA SOURCE S13, NI S41
-------------------------------------------
Le secteur ESA **S13** = administrations publiques (État, Odac, APUL, ASSO).
La source France Transparence **S13** = situations mensuelles budgétaires
DGFiP (flux de l'État, solde du budget général).
La source **S41** = encours (stock, na_item=GD, trimestriel).
`source_id` ici = **S42**, jamais `'S13'` ni `'S41'`.

N'ingère que `na_item=B9` (capacité (+)/besoin (−) de financement).
Pas de `GD`, pas de sous-secteur S.1311, pas de série trimestrielle
(`gov_10q_ggnfa`), pas de montant par habitant, pas de comparaison au
seuil de 3 % du PIB.

`B9` est signé : négatif = besoin de financement (déficit), positif =
capacité (excédent). La conversion Md€ = MIO_EUR ÷ 1000 se fait À LA
LECTURE, jamais ÷ 1e9 (unité S13).

`date_donnees` = 31 décembre du TIME max (2025 → 2025-12-31), jamais
le champ JSON-stat `updated` (date de diffusion, notification EDP d'avril).

Exécution : python -m pipelines.ingest_deficit_maastricht
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente (DELETE puis
INSERT dans une transaction), puis upsert_meta('S42', …). Échec → exit ≠ 0,
base intacte.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("deficit_maastricht")

SOURCE_ID = "S42"
NOM_SOURCE = (
    "Déficit public des APU au sens de Maastricht "
    "(Eurostat gov_10dd_edpt1, B9)"
)
URL_API_MIO = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "gov_10dd_edpt1?format=JSON&geo=FR&unit=MIO_EUR&sector=S13"
    "&na_item=B9&lang=EN"
)
URL_API_PC = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "gov_10dd_edpt1?format=JSON&geo=FR&unit=PC_GDP&sector=S13"
    "&na_item=B9&lang=EN"
)
URL_DOI = "https://doi.org/10.2908/GOV_10DD_EDPT1"
LICENCE = "Décision 2011/833/UE (réutilisation des données statistiques Eurostat)"
FREQUENCE = "annuelle"
FICHIER_RAW_MIO = "eurostat/gov_10dd_edpt1_mio.json"
FICHIER_RAW_PC = "eurostat/gov_10dd_edpt1_pc.json"
CACHE_HEURES = 7 * 24

DIMS_COMMUNES = {
    "geo": "FR",
    "sector": "S13",
    "na_item": "B9",
    "freq": "A",
}

ANNEE_RE = re.compile(r"^\d{4}$")

# Bornes d'unité sur |B9| en millions d'euros, pas la valeur du jour :
# un besoin de financement APU FR tient entre quelques Md€ et quelques
# centaines de Md€. |PC_GDP| tient sous 20 points hors guerre/crise.
BORNE_MIN_ABS_MIO = 5e3  # exclusive
BORNE_MAX_ABS_MIO = 5e5  # exclusive
BORNE_MAX_ABS_PC = 20.0  # exclusive
N_VALUES_MIN = 25

NOTES = (
    "flux annuel, na_item=B9 (net lending + / net borrowing −) ; "
    "ESA S13 = APU, distinct de la source S13 (SMB DGFiP, solde de l'État) "
    "et de S41 (stock GD trimestriel) ; "
    "Md€ = MIO_EUR÷1000 (jamais ÷1e9) ; "
    "PC_GDP lu à part, jamais comparé au seuil de 3 % ; "
    "pas de série trimestrielle, pas de S.1311, pas de par habitant ; "
    "date_donnees = 31/12 du TIME max, jamais JSON-stat updated ; "
    "DOI 10.2908/GOV_10DD_EDPT1"
)

_DDL = """
CREATE TABLE IF NOT EXISTS deficit_apu_maastricht (
    geo            TEXT NOT NULL CHECK (geo = 'FR'),
    sector         TEXT NOT NULL CHECK (sector = 'S13'), -- ESA APU, pas la source S13
    na_item        TEXT NOT NULL CHECK (na_item = 'B9'), -- jamais GD (stock S41)
    annee          INTEGER NOT NULL,
    valeur_mio_eur REAL NOT NULL, -- signé : − = besoin de financement
    valeur_pc_gdp  REAL NOT NULL, -- signé, % du PIB ; jamais un écart à 3 %
    statut         TEXT,
    PRIMARY KEY (geo, sector, na_item, annee)
);
"""


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


def extraire(payload: dict, unit: str) -> list[dict]:
    """JSON-stat 2.0 → observations (FR / ESA S13 / B9 / unit demandée).

    `value` est un dict d'index linéaires (clés str). Les années sans
    observation sont sautées, pas inventées. Refuse net toute autre
    dimension que FR / S13 / B9 / freq=A / unit.
    """
    dimension = payload.get("dimension")
    if not isinstance(dimension, dict):
        raise ValueError("JSON-stat : dimension absente")
    _verifier_dimension_unique(dimension, "geo", "FR")
    _verifier_dimension_unique(dimension, "sector", "S13")
    _verifier_dimension_unique(dimension, "na_item", "B9")
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

    dims_attendues = dict(DIMS_COMMUNES)
    dims_attendues["unit"] = unit

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
        st = status.get(cle)
        if st == "":
            st = None
        observations.append({
            "geo": "FR",
            "sector": "S13",
            "na_item": "B9",
            "annee": int(code),
            champ_valeur: val,
            "statut": st,
        })

    if not observations:
        raise ValueError(f"aucune observation B9/FR/S13/{unit}")
    observations.sort(key=lambda o: o["annee"])
    return observations


def assembler(obs_mio: list[dict], obs_pc: list[dict]) -> list[dict]:
    """Jointure stricte sur l'année : le TIME max MIO_EUR doit avoir son PC_GDP."""
    pc_par_annee = {o["annee"]: o for o in obs_pc}
    jointes = []
    for o in obs_mio:
        pc = pc_par_annee.get(o["annee"])
        if pc is None:
            continue
        statut = o["statut"] if o["statut"] is not None else pc["statut"]
        jointes.append({
            "geo": "FR",
            "sector": "S13",
            "na_item": "B9",
            "annee": o["annee"],
            "valeur_mio_eur": o["valeur_mio_eur"],
            "valeur_pc_gdp": pc["valeur_pc_gdp"],
            "statut": statut,
        })
    if not jointes:
        raise ValueError("aucune année commune MIO_EUR × PC_GDP")
    time_max_mio = max(o["annee"] for o in obs_mio)
    annees_jointes = {o["annee"] for o in jointes}
    if time_max_mio not in annees_jointes:
        raise ValueError(
            f"TIME max MIO_EUR {time_max_mio} sans observation PC_GDP"
        )
    jointes.sort(key=lambda o: o["annee"])
    return jointes


def controler_ampleur(observations: list[dict]) -> None:
    """Garde-fous d'unité sur une série réelle, pas sur une fixture minimale."""
    if len(observations) < N_VALUES_MIN:
        raise ValueError(
            f"{len(observations)} observations, {N_VALUES_MIN} attendues au minimum"
        )
    dernier = max(observations, key=lambda o: o["annee"])
    v = abs(dernier["valeur_mio_eur"])
    if not (BORNE_MIN_ABS_MIO < v < BORNE_MAX_ABS_MIO):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"{dernier['annee']} |B9| = {v} MIO_EUR "
            f"hors ]{BORNE_MIN_ABS_MIO:g}, {BORNE_MAX_ABS_MIO:g}["
        )
    pc = abs(dernier["valeur_pc_gdp"])
    if not (0 < pc < BORNE_MAX_ABS_PC):
        raise ValueError(
            "ordre de grandeur suspect (PC_GDP) : "
            f"{dernier['annee']} |B9| = {pc} % PIB "
            f"hors ]0, {BORNE_MAX_ABS_PC:g}["
        )
    if dernier["statut"] not in (None, "p"):
        raise ValueError(
            f"statut du TIME max {dernier['annee']!r} = {dernier['statut']!r} "
            "(attendu None ou 'p')"
        )


def ecrire_db(conn, observations: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S42. Retourne date_donnees."""
    date_donnees = date_fin_annee(max(o["annee"] for o in observations))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM deficit_apu_maastricht")
        conn.executemany(
            """INSERT INTO deficit_apu_maastricht
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
        chemin_mio = telecharger(URL_API_MIO, FICHIER_RAW_MIO, max_age_heures=CACHE_HEURES)
        chemin_pc = telecharger(URL_API_PC, FICHIER_RAW_PC, max_age_heures=CACHE_HEURES)
        payload_mio = json.loads(Path(chemin_mio).read_text(encoding="utf-8"))
        payload_pc = json.loads(Path(chemin_pc).read_text(encoding="utf-8"))
        obs_mio = extraire(payload_mio, "MIO_EUR")
        obs_pc = extraire(payload_pc, "PC_GDP")
        observations = assembler(obs_mio, obs_pc)
        controler_ampleur(observations)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, observations)
        conn.close()
        log.info(
            "deficit_apu_maastricht: %d observations, données au %s (TIME max %s)",
            len(observations),
            date_donnees,
            max(o["annee"] for o in observations),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S42 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
