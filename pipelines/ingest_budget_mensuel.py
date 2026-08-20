"""P1 — Situations mensuelles budgétaires de l'État, séries longues (S13, DGFiP).

Source (data.economie.gouv.fr, Licence Ouverte 2.0) : dataset
« situations-mensuelles-budgetaires-series-longues » — 26 lignes (solde,
dépenses par titre agrégé, recettes, comptes spéciaux) × 1 colonne par fin
de mois. Deux fichiers complémentaires, sans chevauchement :
- export CSV de l'API : mois 01/2024 → dernier publié (UTF-8 BOM, décimales « . ») ;
- pièce jointe « Séries longues SMB_DGFiP_2013-2023.csv » : 01/2013 → 12/2023
  (UTF-16, décimales « , », libellés avec espaces parasites, lignes vides en fin).
Les montants sont des CUMULS depuis le 1er janvier de l'exercice, en euros.
Pièges gérés : colonne anormale `24_04_2024` (le jour est ignoré, seuls
mois/année font foi) ; libellés à apostrophes/espaces variables (normalisés).

Table créée (module UI « Dépenses de l'État » + compteur Accueil) :
- budget_mensuel :
    ligne_id         TEXT  clé stable, ex. 'depenses/budget-general/depenses-de-personnel'
    ordre            INT   ordre d'affichage (ordre du tableau source, 0-25)
    niveau           INT   niveau hiérarchique source (0 à 4)
    categorie        TEXT  'Solde budgétaire' | 'Dépenses' | 'Recettes' | 'Soldes'
    sous_categorie   TEXT  ex. 'Budget général', 'Prélèvements sur recettes'
    ligne            TEXT  libellé d'affichage, ex. 'Total dépenses nettes du budget général'
    date_fin_mois    TEXT  ISO 'YYYY-MM-DD' (dernier jour réel du mois)
    annee            INT
    mois             INT
    montant_cumul    REAL  cumul depuis le 1er janvier (valeur native source, €)
    montant_mois     REAL  flux du mois (cumul m − cumul m−1 ; janvier = cumul) ; NULL si m−1 absent
    montant_cumul_n1 REAL  cumul au même mois de l'année précédente (NULL si absent)
    montant_mois_n1  REAL  flux du même mois de l'année précédente (NULL si absent)
  PK (ligne_id, date_fin_mois) ; index (annee, mois).

Affichages couverts : dernier mois connu (max date_fin_mois), cumul annuel
(montant_cumul), variation vs même mois / même cumul N−1 (colonnes *_n1),
décomposition par titre : WHERE categorie = 'Dépenses' AND sous_categorie =
'Budget général' AND niveau = 2 (sans ce filtre categorie, les lignes de
recettes niveau 2 du budget général s'y mêlent).
Rappel pour le front : mois infra-annuels provisoires ; ni temps réel ni
détail mission/programme dans cette source (cf. docs/SOURCES.md S13).

Exécution : python -m pipelines.ingest_budget_mensuel
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente (DELETE puis
INSERT dans une transaction), puis upsert_meta('S13', …). Échec source →
exit ≠ 0, base intacte.
"""

from __future__ import annotations

import calendar
import csv
import re
import sys
import unicodedata
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("budget_mensuel")

SOURCE_ID = "S13"
URL_PAGE = (
    "https://data.economie.gouv.fr/explore/dataset/"
    "situations-mensuelles-budgetaires-series-longues/"
)
URL_EXPORT = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "situations-mensuelles-budgetaires-series-longues/exports/csv"
)
URL_HISTORIQUE = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "situations-mensuelles-budgetaires-series-longues/attachments/"
    "series_longues_smb_dgfip_2013_2023_csv"
)

# Garde-fous d'ordre de grandeur (dépenses nettes annuelles du BG ~450-500 Md€).
LIGNE_TEMOIN = "Total dépenses nettes du budget général"
TEMOIN_MIN, TEMOIN_MAX = 250e9, 800e9  # cumul de décembre, années 2013→
NB_LIGNES_ATTENDU = 26

_RE_COL_DATE = re.compile(r"^\s*(\d{1,2})[_/](\d{1,2})[_/](\d{4})\s*$")

# ---------------------------------------------------------------------------
# Transformations pures (testées dans pipelines/tests/test_budget.py)
# ---------------------------------------------------------------------------


def normaliser_libelle(s: str) -> str:
    """Libellé comparable entre l'export (’, propre) et la pièce jointe
    (apostrophes droites, doubles espaces, espaces de fin, insécables)."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("’", "'").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def analyser_colonne_date(nom: str) -> tuple[int, int] | None:
    """'31_01_2024' / '31/01/2013' / '24_04_2024' (anomalie réelle) → (annee, mois).

    Le « jour » de l'en-tête n'est jamais utilisé (cf. anomalie 24_04_2024) ;
    None si la colonne n'est pas une colonne de date valide.
    """
    m = _RE_COL_DATE.match(nom or "")
    if not m:
        return None
    mois, annee = int(m.group(2)), int(m.group(3))
    if not 1 <= mois <= 12:
        return None
    return (annee, mois)


def parser_montant(s: str | None) -> float | None:
    """Montant source → float. Gère décimales '.' (export) et ',' (pièce
    jointe), espaces y compris insécables ; vide/None → None (jamais 0 inventé)."""
    if s is None:
        return None
    s = s.replace(" ", "").replace(" ", "").replace(" ", "").strip()
    if not s:
        return None
    return float(s.replace(",", "."))


def fin_de_mois(annee: int, mois: int) -> str:
    """Dernier jour réel du mois, ISO ('2024-02-29' pour 2024/02)."""
    return f"{annee:04d}-{mois:02d}-{calendar.monthrange(annee, mois)[1]:02d}"


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def identifiant_ligne(categorie: str, sous_categorie: str, ligne: str) -> str:
    """Clé stable et lisible d'une ligne SMB, ex.
    'depenses/budget-general/depenses-de-personnel'."""
    return "/".join(_slug(p) for p in (categorie, sous_categorie, ligne))


def extraire_tableau(lignes_csv: list[list[str]]) -> tuple[list[dict], list[tuple[int, int]]]:
    """CSV SMB brut (liste de lignes) → (lignes métier, mois présents).

    Chaque ligne métier : {'niveau', 'categorie', 'sous_categorie', 'ligne',
    'valeurs': {(annee, mois): float}}. Ignore les lignes de remplissage vides
    de la pièce jointe et la colonne finale vide. Ne fabrique aucune valeur :
    cellule vide → absente du dict.
    """
    if not lignes_csv:
        raise ValueError("CSV SMB vide")
    entete = lignes_csv[0]
    cols_dates = [(i, am) for i, c in enumerate(entete)
                  if (am := analyser_colonne_date(c)) is not None]
    if not cols_dates:
        raise ValueError(f"aucune colonne de date reconnue dans l'en-tête: {entete[:8]}")
    resultat = []
    for brut in lignes_csv[1:]:
        if len(brut) < 5 or not normaliser_libelle(brut[4]):
            continue  # lignes de remplissage en fin de pièce jointe
        valeurs = {}
        for i, am in cols_dates:
            v = parser_montant(brut[i]) if i < len(brut) else None
            if v is not None:
                valeurs[am] = v
        resultat.append({
            "niveau": int(brut[0]),
            "categorie": normaliser_libelle(brut[2]),
            "sous_categorie": normaliser_libelle(brut[3]),
            "ligne": normaliser_libelle(brut[4]),
            "valeurs": valeurs,
        })
    return resultat, [am for _, am in cols_dates]


def construire_serie(tableau_export: list[dict],
                     tableau_hist: list[dict]) -> list[dict]:
    """Fusionne export (2024→) et historique (2013-2023) en enregistrements longs.

    - jointure des 26 lignes par (categorie, sous_categorie, ligne) normalisés,
      erreur claire si les deux fichiers ne portent pas les mêmes lignes ;
    - en cas de chevauchement d'un mois, la valeur de l'export (plus fraîche) gagne ;
    - calcule montant_mois (cumul m − cumul m−1, janvier = cumul) et les
      colonnes N−1 (montant_cumul_n1, montant_mois_n1).
    """
    cle = lambda l: (l["categorie"], l["sous_categorie"], l["ligne"])  # noqa: E731
    exp = {cle(l): l for l in tableau_export}
    hist = {cle(l): l for l in tableau_hist}
    if set(exp) != set(hist):
        raise ValueError(
            "lignes divergentes entre export et pièce jointe 2013-2023 — "
            f"export seulement: {sorted(set(exp) - set(hist))} ; "
            f"pièce jointe seulement: {sorted(set(hist) - set(exp))}"
        )

    enregistrements = []
    for ordre, ligne in enumerate(tableau_export):
        k = cle(ligne)
        valeurs = dict(hist[k]["valeurs"])
        valeurs.update(ligne["valeurs"])  # l'export gagne sur un éventuel chevauchement
        flux = {}
        for (a, m), cumul in valeurs.items():
            if m == 1:
                flux[(a, m)] = cumul
            elif (a, m - 1) in valeurs:
                flux[(a, m)] = cumul - valeurs[(a, m - 1)]
        for (a, m) in sorted(valeurs):
            enregistrements.append({
                "ligne_id": identifiant_ligne(*k),
                "ordre": ordre,
                "niveau": ligne["niveau"],
                "categorie": k[0],
                "sous_categorie": k[1],
                "ligne": k[2],
                "date_fin_mois": fin_de_mois(a, m),
                "annee": a,
                "mois": m,
                "montant_cumul": valeurs[(a, m)],
                "montant_mois": flux.get((a, m)),
                "montant_cumul_n1": valeurs.get((a - 1, m)),
                "montant_mois_n1": flux.get((a - 1, m)),
            })
    return enregistrements


def controler_serie(enregistrements: list[dict]) -> None:
    """Garde-fous avant écriture : structure et ordres de grandeur (unités)."""
    lignes = {e["ligne_id"] for e in enregistrements}
    if len(lignes) != NB_LIGNES_ATTENDU:
        raise ValueError(f"{len(lignes)} lignes SMB au lieu de {NB_LIGNES_ATTENDU}")
    temoins = [e for e in enregistrements
               if e["ligne"] == LIGNE_TEMOIN and e["mois"] == 12]
    if not temoins:
        raise ValueError(f"ligne témoin absente: {LIGNE_TEMOIN!r}")
    for e in temoins:
        if not (TEMOIN_MIN <= e["montant_cumul"] <= TEMOIN_MAX):
            raise ValueError(
                "ordre de grandeur suspect (erreur d'unité ?) : "
                f"{LIGNE_TEMOIN} {e['annee']} = {e['montant_cumul']:.0f} € "
                f"hors [{TEMOIN_MIN:.0f}, {TEMOIN_MAX:.0f}]"
            )


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS budget_mensuel (
    ligne_id         TEXT    NOT NULL,
    ordre            INTEGER NOT NULL,
    niveau           INTEGER NOT NULL,
    categorie        TEXT    NOT NULL,
    sous_categorie   TEXT    NOT NULL,
    ligne            TEXT    NOT NULL,
    date_fin_mois    TEXT    NOT NULL,
    annee            INTEGER NOT NULL,
    mois             INTEGER NOT NULL CHECK (mois BETWEEN 1 AND 12),
    montant_cumul    REAL    NOT NULL,
    montant_mois     REAL,
    montant_cumul_n1 REAL,
    montant_mois_n1  REAL,
    PRIMARY KEY (ligne_id, date_fin_mois)
);
CREATE INDEX IF NOT EXISTS idx_budget_mensuel_annee_mois
    ON budget_mensuel(annee, mois);
"""


def lire_csv(chemin: Path, encodage: str) -> list[list[str]]:
    with open(chemin, encoding=encodage, newline="") as f:
        return list(csv.reader(f, delimiter=";"))


def main() -> int:
    try:
        chemin_export = telecharger(URL_EXPORT, "budget/smb_export.csv",
                                    max_age_heures=24)
        chemin_hist = telecharger(URL_HISTORIQUE, "budget/smb_2013_2023.csv",
                                  max_age_heures=7 * 24)
        tableau_export, mois_export = extraire_tableau(
            lire_csv(chemin_export, "utf-8-sig"))
        tableau_hist, mois_hist = extraire_tableau(
            lire_csv(chemin_hist, "utf-16"))
        log.info("export: %d lignes × %d mois (%s → %s) ; historique: %d lignes × %d mois",
                 len(tableau_export), len(mois_export), min(mois_export),
                 max(mois_export), len(tableau_hist), len(mois_hist))

        enregistrements = construire_serie(tableau_export, tableau_hist)
        controler_serie(enregistrements)
        date_max = max(e["date_fin_mois"] for e in enregistrements)

        conn = db.init_db()
        conn.executescript(_DDL)
        conn.commit()
        with conn:  # transaction : réécriture idempotente, tout ou rien
            conn.execute("DELETE FROM budget_mensuel")
            conn.executemany(
                """INSERT INTO budget_mensuel
                   (ligne_id, ordre, niveau, categorie, sous_categorie, ligne,
                    date_fin_mois, annee, mois, montant_cumul, montant_mois,
                    montant_cumul_n1, montant_mois_n1)
                   VALUES (:ligne_id, :ordre, :niveau, :categorie,
                           :sous_categorie, :ligne, :date_fin_mois, :annee,
                           :mois, :montant_cumul, :montant_mois,
                           :montant_cumul_n1, :montant_mois_n1)""",
                enregistrements,
            )
        db.upsert_meta(
            conn,
            source_id=SOURCE_ID,
            nom="Situations mensuelles budgétaires de l'État, séries longues (DGFiP)",
            url=URL_PAGE,
            licence="Licence Ouverte 2.0",
            frequence="mensuelle",
            date_donnees=date_max,
            lignes=len(enregistrements),
            notes="Cumuls depuis le 1er janvier, euros ; mois infra-annuels "
                  "provisoires ; export API (2024→) + pièce jointe 2013-2023 ; "
                  "pas de détail mission/programme dans cette source.",
        )
        conn.close()
        log.info("budget_mensuel: %d enregistrements écrits, données au %s",
                 len(enregistrements), date_max)
        return 0
    except Exception:
        log.exception("échec de l'ingestion S13 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
