"""P28 — Dépenses et recettes des ODAC (S51, INSEE, tableau 3.204).

Source : Insee Résultats 8988845, xlsx t_3204_fr.xlsx — « Dépenses et
recettes des organismes divers d'administration centrale (S13112) ».
Page : https://www.insee.fr/fr/statistiques/8988845?sommaire=8988934.

Licence : Licence Ouverte 2.0 (Etalab) — catalogue INSEE
https://www.insee.fr/fr/information/8184173 ; texte légal relu
https://www.data.gouv.fr/pages/legal/licences/etalab-2.0/ (25/08/2026).

CE PIPELINE N'EST PAS LA SOURCE S50, NI S13, NI S39, NI S44, NI S42
------------------------------------------------------------------
S50 ingère les totaux 3.201–3.203 / 3.205 / 3.212 et le PO 3.216 dans
`comptes_apu_insee` (DELETE à chaque run) : il n'a pas le 3.204.
S1311 (APU centrale) est l'État + ODAC en consolidation, pas la somme
S13111 + S13112. On n'additionne pas ce tableau à S13111 ni à S1311.
S13 = budget de l'État (SMB DGFiP). S39 = jaune opérateurs (0 €).
S44 = TE/TR Eurostat. S42 = B9 Maastricht (non ingéré ici).
ODAC ≠ opérateurs de l'État. Pas de PO (le 3.216 reste à S50).

N'ingère PAS B9NF, PAS l'épargne brute, PAS les lignes « dont », PAS
les recettes/dépenses hors imputés, PAS 3.217 / 3.207–3.210.

Unité native du xlsx : **milliards d'euros**. Stockée telle quelle.
Jamais × 1000 ni ÷ 1e9.

`date_donnees` = 31 décembre de l'année max observée, jamais
`modified` Melodi (2026-06-08) ni la date de parution Insee Résultats
(29/05/2026).

Exécution : python -m pipelines.ingest_odac_insee
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente
(DELETE puis INSERT dans une transaction), puis upsert_meta('S51', …).
Échec → exit ≠ 0, base intacte.

Le parseur xlsx est celui de S50 (`extraire_dep_rec` accepte déjà
S13112) : le 3.204 a le même gabarit DEP/REC que 3.201–3.203.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger
from pipelines.ingest_comptes_apu_insee import date_fin_annee, extraire_dep_rec

log = obtenir_logger("odac_insee")

SOURCE_ID = "S51"
NOM_SOURCE = (
    "Dépenses et recettes des ODAC (INSEE, S13112, tableau 3.204)"
)
URL_PAGE = (
    "https://www.insee.fr/fr/statistiques/8988845?sommaire=8988934"
)
URL_FICHIER = (
    "https://www.insee.fr/fr/statistiques/fichier/8988845/t_3204_fr.xlsx"
)
LICENCE = "Licence Ouverte 2.0 (Etalab)"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24
CACHE_RELATIF = "insee/cna_apu/t_3204_fr.xlsx"

TABLEAU = "3.204"
SECTEUR = "S13112"
POSTES = ("DEP_TOTAL", "REC_TOTAL")
UNITE = "MdEUR"

BORNE_MIN_MD = 20.0
BORNE_MAX_MD = 400.0
N_ANNEES_MIN = 25

NOTES = (
    "comptes nationaux base 2020, présentation dépenses et recettes "
    "(Insee Résultats 8988845, tableau 3.204 seulement, secteur S13112 "
    "ODAC) ; unité native Md€ ; date_donnees = 31/12 de l'année max, "
    "jamais modified Melodi ni date de parution ; distinct de S50 "
    "(S1311 = État+ODAC en consolidation, sans le 3.204 ; ne pas "
    "additionner à S13111) ; distinct de S13 (budget de l'État), de S39 "
    "(jaune opérateurs, 0 €), de S44 (TE/TR), de S42 (B9 non ingéré) ; "
    "ODAC ≠ opérateurs de l'État ; pas de PO (3.216 reste à S50) ; "
    "pas B9NF, pas épargne brute, pas les lignes dont"
)

_DDL = """
CREATE TABLE IF NOT EXISTS comptes_odac_insee (
    tableau   TEXT NOT NULL CHECK (tableau = '3.204'),
    secteur   TEXT NOT NULL CHECK (secteur = 'S13112'),
    poste     TEXT NOT NULL CHECK (poste IN ('DEP_TOTAL','REC_TOTAL')),
    libelle   TEXT NOT NULL,
    annee     INTEGER NOT NULL,
    valeur_md REAL NOT NULL CHECK (valeur_md > 0),
    unite     TEXT NOT NULL CHECK (unite = 'MdEUR'),
    PRIMARY KEY (tableau, secteur, poste, annee, unite)
);
"""

_INTERDITS = (
    "b9",
    "besoin de financement",
    "epargne brute",
    "épargne brute",
)


def _lab_minuscule(texte: str) -> str:
    return " ".join((texte or "").lower().split())


def _motif_interdit(observation: dict) -> str | None:
    blob = _lab_minuscule(
        f"{observation.get('libelle') or ''} {observation.get('poste') or ''}"
    )
    for motif in _INTERDITS:
        if motif in blob:
            return motif
    lab = _lab_minuscule(observation.get("libelle") or "")
    if lab.startswith("dont") or "dont (" in lab:
        return "dont"
    if "hors elements imputes" in lab or "hors éléments imputés" in lab:
        return "hors imputés"
    return None


def extraire(chemin: Path) -> list[dict]:
    """Totaux DEP/REC du 3.204, secteur S13112. Pas B9, pas les « dont »."""
    observations = extraire_dep_rec(chemin, TABLEAU, SECTEUR)
    for o in observations:
        motif = _motif_interdit(o)
        if motif is not None:
            raise ValueError(
                f"solde B9, épargne, dont ou hors imputés ingéré "
                f"({motif}) : {o['libelle']!r}"
            )
        if (
            o["tableau"] != TABLEAU
            or o["secteur"] != SECTEUR
            or o["poste"] not in POSTES
            or o["unite"] != UNITE
        ):
            raise ValueError(f"observation hors contrat : {o}")
    postes = {o["poste"] for o in observations}
    if postes != set(POSTES):
        raise ValueError(
            f"{TABLEAU} : postes lus {sorted(postes)}, "
            "DEP_TOTAL et REC_TOTAL attendus"
        )
    return observations


def controler_ampleur(observations: list[dict]) -> None:
    """Bornes d'unité sur le TIME max commun DEP/REC, pas la fixture."""
    if not observations:
        raise ValueError("aucune observation")
    for o in observations:
        motif = _motif_interdit(o)
        if motif is not None:
            raise ValueError(
                f"solde B9 ou épargne ingéré : {o.get('libelle')!r}"
            )
        if o.get("tableau") != TABLEAU:
            raise ValueError(
                f"tableau hors contrat : {o.get('tableau')!r}, {TABLEAU} attendu"
            )
        if o.get("secteur") != SECTEUR:
            raise ValueError(
                f"secteur hors contrat : {o.get('secteur')!r}, {SECTEUR} attendu"
            )
        if o.get("poste") not in POSTES:
            raise ValueError(f"poste hors contrat : {o.get('poste')!r}")
        if o.get("unite") != UNITE:
            raise ValueError(f"unité hors contrat : {o.get('unite')!r}")

    tableaux = {o["tableau"] for o in observations}
    if tableaux != {TABLEAU}:
        raise ValueError(
            f"tableaux lus {sorted(tableaux)}, attendu [{TABLEAU}]"
        )
    secteurs = {o["secteur"] for o in observations}
    if secteurs != {SECTEUR}:
        raise ValueError(
            f"secteurs lus {sorted(secteurs)}, attendu [{SECTEUR}]"
        )

    def serie(poste: str) -> list[dict]:
        return [
            o
            for o in observations
            if o["poste"] == poste and o["unite"] == UNITE
        ]

    dep = serie("DEP_TOTAL")
    rec = serie("REC_TOTAL")
    if len(dep) < N_ANNEES_MIN:
        raise ValueError(
            f"S13112 DEP_TOTAL : {len(dep)} années, {N_ANNEES_MIN} attendues"
        )
    if len(rec) < N_ANNEES_MIN:
        raise ValueError(
            f"S13112 REC_TOTAL : {len(rec)} années, {N_ANNEES_MIN} attendues"
        )
    dernier_dep = max(dep, key=lambda o: o["annee"])
    dernier_rec = max(rec, key=lambda o: o["annee"])
    if dernier_dep["annee"] != dernier_rec["annee"]:
        raise ValueError(
            f"millésime DEP ({dernier_dep['annee']}) ≠ REC "
            f"({dernier_rec['annee']}) — année max commune exigée"
        )
    v = dernier_dep["valeur_md"]
    if not (BORNE_MIN_MD < v < BORNE_MAX_MD):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"S13112 DEP_TOTAL {dernier_dep['annee']} = {v} Md€ "
            f"hors ]{BORNE_MIN_MD:g}, {BORNE_MAX_MD:g}["
        )
    vr = dernier_rec["valeur_md"]
    if not (BORNE_MIN_MD < vr < BORNE_MAX_MD):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"S13112 REC_TOTAL {dernier_rec['annee']} = {vr} Md€ "
            f"hors ]{BORNE_MIN_MD:g}, {BORNE_MAX_MD:g}["
        )


def ecrire_db(conn, observations: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S51. Retourne date_donnees."""
    if not observations:
        raise ValueError("écriture vide")
    tableaux = {o["tableau"] for o in observations}
    if tableaux != {TABLEAU}:
        raise ValueError(f"écriture incomplète : {sorted(tableaux)}")
    secteurs = {o["secteur"] for o in observations}
    if secteurs != {SECTEUR}:
        raise ValueError(f"secteur hors contrat à l'écriture : {sorted(secteurs)}")
    date_donnees = date_fin_annee(max(o["annee"] for o in observations))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM comptes_odac_insee")
        conn.executemany(
            """INSERT INTO comptes_odac_insee
               (tableau, secteur, poste, libelle, annee, valeur_md, unite)
               VALUES (:tableau, :secteur, :poste, :libelle,
                       :annee, :valeur_md, :unite)""",
            observations,
        )
    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_PAGE,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(observations),
        notes=NOTES,
    )
    return date_donnees


def main() -> int:
    try:
        brut = telecharger(
            URL_FICHIER,
            CACHE_RELATIF,
            max_age_heures=CACHE_HEURES,
        )
        observations = extraire(Path(brut))
        controler_ampleur(observations)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, observations)
        conn.close()
        log.info(
            "odac_insee: %d observations, données au %s (année max %s)",
            len(observations),
            date_donnees,
            max(o["annee"] for o in observations),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S51 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
