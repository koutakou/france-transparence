"""P2 — Structure annuelle du budget de l'État (S20, S21, S23, data.economie.gouv.fr).

Trois sources annuelles (Licence Ouverte 2.0), trois tables, module UI
« Dépenses de l'État » (+ top missions de l'Accueil) :

1) S20 — « plf-2026-budget-vert » (1 816 lignes, 46 missions) → budget_vert :
     type_depense       TEXT  'Crédits budgétaires' | 'Taxes affectées plafonnées' | 'Dépenses fiscales'
     mission            TEXT
     numero_programme   INTEGER (NULL hors crédits budgétaires)
     programme          TEXT
     code_action        TEXT  (source : code_action_si_credit_budgetaire)
     action             TEXT  (source : action_si_credit_budgetaire)
     affectataire       TEXT  (source : affectataire_si_taxe_affectee)
     impot              TEXT  (source : impot_si_depense_fiscale)
     code_depense       TEXT  ex. '178-05-83'
     libelle            TEXT
     cotation_globale   TEXT  ('Favorable', 'Neutre', 'Défavorable', 'Mixte', 'NC'…)
     categorie_generale TEXT
     attenuation_climat/adaptation_climat/eau/dechets/pollutions/biodiversite REAL
     execution_2024_cp  REAL  exécution 2024 réelle (CP, €) — la plus fine dispo par action
     lfi_2025_cp        REAL  (source : lfi_2025_cp_ou_prevision_2025_si_depense_fiscale)
     plf_2026_cp        REAL  (source : plf_2026_cp_ou_prevision_2026_si_depense_fiscale)
     etiquette_2026     TEXT  ⚠ montants 2026 = PLF déposé, PAS la LFI promulguée
   Répartition/top missions : SELECT mission, SUM(plf_2026_cp) FROM budget_vert
   WHERE type_depense = 'Crédits budgétaires' GROUP BY mission ORDER BY 2 DESC.

2) S21 — « plf25-depenses-2025-selon-destination » (2 404 lignes) →
   budget_destination_2025 (colonnes source conservées, + etiquette_montants) :
     exercice INTEGER, loi TEXT ('PLF'), etiquette_montants TEXT,
     typebudget TEXT ('BG', 'BA', 'CAS', 'CCF'),
     ministere/libelle_ministere, mission/libelle_mission,
     programme/libelle_programme, action/libelle_action,
     sous_action/libelle_sous_action, categorie TEXT, titre TEXT,
     autorisation_engagement REAL, credit_de_paiement REAL (€)
   Répartition par ministère : GROUP BY libelle_ministere (20 ministères).
   NB titre (nomenclature LOLF) : 1 pouvoirs publics, 2 personnel,
   3 fonctionnement, 4 charge de la dette, 5 investissement, 6 intervention,
   7 opérations financières. Montants BG BRUTS (remboursements et
   dégrèvements inclus) : ne pas comparer tels quels aux « dépenses nettes »
   de budget_mensuel (S13).

3) S23 — jaune « effort financier de l'État en faveur des associations »
   PLF 2025 (112 722 lignes, versements 2023) → subventions_associations :
     annee_versement INTEGER (2023), programme TEXT, siren TEXT (9 chiffres ou
     NULL), nic TEXT, denomination TEXT, montant REAL (€),
     objet TEXT (source : objet_2023), convention TEXT (source : convention_2022),
     date_creation_etablissement TEXT, etat_administratif TEXT,
     categorie_juridique TEXT, cog_code TEXT, cog_libelle TEXT,
     departement TEXT (dérivé de cog_code : '75', '2A', '971'… ; NULL si
     étranger, COM 977/978/98x ou code invalide — qualité Chorus brute)
   Top bénéficiaires : GROUP BY siren, denomination ORDER BY SUM(montant) DESC.

Pièges gérés : SIREN « NR\\nCHORUS » → NULL ; espaces insécables U+00A0/U+202F
et retours ligne dans les textes → nettoyés ; lignes Chorus décalées (cog_code
non numérique) → departement NULL, champs bruts conservés.

Exécution : python -m pipelines.ingest_budget_structure
Base : FT_DB_PATH sinon data/france.db. Tout est téléchargé et transformé
AVANT écriture ; réécriture idempotente (DELETE puis INSERT), les 3 tables
dans UNE transaction ; puis upsert_meta par source (S20, S21, S23).
Échec d'une source → exit ≠ 0, base intacte.
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from pathlib import Path

import duckdb

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("budget_structure")

URL_BASE = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
URL_VERT = URL_BASE + "plf-2026-budget-vert/exports/csv"
URL_DEST = URL_BASE + "plf25-depenses-2025-selon-destination/exports/csv"
URL_ASSOS = (URL_BASE + "plf25-donnees-de-l-annexe-jaune-effort-financier-"
             "de-l-etat-en-faveur-des-associations/exports/csv")

PAGE_VERT = "https://data.economie.gouv.fr/explore/dataset/plf-2026-budget-vert/"
PAGE_DEST = ("https://data.economie.gouv.fr/explore/dataset/"
             "plf25-depenses-2025-selon-destination/")
PAGE_ASSOS = ("https://data.economie.gouv.fr/explore/dataset/plf25-donnees-de-l-"
              "annexe-jaune-effort-financier-de-l-etat-en-faveur-des-associations/")

ETIQUETTE_2026 = ("PLF 2026 déposé le 14/10/2025 — pas la LFI promulguée le "
                  "19/02/2026 (jamais publiée en données)")
ETIQUETTE_2025 = "PLF 2025 déposé en octobre 2024 — projet, pas la LFI 2025 votée"
ANNEE_VERSEMENT_ASSOS = 2023  # millésime du jaune PLF 2025 (colonne source objet_2023)

# ---------------------------------------------------------------------------
# Transformations pures (testées dans pipelines/tests/test_budget.py)
# ---------------------------------------------------------------------------


def nettoyer_texte(s: str | None) -> str | None:
    """Qualité Chorus : espaces insécables (U+00A0/U+202F), retours ligne et
    espaces multiples → un espace ; vide → None. Ne modifie pas le contenu."""
    if s is None:
        return None
    s = unicodedata.normalize("NFC", s)
    s = s.replace(" ", " ").replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def normaliser_siren(s: str | None) -> str | None:
    """SIREN valide (9 chiffres, espaces/retours ligne ignorés) sinon None
    (« NR\\nCHORUS » et variantes → None : champ manquant, jamais fabriqué)."""
    if s is None:
        return None
    s = re.sub(r"\s+", "", s)
    return s if re.fullmatch(r"\d{9}", s) else None


def normaliser_nic(s: str | None) -> str | None:
    """NIC valide (5 chiffres) sinon None."""
    if s is None:
        return None
    s = re.sub(r"\s+", "", s)
    return s if re.fullmatch(r"\d{5}", s) else None


def departement_depuis_cog(cog: str | None) -> str | None:
    """Code officiel géographique de commune → département, sinon None.

    '75117' → '75' ; '2A004' → '2A' ; '97209' → '972' (DROM) ;
    None pour : étranger (99xxx), COM (977/978, 98xxx), codes hors norme
    (lignes Chorus décalées : 'Oui', '0', libellés…).
    """
    if cog is None:
        return None
    cog = cog.strip()
    if re.fullmatch(r"2[AB]\d{3}", cog):
        return cog[:2]
    if not re.fullmatch(r"\d{5}", cog):
        return None
    if cog.startswith("97"):
        return cog[:3] if cog[2] in "123456" else None
    if cog.startswith(("98", "99", "96", "20", "00")):
        return None
    return cog[:2]


def _nombre(s: str | None) -> float | None:
    """Montant/cotation de l'export ODS (décimales '.') → float ; vide → None."""
    if s is None:
        return None
    s = s.strip()
    return float(s) if s else None


def _entier(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.strip()
    return int(s) if s else None


def transformer_vert(ligne: dict) -> dict:
    """Ligne du CSV budget vert (dict source) → dict table budget_vert."""
    return {
        "type_depense": nettoyer_texte(ligne["type_depense"]),
        "mission": nettoyer_texte(ligne["mission"]),
        "numero_programme": _entier(ligne["numero_programme"]),
        "programme": nettoyer_texte(ligne["programme"]),
        "code_action": nettoyer_texte(ligne["code_action_si_credit_budgetaire"]),
        "action": nettoyer_texte(ligne["action_si_credit_budgetaire"]),
        "affectataire": nettoyer_texte(ligne["affectataire_si_taxe_affectee"]),
        "impot": nettoyer_texte(ligne["impot_si_depense_fiscale"]),
        "code_depense": nettoyer_texte(ligne["code_depense"]),
        "libelle": nettoyer_texte(ligne["libelle"]),
        "cotation_globale": nettoyer_texte(ligne["cotation_globale"]),
        "categorie_generale": nettoyer_texte(ligne["categorie_generale"]),
        "attenuation_climat": _nombre(ligne["attenuation_climat"]),
        "adaptation_climat": _nombre(ligne["adaptation_climat"]),
        "eau": _nombre(ligne["eau"]),
        "dechets": _nombre(ligne["dechets"]),
        "pollutions": _nombre(ligne["pollutions"]),
        "biodiversite": _nombre(ligne["biodiversite"]),
        "execution_2024_cp": _nombre(ligne["execution_2024_cp"]),
        "lfi_2025_cp": _nombre(
            ligne["lfi_2025_cp_ou_prevision_2025_si_depense_fiscale"]),
        "plf_2026_cp": _nombre(
            ligne["plf_2026_cp_ou_prevision_2026_si_depense_fiscale"]),
        "etiquette_2026": ETIQUETTE_2026,
    }


def transformer_destination(ligne: dict) -> dict:
    """Ligne du CSV PLF 2025 destination → dict table budget_destination_2025."""
    return {
        "exercice": _entier(ligne["exercice"]),
        "loi": nettoyer_texte(ligne["loi"]),
        "etiquette_montants": ETIQUETTE_2025,
        "typebudget": nettoyer_texte(ligne["typebudget"]),
        "ministere": nettoyer_texte(ligne["ministere"]),
        "libelle_ministere": nettoyer_texte(ligne["libelle_ministere"]),
        "mission": nettoyer_texte(ligne["mission"]),
        "libelle_mission": nettoyer_texte(ligne["libelle_mission"]),
        "programme": nettoyer_texte(ligne["programme"]),
        "libelle_programme": nettoyer_texte(ligne["libelle_programme"]),
        "action": nettoyer_texte(ligne["action"]),
        "libelle_action": nettoyer_texte(ligne["libelle_action"]),
        "sous_action": nettoyer_texte(ligne["sous_action"]),
        "libelle_sous_action": nettoyer_texte(ligne["libelle_sous_action"]),
        "categorie": nettoyer_texte(ligne["categorie"]),
        "titre": nettoyer_texte(ligne["titre"]),
        "autorisation_engagement": _nombre(ligne["autorisation_engagement"]),
        "credit_de_paiement": _nombre(ligne["credit_de_paiement"]),
    }


def transformer_subvention(ligne: dict) -> dict:
    """Ligne du CSV jaune associations → dict table subventions_associations."""
    cog = nettoyer_texte(ligne["cog_code"])
    return {
        "annee_versement": ANNEE_VERSEMENT_ASSOS,
        "programme": nettoyer_texte(ligne["programme"]),
        "siren": normaliser_siren(ligne["siren"]),
        "nic": normaliser_nic(ligne["nic"]),
        "denomination": nettoyer_texte(ligne["denomination"]),
        "montant": _nombre(ligne["montant"]),
        "objet": nettoyer_texte(ligne["objet_2023"]),
        "convention": nettoyer_texte(ligne["convention_2022"]),
        "date_creation_etablissement": nettoyer_texte(
            ligne["date_de_creation_de_l_etablissement"]),
        "etat_administratif": nettoyer_texte(ligne["etat_administratif"]),
        "categorie_juridique": nettoyer_texte(ligne["categorie_juridique"]),
        "cog_code": cog,
        "cog_libelle": nettoyer_texte(ligne["cog_libelle"]),
        "departement": departement_depuis_cog(cog),
    }


# ---------------------------------------------------------------------------
# Lecture des sources
# ---------------------------------------------------------------------------


def lire_csv_dicts(chemin: Path) -> list[dict]:
    """Petit export ODS (UTF-8 BOM, ';') → liste de dicts (stdlib)."""
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def lire_assos_duckdb(chemin: Path) -> list[dict]:
    """Jaune associations (17 Mo, retours ligne cités dans les champs) via
    DuckDB, tout en texte (le typage est fait par transformer_subvention)."""
    rel = duckdb.sql(
        "SELECT * FROM read_csv(?, delim=';', header=true, all_varchar=true)",
        params=[str(chemin)],
    )
    colonnes = [d[0] for d in rel.description]
    return [dict(zip(colonnes, valeurs)) for valeurs in rel.fetchall()]


# ---------------------------------------------------------------------------
# Garde-fous (ordres de grandeur : budget de l'État ~450-500 Md€/an)
# ---------------------------------------------------------------------------


def controler(verts: list[dict], dests: list[dict], assos: list[dict]) -> None:
    if len(verts) < 1500:
        raise ValueError(f"budget vert : {len(verts)} lignes (< 1500 attendu ~1816)")
    missions = {v["mission"] for v in verts}
    if not 40 <= len(missions) <= 60:
        raise ValueError(f"budget vert : {len(missions)} missions (attendu ~46)")
    total_plf26 = sum(v["plf_2026_cp"] or 0 for v in verts
                      if v["type_depense"] == "Crédits budgétaires")
    if not 300e9 <= total_plf26 <= 800e9:
        raise ValueError(
            f"budget vert : total PLF 2026 crédits budgétaires = {total_plf26:.3e} € "
            "hors [300 Md€, 800 Md€] — erreur d'unité ?")
    if len(dests) < 2000:
        raise ValueError(f"destination 2025 : {len(dests)} lignes (< 2000 attendu ~2404)")
    total_bg = sum(d["credit_de_paiement"] or 0 for d in dests
                   if d["typebudget"] == "BG")
    if not 400e9 <= total_bg <= 900e9:
        raise ValueError(
            f"destination 2025 : CP budget général = {total_bg:.3e} € "
            "hors [400 Md€, 900 Md€] — erreur d'unité ?")
    if len(assos) < 100_000:
        raise ValueError(f"jaune associations : {len(assos)} lignes (< 100 000 attendu ~112 722)")
    total_assos = sum(a["montant"] or 0 for a in assos)
    if not 3e9 <= total_assos <= 40e9:
        raise ValueError(
            f"jaune associations : total = {total_assos:.3e} € "
            "hors [3 Md€, 40 Md€] — erreur d'unité ?")


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS budget_vert (
    type_depense       TEXT NOT NULL,
    mission            TEXT NOT NULL,
    numero_programme   INTEGER,
    programme          TEXT,
    code_action        TEXT,
    action             TEXT,
    affectataire       TEXT,
    impot              TEXT,
    code_depense       TEXT,
    libelle            TEXT,
    cotation_globale   TEXT,
    categorie_generale TEXT,
    attenuation_climat REAL,
    adaptation_climat  REAL,
    eau                REAL,
    dechets            REAL,
    pollutions         REAL,
    biodiversite       REAL,
    execution_2024_cp  REAL,
    lfi_2025_cp        REAL,
    plf_2026_cp        REAL,
    etiquette_2026     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_budget_vert_mission ON budget_vert(mission);
CREATE INDEX IF NOT EXISTS idx_budget_vert_type ON budget_vert(type_depense);

CREATE TABLE IF NOT EXISTS budget_destination_2025 (
    exercice                INTEGER NOT NULL,
    loi                     TEXT NOT NULL,
    etiquette_montants      TEXT NOT NULL,
    typebudget              TEXT,
    ministere               TEXT,
    libelle_ministere       TEXT,
    mission                 TEXT,
    libelle_mission         TEXT,
    programme               TEXT,
    libelle_programme       TEXT,
    action                  TEXT,
    libelle_action          TEXT,
    sous_action             TEXT,
    libelle_sous_action     TEXT,
    categorie               TEXT,
    titre                   TEXT,
    autorisation_engagement REAL,
    credit_de_paiement      REAL
);
CREATE INDEX IF NOT EXISTS idx_budget_dest_ministere
    ON budget_destination_2025(libelle_ministere);
CREATE INDEX IF NOT EXISTS idx_budget_dest_mission
    ON budget_destination_2025(libelle_mission);

CREATE TABLE IF NOT EXISTS subventions_associations (
    annee_versement             INTEGER NOT NULL,
    programme                   TEXT,
    siren                       TEXT,
    nic                         TEXT,
    denomination                TEXT,
    montant                     REAL,
    objet                       TEXT,
    convention                  TEXT,
    date_creation_etablissement TEXT,
    etat_administratif          TEXT,
    categorie_juridique         TEXT,
    cog_code                    TEXT,
    cog_libelle                 TEXT,
    departement                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_subv_assos_siren ON subventions_associations(siren);
CREATE INDEX IF NOT EXISTS idx_subv_assos_dept ON subventions_associations(departement);
CREATE INDEX IF NOT EXISTS idx_subv_assos_programme ON subventions_associations(programme);
CREATE INDEX IF NOT EXISTS idx_subv_assos_montant ON subventions_associations(montant);
"""


def _inserer(conn, table: str, enregistrements: list[dict]) -> None:
    colonnes = list(enregistrements[0])
    conn.execute(f"DELETE FROM {table}")
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(colonnes)}) "
        f"VALUES ({', '.join(':' + c for c in colonnes)})",
        enregistrements,
    )


def main() -> int:
    try:
        # 1. Tout télécharger et transformer AVANT d'écrire (base intacte si échec).
        chemin_vert = telecharger(URL_VERT, "budget/plf2026_budget_vert.csv",
                                  max_age_heures=7 * 24)
        chemin_dest = telecharger(URL_DEST, "budget/plf25_destination.csv",
                                  max_age_heures=7 * 24)
        chemin_assos = telecharger(URL_ASSOS, "budget/jaune_associations_2023.csv",
                                   max_age_heures=7 * 24)

        verts = [transformer_vert(l) for l in lire_csv_dicts(chemin_vert)]
        dests = [transformer_destination(l) for l in lire_csv_dicts(chemin_dest)]
        assos = [transformer_subvention(l) for l in lire_assos_duckdb(chemin_assos)]
        controler(verts, dests, assos)
        log.info("transformé : budget_vert %d, destination %d, subventions %d",
                 len(verts), len(dests), len(assos))

        # 2. Écriture : les 3 tables dans une seule transaction.
        conn = db.init_db()
        conn.executescript(_DDL)
        conn.commit()
        with conn:
            _inserer(conn, "budget_vert", verts)
            _inserer(conn, "budget_destination_2025", dests)
            _inserer(conn, "subventions_associations", assos)

        # 3. Fraîcheur par source (date de la donnée, jamais la date du jour).
        db.upsert_meta(
            conn, source_id="S20",
            nom="PLF 2026 — Budget vert (mission × programme × action)",
            url=PAGE_VERT, licence="Licence Ouverte 2.0", frequence="annuelle",
            date_donnees="2025-10-14",
            lignes=len(verts),
            notes="Montants 2026 = PLF déposé le 14/10/2025, PAS la LFI "
                  "promulguée le 19/02/2026 (mention « PLF » obligatoire à "
                  "l'affichage) ; inclut l'exécution 2024 réelle en CP par action.",
        )
        db.upsert_meta(
            conn, source_id="S21",
            nom="PLF 2025 — dépenses selon destination (ministère → sous-action × titre)",
            url=PAGE_DEST, licence="Licence Ouverte 2.0", frequence="annuelle",
            date_donnees="2024-10-11",
            lignes=len(dests),
            notes="PLF 2025 déposé en octobre 2024 (données publiées le "
                  "11/10/2024) — projet de loi, pas la LFI votée ; aucun "
                  "équivalent PLF/LFI 2026 en données ; montants BG bruts.",
        )
        db.upsert_meta(
            conn, source_id="S23",
            nom="Jaune PLF 2025 — subventions de l'État aux associations (versements 2023)",
            url=PAGE_ASSOS, licence="Licence Ouverte 2.0", frequence="annuelle",
            date_donnees="2023-12-31",
            lignes=len(assos),
            notes="Versements 2023, publiés en décembre 2024 avec le PLF 2025 "
                  "(décalage ~2 ans) ; le jaune PLF 2026 n'est pas publié en "
                  "données au 19/08/2026 ; qualité Chorus brute (SIREN « NR » "
                  "→ NULL, textes nettoyés).",
        )
        conn.close()
        log.info("écrit : budget_vert=%d, budget_destination_2025=%d, "
                 "subventions_associations=%d", len(verts), len(dests), len(assos))
        return 0
    except Exception:
        log.exception("échec de l'ingestion S20/S21/S23 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())
