"""Tests S52 — sanctions financières ADLC (CSV 2009+ joint aux métadonnées).

Les CSV de fixture sont INVENTÉS (pièges de grain, personnes physiques).
Aucune valeur live de l'Autorité de la concurrence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_adlc import (
    OCTETS_MAX_CSV,
    SOURCE_ID,
    TITRE_META,
    TITRE_SANCTIONS,
    URL_PAGE,
    _ressource_csv,
    assembler,
    controler_ampleur,
    controler_grain,
    ecrire_db,
    est_personne_physique,
    extraire_meta,
    extraire_sanctions,
    ingere_depuis_fichiers,
)

FIXTURES = Path(__file__).parent / "fixtures" / "adlc"


@pytest.fixture
def sanctions_csv() -> Path:
    return FIXTURES / "sanctions.csv"


@pytest.fixture
def meta_csv() -> Path:
    return FIXTURES / "metadata.csv"


@pytest.fixture
def brutes(sanctions_csv: Path):
    return extraire_sanctions(sanctions_csv)


@pytest.fixture
def meta(meta_csv: Path):
    return extraire_meta(meta_csv)


@pytest.fixture
def assemble(brutes, meta):
    return assembler(brutes, meta)


@pytest.fixture
def conn(tmp_path, sanctions_csv, meta_csv):
    c = db.init_db(chemin=tmp_path / "france.db")
    ingere_depuis_fichiers(
        c, sanctions_csv, meta_csv, verifier_ampleur=False
    )
    yield c
    c.close()


def test_filtre_personnes_civil_et_revue():
    assert est_personne_physique("99-D-02", "M. Dupont")
    assert est_personne_physique("19-D-19", "M. I...")
    assert est_personne_physique("18-D-19", "J. Grenot")
    assert est_personne_physique("09-D-25", "R. Vecchietti")
    assert not est_personne_physique("16-D-09", "C. Steinweg")
    assert not est_personne_physique("16-D-09", "C. Steinweg Belgium N.V.")
    assert not est_personne_physique("16-D-09", "Sermétal Réunion")


def test_assembler_retire_physiques_garde_steinweg_et_sermetal(assemble):
    decisions, lignes = assemble
    ids = {d["id_decision"] for d in decisions}
    assert "18-D-19" not in ids
    assert "09-D-25" in ids
    assert "16-D-09" in ids
    assert "99-D-02" in ids
    noms = {(l["id_decision"], l["denomination"]) for l in lignes}
    assert ("18-D-19", "J. Grenot") not in noms
    assert ("09-D-25", "R. Vecchietti") not in noms
    assert ("99-D-02", "M. Dupont") not in noms
    assert ("16-D-09", "C. Steinweg") in noms
    assert ("16-D-09", "C. Steinweg Belgium N.V.") in noms
    sermetal = [
        l
        for l in lignes
        if l["id_decision"] == "16-D-09" and l["denomination"] == "Sermétal Réunion"
    ]
    assert sorted(x["montant_individuel"] for x in sermetal) == [523000.0, 907000.0]
    d09 = next(d for d in decisions if d["id_decision"] == "09-D-25")
    assert d09["montant_total"] == 4200000.0


def test_grain_id_decision_pas_les_sommes_interdites(brutes, assemble):
    decisions, lignes = assemble
    controler_grain(brutes, decisions, lignes)
    heros = sum(d["montant_total"] for d in decisions)
    # 150 + 100 + 4_200_000 + 5_021_000 + 12_670_000 + 148_094
    assert heros == 150 + 100 + 4_200_000 + 5_021_000 + 12_670_000 + 148_094
    somme_ind = sum(l["montant_individuel"] for l in brutes)
    somme_naive = sum(l["montant_total"] for l in brutes)
    assert somme_ind != heros
    assert somme_naive != heros
    assert somme_ind != somme_naive


def test_controler_ampleur_refuse_fixture_hors_bornes(brutes, assemble):
    decisions, lignes = assemble
    with pytest.raises(ValueError, match="décisions conservées"):
        controler_ampleur(brutes, decisions, lignes)


def test_ecrire_db_meta_s52_date_derniere_decision(conn):
    n = conn.execute("SELECT count(*) AS n FROM adlc_decisions").fetchone()["n"]
    assert n == 6
    n_lignes = conn.execute("SELECT count(*) AS n FROM adlc_lignes").fetchone()["n"]
    assert n_lignes == 10
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert ligne is not None
    assert ligne["source_id"] == "S52"
    assert "Licence Ouverte 2.0" in ligne["licence"]
    assert ligne["frequence"] == "mensuelle"
    assert ligne["date_donnees"] == "2026-04-16"
    assert ligne["url"] == URL_PAGE
    assert ligne["lignes"] == 6
    notes = ligne["notes"].lower()
    assert "s39" in notes
    assert "s13" in notes
    assert "id_decision" in notes
    assert "last_modified" in notes
    assert "json" in notes
    assert "sondage" not in notes
    assert "baromètre" not in notes
    assert "barometre" not in notes
    assert "recouvré" not in notes
    assert "recouvre" in notes
    civil = conn.execute(
        "SELECT count(*) AS n FROM adlc_lignes WHERE denomination LIKE 'M. %'"
    ).fetchone()["n"]
    assert civil == 0
    grenot = conn.execute(
        "SELECT count(*) AS n FROM adlc_decisions WHERE id_decision = '18-D-19'"
    ).fetchone()["n"]
    assert grenot == 0
    heros = conn.execute(
        "SELECT SUM(montant_total) AS t FROM adlc_decisions"
    ).fetchone()["t"]
    ind = conn.execute(
        "SELECT SUM(montant_individuel) AS t FROM adlc_lignes"
    ).fetchone()["t"]
    assert heros != ind
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "adlc_decisions" in tables
    assert "adlc_lignes" in tables
    assert "scrutins" not in tables
    assert "votes_recents" not in tables


def test_date_donnees_pas_une_dcc_plus_recente(conn):
    """26-DCC-147 (2026-07-13) n'a pas d'amende : elle ne date pas S52."""
    d = conn.execute(
        "SELECT date_donnees FROM meta_sources WHERE source_id = 'S52'"
    ).fetchone()["date_donnees"]
    assert d == "2026-04-16"
    assert d < "2026-07-13"


def test_idempotent(tmp_path, sanctions_csv, meta_csv):
    c = db.init_db(chemin=tmp_path / "france.db")
    ingere_depuis_fichiers(c, sanctions_csv, meta_csv, verifier_ampleur=False)
    ingere_depuis_fichiers(c, sanctions_csv, meta_csv, verifier_ampleur=False)
    n = c.execute("SELECT count(*) AS n FROM adlc_decisions").fetchone()["n"]
    assert n == 6
    c.close()


def test_ressource_csv_refuse_json_et_xlsx():
    dataset = {
        "resources": [
            {
                "title": "adlc-texte-complet-publications.json",
                "format": "json",
                "mime": "application/json",
                "filesize": 218_725_341,
                "url": "https://example.test/huge.json",
            },
            {
                "title": "listeentreprisessanctionnees.xlsx",
                "format": "xlsx",
                "filesize": 80_418,
                "url": "https://example.test/old.xlsx",
            },
            {
                "title": TITRE_SANCTIONS,
                "format": "csv",
                "mime": "text/csv",
                "filesize": 63_943,
                "url": "https://example.test/sanctions.csv",
            },
        ]
    }
    r = _ressource_csv(dataset, TITRE_SANCTIONS, OCTETS_MAX_CSV)
    assert r["url"] == "https://example.test/sanctions.csv"
    with pytest.raises(RuntimeError, match="JSON"):
        _ressource_csv(
            {
                "resources": [
                    {
                        "title": TITRE_META,
                        "format": "json",
                        "mime": "application/json",
                        "filesize": 1000,
                        "url": "https://example.test/meta.json",
                    }
                ]
            },
            TITRE_META,
            OCTETS_MAX_CSV,
        )
    with pytest.raises(RuntimeError, match="tableur"):
        _ressource_csv(
            {
                "resources": [
                    {
                        "title": TITRE_SANCTIONS,
                        "format": "xlsx",
                        "filesize": 1000,
                        "url": "https://example.test/s.xlsx",
                    }
                ]
            },
            TITRE_SANCTIONS,
            OCTETS_MAX_CSV,
        )
    with pytest.raises(RuntimeError, match="trop volumineuse"):
        _ressource_csv(
            {
                "resources": [
                    {
                        "title": TITRE_META,
                        "format": "csv",
                        "filesize": OCTETS_MAX_CSV + 1,
                        "url": "https://example.test/gros.csv",
                    }
                ]
            },
            TITRE_META,
            OCTETS_MAX_CSV,
        )


def test_payload_api_exemple_ne_prend_pas_le_json():
    payload = json.loads(
        json.dumps(
            {
                "resources": [
                    {
                        "title": "adlc-texte-complet-publications.json",
                        "format": "json",
                        "filesize": 218_725_341,
                        "url": "https://example.test/219mo.json",
                    },
                    {
                        "title": TITRE_META,
                        "format": "csv",
                        "filesize": 2_389_925,
                        "url": "https://example.test/meta.csv",
                    },
                ]
            }
        )
    )
    r = _ressource_csv(payload, TITRE_META, OCTETS_MAX_CSV)
    assert "219mo" not in r["url"]
    assert r["url"].endswith("meta.csv")
