"""P22 — Prestations de protection sociale (S45, DREES).

Source : jeu ODS `305_les-comptes-de-la-protection-sociale`
(DREES / ministère des Solidarités et de la Santé), export JSON
`/exports/json` — pas le plafond `/records` (offset+limit ≤ 10 000).
Licence : Licence Ouverte 2.0 (Etalab), relue le 23/08/2026 sur
https://www.data.gouv.fr/pages/legal/licences/etalab-2.0 (HTTP 200)
et sur la fiche data.gouv (« Licence Ouverte / Open Licence version 2.0 »).
Le PDF historique etalab.gouv.fr/wp-content/uploads/2017/04/… redirige
désormais vers la page d'accueil data.gouv : ce n'est plus la page de
licence.

CE PIPELINE N'EST PAS LA LFSS, NI S13, NI S44, NI ESSPROS
--------------------------------------------------------
Le compte DREES couvre TOUS les régimes (État, Odac, APUL, régime
général, autres assurances sociales, organismes d'assurance, fonds de
pension, ISBLSM, employeurs). Ce n'est PAS la loi de financement de
la sécurité sociale, PAS le budget général (S13), PAS le total des
dépenses des APU (S44, TE). `source_id` = **S45**, jamais `'S13'` ni
`'S44'`. Le régime général (si_code S13141) n'est pas « la Sécu » à
lui seul : S13142 existe à côté.

N'ingère QUE les tranches exclusives, pour ne pas double-compter
l'arbre (niveaux 2 et 3 recouvrent les niveaux 0 et 1) :

  · grain `total`  : si_niveau=0, si_code=S1, ps_niveau=0, ps_code=E11-0
  · grain `risque` : si_code=S1, ps_niveau=1 (six codes E11-1 … E11-6)
  · grain `regime` : si_niveau=1, ps_code=E11-0

Invariant : pour chaque année qui porte un total, la somme des risques
(si elle est retenue) et la somme des régimes (si elle est retenue)
recomposent le total. Le TIME max DOIT porter les trois grains, avec
S13141 présent. Pas de % du PIB (pas dans ce jeu), pas de par habitant,
pas de recettes, pas de frais de gestion.

Unité native : million d'euros (`val`). Md€ = val ÷ 1000 à la lecture,
jamais ÷ 1e9. `date_donnees` = 31 décembre de l'année max, jamais
`last_update` data.gouv (18/12/2025) ni `modified` du catalogue.

Exécution : python -m pipelines.ingest_protection_sociale
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente (DELETE
puis INSERT dans une transaction), puis upsert_meta('S45', …). Échec →
exit ≠ 0, base intacte.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("protection_sociale")

SOURCE_ID = "S45"
NOM_SOURCE = (
    "Prestations de protection sociale "
    "(DREES, comptes de la protection sociale)"
)
URL_DATASET = (
    "https://www.data.gouv.fr/datasets/les-comptes-de-la-protection-sociale"
)
URL_EXPORT = (
    "https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1"
    "/catalog/datasets/305_les-comptes-de-la-protection-sociale/exports/json"
)
LICENCE = "Licence Ouverte 2.0 (Etalab)"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24
FICHIER_RAW = "drees/305_les-comptes-de-la-protection-sociale.json"

CODES_RISQUE = ("E11-1", "E11-2", "E11-3", "E11-4", "E11-5", "E11-6")
CODE_TOTAL_PS = "E11-0"
CODE_TOTAL_SI = "S1"
CODE_REGIME_GENERAL = "S13141"

# Recouvrement flottant : val est en millions à deux décimales.
TOLERANCE_MIO = 0.05

# Garde-fous d'unité sur le TIME max, pas la fixture.
BORNE_MIN_MIO = 2e5  # exclusive — 200 Md€
BORNE_MAX_MIO = 2e6  # exclusive — 2 000 Md€
N_TOTALS_MIN = 20

NOTES = (
    "flux annuel des PRESTATIONS (E11), pas les recettes, pas les frais "
    "de gestion ; tous régimes (si_code S1), distinct du budget de l'État "
    "(S13) et des dépenses APU ESA (S44, TE) ; le régime général S13141 "
    "n'est pas l'ensemble de la sécurité sociale (S13142 existe) ; "
    "tranches exclusives seulement (si_niveau 0/1, ps_niveau 0/1) — "
    "les niveaux 2-3 recouvrent et ne sont pas ingérés ; "
    "Md€ = million d'euros ÷ 1000 (jamais ÷ 1e9) ; "
    "pas de % du PIB, pas de par habitant, pas de LFSS ; "
    "date_donnees = 31/12 de l'année max, jamais last_update data.gouv"
)

_DDL = """
CREATE TABLE IF NOT EXISTS protection_sociale_prestations (
    annee          INTEGER NOT NULL,
    grain          TEXT NOT NULL CHECK (grain IN ('total', 'risque', 'regime')),
    code           TEXT NOT NULL,
    libelle        TEXT NOT NULL,
    val_mio_eur    REAL NOT NULL CHECK (val_mio_eur > 0),
    PRIMARY KEY (annee, grain, code)
);
"""


def date_fin_annee(annee: int) -> str:
    """31 décembre de l'année : 2024 → 2024-12-31."""
    if not isinstance(annee, int) or annee < 1900 or annee > 2100:
        raise ValueError(f"année hors plage : {annee!r}")
    return f"{annee}-12-31"


def mio_en_md(mio: float) -> float:
    """Million d'euros → Md€. Un million d'euros = 0,001 milliard. Jamais ÷ 1e9."""
    return mio / 1000.0


def _annee(valeur) -> int:
    texte = str(valeur).strip()
    if len(texte) != 4 or not texte.isdigit():
        raise ValueError(f"année hors motif YYYY : {valeur!r}")
    return int(texte)


def _val(valeur) -> float:
    try:
        nombre = float(valeur)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"valeur non numérique : {valeur!r}") from exc
    if nombre <= 0:
        raise ValueError(f"prestation ≤ 0 : {nombre}")
    return nombre


def _recompose(parts: list[tuple[str, float]], total: float) -> bool:
    return abs(sum(v for _, v in parts) - total) <= TOLERANCE_MIO


def extraire(payload: list) -> list[dict]:
    """Export JSON DREES → lignes exclusives (total / risque / régime).

    Ignore les niveaux 2 et 3 (recouvrement). Le TIME max doit porter
    les trois grains, avec S13141, et recomposer le total des deux côtés.
    """
    if not isinstance(payload, list) or not payload:
        raise ValueError("export DREES : liste d'enregistrements attendue")

    totaux: dict[int, tuple[str, float]] = {}
    risques: dict[int, list[tuple[str, str, float]]] = defaultdict(list)
    regimes: dict[int, list[tuple[str, str, float]]] = defaultdict(list)

    for i, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"enregistrement {i} n'est pas un objet")
        try:
            annee = _annee(row.get("annee"))
            val = _val(row.get("val"))
        except ValueError as exc:
            raise ValueError(f"enregistrement {i} : {exc}") from exc
        ps_niveau = str(row.get("ps_niveau") or "")
        si_niveau = str(row.get("si_niveau") or "")
        ps_code = str(row.get("ps_code") or "")
        si_code = str(row.get("si_code") or "")
        ps_lib = str(row.get("ps_lib") or "").strip()
        si_nom = str(row.get("si_nom") or "").strip()

        if (
            si_niveau == "0"
            and si_code == CODE_TOTAL_SI
            and ps_niveau == "0"
            and ps_code == CODE_TOTAL_PS
        ):
            if annee in totaux:
                raise ValueError(f"total en double pour {annee}")
            totaux[annee] = (si_nom or "Total tous régimes", val)
            continue
        if si_code == CODE_TOTAL_SI and ps_niveau == "1" and ps_code in CODES_RISQUE:
            if not ps_lib:
                raise ValueError(f"risque {ps_code} {annee} sans libellé")
            risques[annee].append((ps_code, ps_lib, val))
            continue
        if si_niveau == "1" and ps_code == CODE_TOTAL_PS and si_code:
            if not si_nom:
                raise ValueError(f"régime {si_code} {annee} sans libellé")
            regimes[annee].append((si_code, si_nom, val))

    if not totaux:
        raise ValueError("aucun total S1 / E11-0")

    time_max = max(totaux)
    lignes: list[dict] = []

    for annee in sorted(totaux):
        lib_total, val_total = totaux[annee]
        lignes.append({
            "annee": annee,
            "grain": "total",
            "code": CODE_TOTAL_SI,
            "libelle": lib_total,
            "val_mio_eur": val_total,
        })

        ris = risques.get(annee) or []
        codes_ris = [c for c, _, _ in ris]
        if (
            sorted(codes_ris) == sorted(CODES_RISQUE)
            and _recompose([(c, v) for c, _, v in ris], val_total)
        ):
            for code, libelle, val in sorted(ris, key=lambda t: t[0]):
                lignes.append({
                    "annee": annee,
                    "grain": "risque",
                    "code": code,
                    "libelle": libelle,
                    "val_mio_eur": val,
                })
        elif annee == time_max:
            raise ValueError(
                f"TIME max {time_max} : risques incomplets ou non recomposés "
                f"(codes={codes_ris}, somme={sum(v for _, _, v in ris)})"
            )

        reg = regimes.get(annee) or []
        if reg and _recompose([(c, v) for c, _, v in reg], val_total):
            if annee == time_max and CODE_REGIME_GENERAL not in {c for c, _, _ in reg}:
                raise ValueError(
                    f"TIME max {time_max} : régime général {CODE_REGIME_GENERAL} absent"
                )
            for code, libelle, val in sorted(reg, key=lambda t: t[0]):
                lignes.append({
                    "annee": annee,
                    "grain": "regime",
                    "code": code,
                    "libelle": libelle,
                    "val_mio_eur": val,
                })
        elif annee == time_max:
            raise ValueError(
                f"TIME max {time_max} : régimes absents ou non recomposés "
                f"(n={len(reg)}, somme={sum(v for _, _, v in reg)})"
            )

    return lignes


def controler_ampleur(lignes: list[dict]) -> None:
    """Garde-fous d'unité sur le TIME max réel, pas sur une fixture minimale."""
    totaux = [o for o in lignes if o["grain"] == "total"]
    if len(totaux) < N_TOTALS_MIN:
        raise ValueError(
            f"{len(totaux)} totaux, {N_TOTALS_MIN} attendus au minimum"
        )
    dernier = max(totaux, key=lambda o: o["annee"])
    v = dernier["val_mio_eur"]
    if not (BORNE_MIN_MIO < v < BORNE_MAX_MIO):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"total {dernier['annee']} = {v} M€ "
            f"hors ]{BORNE_MIN_MIO:g}, {BORNE_MAX_MIO:g}["
        )
    annee = dernier["annee"]
    risques = [o for o in lignes if o["grain"] == "risque" and o["annee"] == annee]
    regimes = [o for o in lignes if o["grain"] == "regime" and o["annee"] == annee]
    if {o["code"] for o in risques} != set(CODES_RISQUE):
        raise ValueError(f"TIME max {annee} : codes risque {sorted(o['code'] for o in risques)}")
    if not _recompose([(o["code"], o["val_mio_eur"]) for o in risques], v):
        raise ValueError(f"TIME max {annee} : somme des risques ≠ total")
    if CODE_REGIME_GENERAL not in {o["code"] for o in regimes}:
        raise ValueError(f"TIME max {annee} : {CODE_REGIME_GENERAL} absent")
    if not _recompose([(o["code"], o["val_mio_eur"]) for o in regimes], v):
        raise ValueError(f"TIME max {annee} : somme des régimes ≠ total")


def ecrire_db(conn, lignes: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S45. Retourne date_donnees."""
    grains = {o["grain"] for o in lignes}
    if not {"total", "risque", "regime"} <= grains:
        raise ValueError(f"écriture incomplète : {sorted(grains)}")
    date_donnees = date_fin_annee(max(o["annee"] for o in lignes))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM protection_sociale_prestations")
        conn.executemany(
            """INSERT INTO protection_sociale_prestations
               (annee, grain, code, libelle, val_mio_eur)
               VALUES (:annee, :grain, :code, :libelle, :val_mio_eur)""",
            lignes,
        )
    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_DATASET,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(lignes),
        notes=NOTES,
    )
    return date_donnees


def main() -> int:
    try:
        chemin = telecharger(URL_EXPORT, FICHIER_RAW, max_age_heures=CACHE_HEURES)
        payload = json.loads(Path(chemin).read_text(encoding="utf-8"))
        lignes = extraire(payload)
        controler_ampleur(lignes)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, lignes)
        conn.close()
        time_max = max(o["annee"] for o in lignes)
        log.info(
            "protection_sociale_prestations: %d lignes, données au %s (année max %s)",
            len(lignes),
            date_donnees,
            time_max,
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S45 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
