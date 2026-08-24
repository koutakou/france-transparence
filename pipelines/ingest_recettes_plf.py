"""P23 — Recettes du budget général au PLF (S46, data.economie).

Source : jeu ODS `plf25-recettes-du-budget-general`
(Direction du Budget / data.economie.gouv.fr), export CSV.
Licence : Licence Ouverte v2.0 (Etalab), relue le 24/08/2026 sur
la fiche ODS (HTTP 200, champ license). 156 lignes, millésime
unique 2025, publication 11/10/2024 (même jour que S21
destination). Aucun équivalent PLF 2026 / LFI 2026 en données
(préfixe plf26 = 0 ; seul `plf-2026-budget-vert` existe).

CE PIPELINE N'EST PAS LA SOURCE S13, NI LA LFI, NI L'APE
--------------------------------------------------------
Les montants sont ceux du **Projet de loi de finances** (État A),
recettes **brutes**, année civile du PLF. `source_id` = **S46**,
jamais `'S13'`. S13 = situations mensuelles DGFiP, recettes
**nettes** des remboursements et dégrèvements, cumul depuis le
1er janvier, exécution. Les comparer sans dire brutes ≠ nettes
et projet ≠ exécution est un mensonge. On n'additionne pas. On
ne calcule pas de « nettes » en retranchant les prélèvements
sur recettes (PSR) : ce n'est pas dans le jeu.

Les 56 lignes « Recettes non fiscales » SONT le détail que S13
ne publie pas (un seul total). Les lignes 2110, 2116 et 2199
sont les produits de participations / dividendes du même État A
— pas le rapport annuel de l'Agence des participations de l'État
(aucun jeu APE n'existe sur data.gouv / data.economie au
24/08/2026).

Unité native : **euros**. Md€ = euros ÷ 1e9 à la lecture, jamais
÷ 1000 (unité Eurostat MIO_EUR). Un zéro publié est un zéro,
pas un NULL. `date_donnees` = jour de publication de *ce* jeu open data pour
le millésime max (2025 → 2024-10-11, le lendemain de
l'enregistrement du PLF à l'AN le 10/10/2024, et le même jour
que S21 destination). Un millésime nouveau sans date écrite ici
fait échouer l'ingestion : on n'invente pas, et on ne relit pas
`modified` à chaque run (il pourrait bouger sans nouveau
millésime).

Exécution : python -m pipelines.ingest_recettes_plf
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente
(DELETE puis INSERT dans une transaction), puis upsert_meta
('S46', …). Échec → exit ≠ 0, base intacte.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from pipelines import db
from pipelines.common import assainir_texte, obtenir_logger, telecharger

log = obtenir_logger("recettes_plf")

SOURCE_ID = "S46"
NOM_SOURCE = (
    "PLF 2025 — recettes du budget général "
    "(État A, Direction du Budget)"
)
URL_DATASET = (
    "https://data.economie.gouv.fr/explore/dataset/"
    "plf25-recettes-du-budget-general/"
)
URL_EXPORT = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "plf25-recettes-du-budget-general/exports/csv"
)
LICENCE = "Licence Ouverte 2.0 (Etalab)"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24
FICHIER_RAW = "budget/plf25_recettes_bg.csv"

# Jour de publication de ce jeu open data, par millésime de l'État A.
# 2025 : created/modified ODS = 2024-10-11 (mesuré 24/08/2026). Ce
# n'est PAS le dépôt parlementaire (AN, texte n° 324, 10/10/2024).
# Un millésime nouveau sans date ici fait échouer l'ingestion : on
# n'invente pas, et on ne relit pas `modified` à chaque run.
DATES_PUBLICATION = {2025: "2024-10-11"}

ETIQUETTE = (
    "PLF 2025 déposé en octobre 2024 — projet, pas la LFI 2025 votée, "
    "pas l'exécution (S13)"
)

# Libellés source → type interne. Un libellé hors de ce dictionnaire
# arrête l'ingestion (un cinquième type n'est pas « autres »).
TYPES_SOURCE = {
    "Recettes fiscales": "fiscales",
    "Recettes non fiscales": "non_fiscales",
    (
        "Prélèvements sur les recettes de l'État au profit "
        "des collectivités territoriales"
    ): "psr_collectivites",
    (
        "Prélèvement sur les recettes de l'État au profit "
        "de l'Union européenne"
    ): "psr_ue",
}
TYPES_INTERNES = frozenset(TYPES_SOURCE.values())

# Produits des participations / dividendes de l'État A (codes
# stables du jaune « voies et moyens »). Liste fermée, pas un
# grep sur le libellé.
CODES_PARTICIPATIONS = (2110, 2116, 2199)

# Garde-fous d'ampleur sur le millésime max, pas la fixture.
N_LIGNES_MIN = 100
N_LIGNES_MAX = 250
BORNE_NF = (5e9, 50e9)        # 5–50 Md€ de non fiscales
BORNE_FISCALES = (200e9, 900e9)

NOTES = (
    "État A du PLF, recettes BRUTES en euros, pas les nettes S13 ; "
    "pas la LFI votée ; pas 2026 (aucun jeu plf26-recettes au 24/08) ; "
    "56 lignes non fiscales = le détail que S13 ne publie pas ; "
    "lignes 2110/2116/2199 = participations et dividendes du même "
    "État A, pas le rapport APE ; PSR = prélèvements sur recettes, "
    "pas un encaissement conservé ; un zéro publié est un zéro ; "
    "Md€ = euros ÷ 1e9 à la lecture (jamais ÷ 1000) ; "
    "date_donnees = publication open data du millésime max "
    "(2025 → 2024-10-11, lendemain du dépôt AN 10/10/2024), "
    "jamais modified relu à chaque run"
)

_DDL = """
CREATE TABLE IF NOT EXISTS recettes_plf_etat_a (
    annee          INTEGER NOT NULL,
    type_recette   TEXT NOT NULL CHECK (type_recette IN (
                       'fiscales',
                       'non_fiscales',
                       'psr_collectivites',
                       'psr_ue'
                   )),
    code           INTEGER NOT NULL,
    libelle        TEXT NOT NULL,
    montant_euros  REAL NOT NULL CHECK (montant_euros >= 0),
    PRIMARY KEY (annee, code)
);
"""


def euros_en_md(euros: float) -> float:
    """Euros → Md€. Un milliard d'euros = 1,0. Jamais ÷ 1000."""
    return euros / 1e9


def date_publication(annee: int) -> str:
    """Jour de publication open data du millésime, ou échec franc."""
    try:
        return DATES_PUBLICATION[annee]
    except KeyError as e:
        raise ValueError(
            f"millésime {annee} : date de publication open data absente de "
            "DATES_PUBLICATION — l'écrire, ne pas relire modified du catalogue"
        ) from e


def _entier_code(brut: str) -> int:
    """'2110.0' / '2110' → 2110. Refuse un code non entier."""
    s = (brut or "").strip().replace(" ", "").replace(",", ".")
    if not s:
        raise ValueError("code_ligne_recettes vide")
    try:
        val = float(s)
    except ValueError as e:
        raise ValueError(f"code_ligne_recettes illisible : {brut!r}") from e
    if val != int(val) or val <= 0:
        raise ValueError(f"code_ligne_recettes non entier positif : {brut!r}")
    return int(val)


def _montant(brut: str) -> float:
    """Montant source → float euros. 0 est licite. Négatif interdit."""
    s = (brut or "").strip().replace(" ", "").replace(",", ".")
    if not s:
        raise ValueError("montant_recettes_plf vide")
    try:
        val = float(s)
    except ValueError as e:
        raise ValueError(f"montant_recettes_plf illisible : {brut!r}") from e
    if val < 0:
        raise ValueError(f"montant négatif refusé : {brut!r}")
    return val


def extraire(chemin: Path) -> list[dict]:
    """CSV ODS (UTF-8 BOM, ';') → lignes métier, sans écriture."""
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteurs = csv.DictReader(f, delimiter=";")
        if lecteurs.fieldnames is None:
            raise ValueError("CSV sans en-tête")
        lecteurs.fieldnames = [
            (nom or "").lstrip("\ufeff") for nom in lecteurs.fieldnames
        ]
        champs = set(lecteurs.fieldnames)
        attendus = {
            "annee",
            "type_de_recettes",
            "code_ligne_recettes",
            "libelle",
            "montant_recettes_plf",
        }
        if not attendus <= champs:
            raise ValueError(
                f"colonnes manquantes : {sorted(attendus - champs)}"
            )
        lignes: list[dict] = []
        vus: set[tuple[int, int]] = set()
        for brut in lecteurs:
            annee_s = (brut.get("annee") or "").strip()
            try:
                annee = int(annee_s)
            except ValueError as e:
                raise ValueError(f"année illisible : {annee_s!r}") from e
            if annee < 2000 or annee > 2100:
                raise ValueError(f"année hors plage : {annee}")
            type_src = assainir_texte(brut.get("type_de_recettes"))
            if type_src not in TYPES_SOURCE:
                raise ValueError(
                    f"type_de_recettes inconnu : {type_src!r} "
                    f"(attendus : {sorted(TYPES_SOURCE)})"
                )
            libelle = assainir_texte(brut.get("libelle"))
            if not libelle:
                raise ValueError(
                    f"libellé vide pour le code {brut.get('code_ligne_recettes')!r}"
                )
            code = _entier_code(brut.get("code_ligne_recettes") or "")
            cle = (annee, code)
            if cle in vus:
                raise ValueError(f"code dupliqué : année {annee} code {code}")
            vus.add(cle)
            lignes.append(
                {
                    "annee": annee,
                    "type_recette": TYPES_SOURCE[type_src],
                    "code": code,
                    "libelle": libelle,
                    "montant_euros": _montant(
                        brut.get("montant_recettes_plf") or ""
                    ),
                }
            )
    if not lignes:
        raise ValueError("aucune ligne extraite")
    return lignes


def controler_ampleur(lignes: list[dict]) -> None:
    """Garde-fous d'unité et de catalogue sur le millésime max réel."""
    n = len(lignes)
    if not (N_LIGNES_MIN <= n <= N_LIGNES_MAX):
        raise ValueError(
            f"{n} lignes, attendu entre {N_LIGNES_MIN} et {N_LIGNES_MAX}"
        )
    types = {o["type_recette"] for o in lignes}
    if types != TYPES_INTERNES:
        raise ValueError(f"types présents {sorted(types)}, attendus {sorted(TYPES_INTERNES)}")
    annee = max(o["annee"] for o in lignes)
    date_publication(annee)  # millésime sans date écrite → échec
    du_millesime = [o for o in lignes if o["annee"] == annee]
    codes = {o["code"] for o in du_millesime}
    manquants = [c for c in CODES_PARTICIPATIONS if c not in codes]
    if manquants:
        raise ValueError(
            f"TIME max {annee} : codes participations manquants {manquants}"
        )
    somme_nf = sum(
        o["montant_euros"]
        for o in du_millesime
        if o["type_recette"] == "non_fiscales"
    )
    if not (BORNE_NF[0] < somme_nf < BORNE_NF[1]):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"non fiscales {annee} = {somme_nf} € "
            f"hors ]{BORNE_NF[0]:g}, {BORNE_NF[1]:g}["
        )
    somme_fis = sum(
        o["montant_euros"]
        for o in du_millesime
        if o["type_recette"] == "fiscales"
    )
    if not (BORNE_FISCALES[0] < somme_fis < BORNE_FISCALES[1]):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"fiscales {annee} = {somme_fis} € "
            f"hors ]{BORNE_FISCALES[0]:g}, {BORNE_FISCALES[1]:g}["
        )


def ecrire_db(conn, lignes: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S46. Retourne date_donnees."""
    types = {o["type_recette"] for o in lignes}
    if types != TYPES_INTERNES:
        raise ValueError(f"écriture incomplète : {sorted(types)}")
    annee = max(o["annee"] for o in lignes)
    date_donnees = date_publication(annee)
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM recettes_plf_etat_a")
        conn.executemany(
            """INSERT INTO recettes_plf_etat_a
               (annee, type_recette, code, libelle, montant_euros)
               VALUES (:annee, :type_recette, :code, :libelle, :montant_euros)""",
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
        lignes = extraire(Path(chemin))
        controler_ampleur(lignes)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, lignes)
        conn.close()
        annee = max(o["annee"] for o in lignes)
        nf = sum(
            o["montant_euros"]
            for o in lignes
            if o["annee"] == annee and o["type_recette"] == "non_fiscales"
        )
        log.info(
            "recettes_plf_etat_a: %d lignes, données au %s "
            "(PLF %s, non fiscales %.3f Md€)",
            len(lignes),
            date_donnees,
            annee,
            euros_en_md(nf),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S46 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
