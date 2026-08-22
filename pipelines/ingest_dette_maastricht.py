"""P17 — Encours de dette des APU au sens de Maastricht (S41, Eurostat).

Source : JSON-stat `gov_10q_ggdebt`, extrait figé
geo=FR × sector=S13 × na_item=GD × unit=MIO_EUR.
DOI : https://doi.org/10.2908/GOV_10Q_GGDEBT
Licence : décision 2011/833/UE (réutilisation des données statistiques
Eurostat) — pas CC BY 4.0. La France est un État membre : l'exception
« pays tiers, réutilisation commerciale » ne s'applique pas.

CE PIPELINE N'EST PAS LA SOURCE S13
-----------------------------------
Le secteur ESA **S13** = administrations publiques (État, Odac, APUL, ASSO).
La source France Transparence **S13** = situations mensuelles budgétaires
DGFiP (flux de l'État). `source_id` ici = **S41**, jamais `'S13'`.
L'objet n'est pas non plus la ligne DGFiP « Charges de la dette de l'État »
(intérêts, cumul YTD du budget général).

N'ingère que `na_item=GD` (dette brute consolidée, valeur faciale). Pas de
déficit, pas de `B9`, pas de `PC_GDP`, pas de sous-secteur S.1311 seul.

Table créée :
- dette_apu_maastricht : une ligne par trimestre, unité native MIO_EUR.
  Conversion Md€ = MIO_EUR ÷ 1000 À LA LECTURE, jamais ÷ 1e9 (unité S13).

`date_donnees` = dernier jour du TIME max (2026-Q1 → 2026-03-31), jamais
le champ JSON-stat `updated` (date de diffusion).

Exécution : python -m pipelines.ingest_dette_maastricht
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente (DELETE puis
INSERT dans une transaction), puis upsert_meta('S41', …). Échec → exit ≠ 0,
base intacte.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("dette_maastricht")

SOURCE_ID = "S41"
NOM_SOURCE = (
    "Encours de dette des APU au sens de Maastricht (Eurostat gov_10q_ggdebt)"
)
URL_API = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "gov_10q_ggdebt?format=JSON&geo=FR&unit=MIO_EUR&sector=S13&na_item=GD&lang=EN"
)
URL_DOI = "https://doi.org/10.2908/GOV_10Q_GGDEBT"
LICENCE = "Décision 2011/833/UE (réutilisation des données statistiques Eurostat)"
FREQUENCE = "trimestrielle"
FICHIER_RAW = "eurostat/gov_10q_ggdebt.json"
CACHE_HEURES = 7 * 24

# ESA S13 = APU. Pas la source FT S13.
DIMS_ATTENDUES = {
    "geo": "FR",
    "sector": "S13",
    "na_item": "GD",
    "unit": "MIO_EUR",
}

TRIMESTRE_RE = re.compile(r"^\d{4}-Q[1-4]$")
_FIN_TRIMESTRE = {1: "-03-31", 2: "-06-30", 3: "-09-30", 4: "-12-31"}

# Bornes d'unité, pas la valeur du jour : un encours APU FR tient en
# millions d'euros entre 10³ et 8×10³ Md€.
BORNE_MIN_MIO = 1e6  # exclusive
BORNE_MAX_MIO = 8e6  # exclusive
N_VALUES_MIN = 80

NOTES = (
    "stock consolidé brut, valeur faciale, fin de trimestre ; "
    "ESA S13 = APU, distinct de la source S13 (SMB DGFiP, flux de l'État) ; "
    "na_item=GD uniquement, jamais un déficit ; "
    "distinct des charges d'intérêts DGFiP ; "
    "Md€ = MIO_EUR÷1000 (jamais ÷1e9) ; "
    "le TIME max peut porter le statut p (provisoire) ; "
    "DOI 10.2908/GOV_10Q_GGDEBT"
)

_DDL = """
CREATE TABLE IF NOT EXISTS dette_apu_maastricht (
    geo            TEXT NOT NULL CHECK (geo = 'FR'),
    sector         TEXT NOT NULL CHECK (sector = 'S13'), -- ESA APU, pas la source S13
    na_item        TEXT NOT NULL CHECK (na_item = 'GD'), -- jamais un déficit
    unit           TEXT NOT NULL CHECK (unit = 'MIO_EUR'),
    trimestre      TEXT NOT NULL,
    valeur_mio_eur REAL NOT NULL CHECK (valeur_mio_eur > 0),
    statut         TEXT,
    PRIMARY KEY (geo, sector, na_item, unit, trimestre)
);
"""


def mio_en_md(mio: float) -> float:
    """MIO_EUR → Md€. Un million d'euros = 0,001 milliard. Jamais ÷ 1e9."""
    return mio / 1000.0


def date_fin_trimestre(trimestre: str) -> str:
    """Dernier jour du trimestre ISO : 2026-Q1 → 2026-03-31."""
    if not TRIMESTRE_RE.fullmatch(trimestre):
        raise ValueError(f"trimestre hors motif YYYY-Qn : {trimestre!r}")
    annee, q = trimestre.split("-Q")
    return f"{annee}{_FIN_TRIMESTRE[int(q)]}"


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


def extraire(payload: dict) -> list[dict]:
    """JSON-stat 2.0 → observations (FR / ESA S13 / GD / MIO_EUR).

    `value` est un dict d'index linéaires (clés str). Les trimestres sans
    observation (trous 1994-1999 côté Eurostat) sont sautés, pas inventés.
    Refuse net toute autre dimension que FR / S13 / GD / MIO_EUR.
    """
    dimension = payload.get("dimension")
    if not isinstance(dimension, dict):
        raise ValueError("JSON-stat : dimension absente")
    _verifier_dimension_unique(dimension, "geo", "FR")
    _verifier_dimension_unique(dimension, "sector", "S13")
    _verifier_dimension_unique(dimension, "na_item", "GD")
    _verifier_dimension_unique(dimension, "unit", "MIO_EUR")

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

    pos_fixe: list[int | None] = []
    for nom in ids:
        if nom == "time":
            pos_fixe.append(None)
            continue
        if nom in DIMS_ATTENDUES:
            pos_fixe.append(_index_categorie(dimension, nom)[DIMS_ATTENDUES[nom]])
            continue
        idx = _index_categorie(dimension, nom)
        if len(idx) != 1:
            raise ValueError(f"dimension {nom} n'est pas unique : {sorted(idx)}")
        pos_fixe.append(next(iter(idx.values())))

    observations = []
    for code, tpos in time_index.items():
        if not TRIMESTRE_RE.fullmatch(code):
            raise ValueError(f"trimestre hors motif YYYY-Qn : {code!r}")
        positions = [tpos if p is None else p for p in pos_fixe]
        cle = str(_indice_lineaire(positions, sizes))
        if cle not in values or values[cle] is None:
            continue
        try:
            mio = float(values[cle])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"valeur non numérique au {code}") from exc
        if mio <= 0:
            raise ValueError(f"valeur_mio_eur ≤ 0 au {code}")
        st = status.get(cle)
        if st == "":
            st = None
        observations.append({
            "geo": "FR",
            "sector": "S13",
            "na_item": "GD",
            "unit": "MIO_EUR",
            "trimestre": code,
            "valeur_mio_eur": mio,
            "statut": st,
        })

    if not observations:
        raise ValueError("aucune observation GD/FR/S13/MIO_EUR")
    observations.sort(key=lambda o: o["trimestre"])
    return observations


def controler_ampleur(observations: list[dict]) -> None:
    """Garde-fous d'unité sur une série réelle, pas sur une fixture minimale."""
    if len(observations) < N_VALUES_MIN:
        raise ValueError(
            f"{len(observations)} observations, {N_VALUES_MIN} attendues au minimum"
        )
    dernier = max(observations, key=lambda o: o["trimestre"])
    v = dernier["valeur_mio_eur"]
    if not (BORNE_MIN_MIO < v < BORNE_MAX_MIO):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"{dernier['trimestre']} = {v} MIO_EUR "
            f"hors ]{BORNE_MIN_MIO:g}, {BORNE_MAX_MIO:g}["
        )
    if dernier["statut"] not in (None, "p"):
        raise ValueError(
            f"statut du TIME max {dernier['trimestre']!r} = {dernier['statut']!r} "
            "(attendu None ou 'p')"
        )


def ecrire_db(conn, observations: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S41. Retourne date_donnees."""
    date_donnees = date_fin_trimestre(max(o["trimestre"] for o in observations))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM dette_apu_maastricht")
        conn.executemany(
            """INSERT INTO dette_apu_maastricht
               (geo, sector, na_item, unit, trimestre, valeur_mio_eur, statut)
               VALUES (:geo, :sector, :na_item, :unit, :trimestre,
                       :valeur_mio_eur, :statut)""",
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
        chemin = telecharger(URL_API, FICHIER_RAW, max_age_heures=CACHE_HEURES)
        payload = json.loads(Path(chemin).read_text(encoding="utf-8"))
        observations = extraire(payload)
        controler_ampleur(observations)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, observations)
        conn.close()
        log.info(
            "dette_apu_maastricht: %d observations, données au %s (TIME max %s)",
            len(observations),
            date_donnees,
            max(o["trimestre"] for o in observations),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S41 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
